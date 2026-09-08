# Deployment — stable Studionet only

Once is prepared for **GenLayer Studionet chain ID 61999**.

RPC:

```text
https://studio.genlayer.com/api
```

## 1. Prepare environment

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Add a funded throwaway Studionet key to `.env`. Never commit it.

## 2. Verify the network before doing anything stateful

```bash
python scripts/check_studionet.py
```

Expected output must end in:

```text
target chain 61999
```

or an equivalent successful chain report. If the RPC reports any other chain ID, stop.

## 3. Preflight

Run the whole gate suite in one command:

```bash
python scripts/verify_all.py
```

Or the individual steps:

```bash
python scripts/preflight.py
genvm-lint check contracts/once.py
genvm-lint check contracts/protected_executor.py
pytest tests/direct -q                          # 27 cases
pytest tests/integration --collect-only -q
```

Do not deploy while any of these fail.

## 4. Configure gltest

Use the `studionet` entry in `gltest.config.yaml`.

The stable endpoint is already explicit there.

## 5. Deploy Once

Either use the GenLayer CLI against the stable RPC or the gltest integration flow.

CLI shape:

```bash
genlayer network set studionet
genlayer network info
genlayer deploy --contract contracts/once.py --rpc https://studio.genlayer.com/api
```

Record the finalized address and deployment transaction hash.

## 6. Deploy the consumer

Constructor argument: the finalized Once address.

```bash
genlayer deploy --contract contracts/protected_executor.py --rpc https://studio.genlayer.com/api --args <ONCE_ADDRESS>
```

Record the finalized address and transaction hash.

## 7. Create the demo profile

Use the consumer address from step 6.

Suggested values:

```text
title:
GPU purchase idempotency

purpose:
Prevent semantically equivalent retries from creating duplicate purchase side effects for one scoped job.

equivalence_rule:
Requests are the same effect only when fulfilling both would create the same purchase for the same scoped job. Material quantity, supplier, product, recipient, or total-price changes are different effects.

consumer:
<PROTECTED_EXECUTOR_ADDRESS>

window_seconds:
3600
```

Call `seal_profile(1)` and read `get_profile(1)`. Record the 64-character `definition_hash`.

## 8. Prove semantic retry collapse

First attempt:

```text
scope_key: atlas:batch-42:gpu
description: Purchase two A100 GPU hours from Supplier Atlas for batch 42 at total price 90 USDC.
proposed_action_hash: 1111...1111 (64 bytes / 128 hex chars is fine)
```

Expected:

```text
NEW_EFFECT
Effect #1
```

Second attempt:

```text
scope_key: atlas:batch-42:gpu
description: Retry my existing Atlas order for two A100 GPU hours, total 90 USDC, for batch 42. Do not create a second purchase.
proposed_action_hash: 2222...2222
```

Expected under consensus:

```text
SAME_EFFECT
Effect #1
```

Read `get_effect(1)` and verify its `canonical_action_hash` is still the first hash.

## 9. Prove the consumer consequence

Call the consumer with Effect #1 and the retry hash. It must fail.

Call it with Effect #1 and the canonical first hash. It must succeed.

Call it again with the canonical hash. It must fail as replay.

## 10. Run/record the integration lifecycle

```bash
pytest tests/integration/test_once_studionet.py -q --network studionet -s
```

If the installed gltest version uses a different network-selection flag, use its documented `studionet` selector; do not change the RPC or chain target.

## 11. Update evidence

Fill `deployments/studionet.json` with real values and replace all
`PENDING` fields. Add the real transaction hashes and final commit SHA
to `SUBMISSION.md`.

Then re-run the machine-readable verifier and confirm every hash
resolves to a `FINALIZED` transaction with the expected execution
result:

```bash
python scripts/verify_live_evidence.py
```

## 12. Push only after evidence is truthful

```bash
git status
git add .
git commit -m "Build Once semantic idempotency primitive"
git push origin main
```
