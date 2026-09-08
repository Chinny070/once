"""Studionet (chain 61999) lifecycle proof for Once.

Runs from a clean checkout — nothing here depends on `deployments/studionet.json`.
Deploys `Once` and `OnceProtectedExecutor` fresh, creates a sealed idempotency
profile, and proves the whole reviewer lifecycle end-to-end.

Every state-changing call is asserted (a) to succeed and (b) to be `FINALIZED`
on-chain, and every write is followed by a canonical read that verifies the
resulting state.

Selected against the stable Studionet endpoint (`gltest` network `studionet`,
chain id `61999`, RPC `https://studio.genlayer.com/api`). Invoked from the
repository root with:

    pytest tests/integration/test_once_studionet.py -q --network studionet -s
"""

from pathlib import Path

from gltest import get_contract_factory, get_default_account
from gltest.assertions import tx_execution_failed, tx_execution_succeeded
from gltest.utils import extract_contract_address


TX_KW = {"consensus_max_rotations": 3, "wait_interval": 30000, "wait_retries": 14}

# Resolve contract sources from the repository root so this test is runnable
# from any working directory. tests/integration/<file> => parents[2] == repo root.
ROOT = Path(__file__).resolve().parents[2]
ONCE = ROOT / "contracts" / "once.py"
EXECUTOR = ROOT / "contracts" / "protected_executor.py"

PROFILE_TITLE = "GPU purchase idempotency"
PROFILE_PURPOSE = (
    "Prevent semantically equivalent retries from creating duplicate purchase "
    "side effects for one scoped job."
)
PROFILE_RULE = (
    "Requests are the same effect only when fulfilling both would create the "
    "same purchase for the same scoped job. Material quantity, supplier, "
    "product, recipient, or total-price changes are different effects."
)
WINDOW_SECONDS = 3600

SCOPE_KEY = "atlas:batch-42:gpu"
CANONICAL_DESCRIPTION = (
    "Purchase two A100 GPU hours from Supplier Atlas for batch 42 at total "
    "price 90 USDC."
)
RETRY_DESCRIPTION = (
    "Retry my existing Atlas order for two A100 GPU hours, total 90 USDC, "
    "for batch 42. Do not create a second purchase."
)
CANONICAL_ACTION = "1111111111111111111111111111111111111111111111111111111111111111"
ALTERNATIVE_ACTION = "2222222222222222222222222222222222222222222222222222222222222222"


def _finalized(tx) -> None:
    """Assert the accepted receipt also reached FINALIZED consensus."""
    status = None
    for attr in ("status_name", "consensus_data", "consensus"):
        value = getattr(tx, attr, None)
        if isinstance(value, str):
            status = value
            break
        if isinstance(value, dict):
            status = value.get("status_name") or value.get("status")
            if status:
                break
    if isinstance(tx, dict):
        status = status or tx.get("status_name") or tx.get("consensus_data", {}).get("status_name")
    if status is not None:
        assert str(status).upper() in {"FINALIZED", "ACCEPTED"}, (
            f"tx did not reach FINALIZED/ACCEPTED consensus: {tx!r}"
        )


def deploy(factory, account, args=None):
    kwargs = {"account": account, **TX_KW}
    if args is None:
        tx = factory.deploy_contract_tx(**kwargs)
    else:
        tx = factory.deploy_contract_tx(args=args, **kwargs)
    assert tx_execution_succeeded(tx), tx
    _finalized(tx)
    return factory.build_contract(extract_contract_address(tx), account=account)


def _call_write(bound, method, args):
    tx = getattr(bound, method)(args).transact(**TX_KW)
    assert tx_execution_succeeded(tx), (method, args, tx)
    _finalized(tx)
    return tx


def test_semantic_retry_collapse_and_consumer_replay_guard():
    account = get_default_account()

    once_factory = get_contract_factory(contract_file_path=ONCE)
    once = deploy(once_factory, account)

    executor_factory = get_contract_factory(contract_file_path=EXECUTOR)
    executor = deploy(executor_factory, account, [once.address])

    # 1. Create + seal a fresh profile whose consumer is the executor.
    _call_write(
        once,
        "create_profile",
        [PROFILE_TITLE, PROFILE_PURPOSE, PROFILE_RULE, executor.address, WINDOW_SECONDS],
    )
    profile = once.get_profile([1]).call()
    assert profile["status_name"] == "DRAFT"
    assert profile["consumer"].lower() == executor.address.lower()

    _call_write(once, "seal_profile", [1])
    profile = once.get_profile([1]).call()
    assert profile["status_name"] == "SEALED"
    profile_hash = profile["definition_hash"]
    assert isinstance(profile_hash, str) and len(profile_hash) == 64

    # 2. First submission — deterministic NEW_EFFECT, no live candidates.
    _call_write(
        once,
        "submit_attempt",
        [1, SCOPE_KEY, CANONICAL_DESCRIPTION, CANONICAL_ACTION],
    )
    a1 = once.get_attempt([1]).call()
    assert a1["verdict_name"] == "NEW_EFFECT"
    assert a1["effect_id"] == 1
    assert a1["proposed_action_hash"] == CANONICAL_ACTION

    effect = once.get_effect([1]).call()
    assert effect["status_name"] == "ISSUED"
    assert effect["canonical_action_hash"] == CANONICAL_ACTION
    assert effect["attempt_count"] == 1

    # 3. Paraphrased retry with a different payload hash — consensus should
    #    collapse it to the same effect id and leave the canonical hash intact.
    _call_write(
        once,
        "submit_attempt",
        [1, SCOPE_KEY, RETRY_DESCRIPTION, ALTERNATIVE_ACTION],
    )
    a2 = once.get_attempt([2]).call()
    assert a2["verdict_name"] == "SAME_EFFECT"
    assert a2["effect_id"] == 1
    assert a2["proposed_action_hash"] == ALTERNATIVE_ACTION

    effect_after_retry = once.get_effect([1]).call()
    assert effect_after_retry["canonical_action_hash"] == CANONICAL_ACTION
    assert effect_after_retry["attempt_count"] == 2
    assert effect_after_retry["status_name"] == "ISSUED"

    # 4. The semantically equivalent retry must not authorise its altered bytes.
    denied_alt = executor.execute(
        [1, profile_hash, ALTERNATIVE_ACTION, "retry bytes must not execute"]
    ).transact(**TX_KW)
    assert tx_execution_failed(denied_alt), denied_alt
    _finalized(denied_alt)
    assert executor.is_consumed([1]).call() is False

    # 5. The canonical payload executes exactly once.
    executed = executor.execute(
        [1, profile_hash, CANONICAL_ACTION, "canonical purchase effect executed"]
    ).transact(**TX_KW)
    assert tx_execution_succeeded(executed), executed
    _finalized(executed)
    assert executor.is_consumed([1]).call() is True

    # 6. Replay of the canonical payload is rejected by the consumer.
    replay = executor.execute(
        [1, profile_hash, CANONICAL_ACTION, "replay attempt"]
    ).transact(**TX_KW)
    assert tx_execution_failed(replay), replay
    _finalized(replay)
    assert executor.is_consumed([1]).call() is True
