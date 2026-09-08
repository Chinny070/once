"""Studionet (chain 61999) lifecycle proof for Once.

Run only against the stable hosted Studionet endpoint configured as `studionet`.
This suite deploys Once plus its tiny consumer, creates a sealed idempotency profile,
proves semantic retry collapse under live consensus, and proves the consumer rejects
an alternative retry payload and replay.
"""

from pathlib import Path

from gltest import get_contract_factory, get_default_account
from gltest.assertions import tx_execution_failed, tx_execution_succeeded
from gltest.utils import extract_contract_address


TX_KW = {"consensus_max_rotations": 3, "wait_interval": 30000, "wait_retries": 14}
ONCE = Path("once.py")
EXECUTOR = Path("protected_executor.py")


def deploy(factory, account, args=None):
    kwargs = {"account": account, **TX_KW}
    if args is None:
        tx = factory.deploy_contract_tx(**kwargs)
    else:
        tx = factory.deploy_contract_tx(args=args, **kwargs)
    assert tx_execution_succeeded(tx), tx
    return factory.build_contract(extract_contract_address(tx), account=account)


def test_semantic_retry_collapse_and_consumer_replay_guard():
    account = get_default_account()

    once_factory = get_contract_factory(contract_file_path=ONCE)
    once = deploy(once_factory, account)

    executor_factory = get_contract_factory(contract_file_path=EXECUTOR)
    executor = deploy(executor_factory, account, [once.address])

    created = once.create_profile([
        "GPU purchase idempotency",
        "Prevent semantically equivalent retries from creating duplicate purchase side effects for one scoped job.",
        "Requests are the same effect only when fulfilling both would create the same purchase for the same scoped job. Material quantity, supplier, product, recipient, or total-price changes are different effects.",
        executor.address,
        3600,
    ]).transact(**TX_KW)
    assert tx_execution_succeeded(created), created

    sealed = once.seal_profile([1]).transact(**TX_KW)
    assert tx_execution_succeeded(sealed), sealed
    profile = once.get_profile([1]).call()
    profile_hash = profile["definition_hash"]
    assert profile["status_name"] == "SEALED"
    assert len(profile_hash) == 64

    canonical_action = "11" * 32
    alternative_action = "22" * 32

    first = once.submit_attempt([
        1,
        "atlas:batch-42:gpu",
        "Purchase two A100 GPU hours from Supplier Atlas for batch 42 at total price 90 USDC.",
        canonical_action,
    ]).transact(**TX_KW)
    assert tx_execution_succeeded(first), first
    a1 = once.get_attempt([1]).call()
    assert a1["verdict_name"] == "NEW_EFFECT"
    assert a1["effect_id"] == 1

    retry = once.submit_attempt([
        1,
        "atlas:batch-42:gpu",
        "Retry my existing Atlas order for two A100 GPU hours, total 90 USDC, for batch 42. Do not create a second purchase.",
        alternative_action,
    ]).transact(**TX_KW)
    assert tx_execution_succeeded(retry), retry
    a2 = once.get_attempt([2]).call()
    assert a2["verdict_name"] == "SAME_EFFECT"
    assert a2["effect_id"] == 1

    effect = once.get_effect([1]).call()
    assert effect["canonical_action_hash"] == canonical_action
    assert effect["attempt_count"] == 2

    # The semantically equivalent retry must not authorize its altered payload.
    denied_alt = executor.execute([1, profile_hash, alternative_action, "retry bytes must not execute"]).transact(**TX_KW)
    assert tx_execution_failed(denied_alt), denied_alt

    executed = executor.execute([1, profile_hash, canonical_action, "canonical purchase effect executed"]).transact(**TX_KW)
    assert tx_execution_succeeded(executed), executed
    assert executor.is_consumed([1]).call() is True

    replay = executor.execute([1, profile_hash, canonical_action, "replay attempt"]).transact(**TX_KW)
    assert tx_execution_failed(replay), replay
