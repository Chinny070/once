# Once

**Semantic idempotency for autonomous side effects on GenLayer.**

Once is a standalone reusable Intelligent Contract primitive. It prevents semantically equivalent retries from creating duplicate side effects when the requests are worded differently but mean the same thing.

It deliberately has **no frontend**. The repository is contract-first: one reusable primitive, one tiny consumer contract that proves IC-to-IC reuse, direct-mode tests, and a Studionet lifecycle proof.

## Why this exists

Ordinary idempotency keys work when the caller can resend exactly the same key. Autonomous agents often retry with materially different bytes:

- `Purchase 2 A100 GPU hours from Atlas for batch 42, total 90 USDC.`
- `Retry my Atlas order for two A100 hours, total 90 USDC, for batch 42. Do not create another order.`

A deterministic hash sees two different requests. A naïve agent may execute both.

Once separates the problem into two layers:

1. **Deterministic domain binding** — requester, profile, `scope_key`, immutable profile hash, consumer address, expiry window, and canonical action hash.
2. **GenLayer semantic consensus** — only when a new wording must be compared with existing live effects in the same deterministic domain.

The LLM never executes an action, chooses money amounts, edits the canonical payload, or creates a compromise. It only classifies a bounded relation:

`SAME_EFFECT | NEW_EFFECT | AMBIGUOUS`

## Core safety property

When a retry is classified as `SAME_EFFECT`, it receives the **existing effect ID**. It does **not** replace the first effect's `canonical_action_hash`.

So if the first attempt authorized payload hash `A` and a later semantic retry supplies payload hash `B`, the consumer still accepts only `A`.

That prevents semantic equivalence from becoming a payload-substitution primitive.

## Architecture

```text
requester
   |
   | submit_attempt(profile, scope, description, action_hash)
   v
+--------------------+
|        Once        |
|--------------------|
| deterministic      |
| domain filtering   |
|        |           |
|        v           |
| semantic consensus |----> NEW_EFFECT ------> effect + permit
|        |           |
|        +-----------> SAME_EFFECT -----> existing effect id
|        |           |
|        +-----------> AMBIGUOUS -------> no permit
+--------------------+
          |
          | is_executable(...)
          v
+---------------------------+
| OnceProtectedExecutor     |
|---------------------------|
| exact profile hash        |
| exact action hash         |
| exact requester           |
| exact registered consumer |
| local replay protection   |
+---------------------------+
```

## Contract files

### `contracts/once.py`

The reusable primitive.

Important state:

- `OperationProfile` — immutable after sealing.
- `Effect` — the canonical side effect and original action hash.
- `Attempt` — every submission and its classification receipt.

### `contracts/protected_executor.py`

A deliberately tiny consumer contract. It proves another Intelligent Contract can enforce a Once permit using a typed IC-to-IC view call. It is not a product or frontend.

The consumer refuses:

- unknown effects;
- revoked effects;
- expired effects;
- mismatched profile hashes;
- mismatched action hashes;
- the wrong requester;
- the wrong consumer address;
- replay of an already consumed effect.

## Profile lifecycle

```text
DRAFT
  |
  | seal_profile
  v
SEALED
```

A profile freezes:

- purpose;
- semantic equivalence rule;
- idempotency window;
- one consumer contract address.

`definition_hash` commits to all of them.

## Effect lifecycle

```text
               revoke
ISSUED --------------------> REVOKED
  |
  | idempotency window ends
  v
EXPIRED
```

Expiry is enforced both when candidate effects are selected and when a consumer calls `is_executable`. `expire_effect` also materializes the terminal state on-chain.

## Attempt outcomes

### `NEW_EFFECT`

No live equivalent side effect exists. Once creates a new canonical `Effect` and binds the first action hash.

### `SAME_EFFECT`

The request is a semantic retry of one existing effect. The attempt points to the old effect ID. No new permit is created and the original action hash remains canonical.

### `AMBIGUOUS`

The validator set cannot safely determine equivalence. No effect is created.

Failing closed on ambiguity is a protocol property, not an error-handling afterthought.

## Consensus design

The leader sees only a bounded candidate list already filtered by deterministic state:

- same profile;
- same requester;
- exact same `scope_key`;
- still inside the idempotency window.

The prompt contains the immutable profile purpose and equivalence rule plus candidate descriptions. Opaque action hashes are intentionally omitted from the semantic evidence.

The leader proposes:

```json
{
  "verdict": "SAME_EFFECT",
  "effect_id": 7,
  "reason": "same purchase side effect under the frozen rule"
}
```

A validator independently reruns the semantic classification and only accepts when both the enumerated verdict and selected candidate ID match.

The protocol separately validates the output shape and candidate membership. A leader cannot invent an effect ID.

## Deterministic shortcuts

Consensus is avoided when it is unnecessary:

- no live candidates in the exact requester/scope domain -> `NEW_EFFECT` deterministically;
- exact canonical request text already exists -> `SAME_EFFECT` deterministically.

This keeps the LLM at the smallest genuinely semantic boundary.

## Scope keys are a security boundary

`scope_key` is not produced by the LLM. Integrators should make it narrow and deterministic, for example:

```text
supplier:atlas/job:batch-42/operation:gpu-purchase
```

A scope should encode identifiers that must never be blurred by semantic judgement. If one scope accumulates too many simultaneously live effects, Once fails closed and requires a narrower scope instead of silently truncating the candidate set.

## Example

First attempt:

```text
scope: atlas:batch-42:gpu
request: Purchase two A100 GPU hours from Atlas for batch 42 at 90 USDC.
action hash: 1111...1111
```

Result:

```text
NEW_EFFECT
Effect #1
canonical action hash = 1111...1111
```

Retry:

```text
scope: atlas:batch-42:gpu
request: Retry my existing Atlas order for two A100 hours, total 90 USDC, for batch 42.
action hash: 2222...2222
```

Consensus:

```text
SAME_EFFECT -> Effect #1
```

The action hash remains:

```text
1111...1111
```

The consumer therefore rejects `2222...2222`, accepts `1111...1111` once, and rejects replay.

## Threat model highlights

Once explicitly defends against:

- paraphrased duplicate retries;
- payload substitution through a semantic retry;
- cross-requester collision;
- cross-scope collision;
- invented candidate IDs from a faulty leader;
- ambiguous semantic equivalence;
- revoked permits;
- stale permits;
- consumer mismatch;
- consumer replay;
- unbounded candidate truncation.

See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## What Once does not claim

Once does not prove that an external side effect really happened. It controls whether a compliant consumer should admit a side effect under a semantic idempotency policy.

It does not replace:

- payment settlement;
- authorization/mandates;
- workflow verification;
- agent conformance auditing;
- application-specific business logic.

It composes with those systems.

## Testing

Install the pinned development toolchain
(`genlayer-test==0.29.2`, `genvm-linter==0.10.0`, `pytest==9.1.1`):

```bash
python -m pip install -r requirements-dev.txt
```

One command runs every reviewer gate — Python compilation, static
preflight, GenVM lint & validation, direct-mode tests, integration-test
collection, Studionet chain-id guard, and the live-evidence verifier:

```bash
python scripts/verify_all.py
```

Set `ONCE_SKIP_LIVE=1` to skip the two live-RPC steps.

Individual steps:

```bash
python scripts/preflight.py
genvm-lint check contracts/once.py
genvm-lint check contracts/protected_executor.py
pytest tests/direct -q                              # 27 direct-mode cases
pytest tests/integration --collect-only -q          # collect-only sanity
python scripts/check_studionet.py                   # RPC reports chain 61999
python scripts/verify_live_evidence.py              # 30 on-chain checks
```

The direct suite covers deterministic first issuance, exact retries,
semantic retries, material changes, ambiguity, requester/scope
isolation, revocation, expiry, action-hash binding, consumer binding,
prompt-control rejection, malicious leader inventing an unknown
candidate id, malformed model output, validator disagreement,
action-hash immutability across three semantic retries, short
action_hash, empty scope, submit-before-seal, control-like
`equivalence_rule`, expired-effect executability, `MAX_LIVE_CANDIDATES`
overflow failing closed, profile-owner-only revocation, stranger revoke
rejection, and missing-timestamp fail-closed.

The Studionet integration test (`tests/integration/test_once_studionet.py`)
deploys both contracts from a clean checkout, runs the entire lifecycle,
verifies every write reaches `FINALIZED`, and reads canonical state
after each write. Contract paths resolve from the repository root, so
the test is invocable from any working directory:

```bash
pytest tests/integration/test_once_studionet.py -q --network studionet -s
```

CI enforces the same offline gates on every push and PR to `main`
(see `.github/workflows/ci.yml`), and a second job runs the live
Studionet checks on pushes to `main`.

## Studionet target

This repository targets **stable GenLayer Studionet, chain ID `61999`**.

RPC:

```text
https://studio.genlayer.com/api
```

Verify the RPC before deployment:

```bash
python scripts/check_studionet.py
```

Then run the lifecycle test using the `studionet` network configuration. See [`DEPLOYMENT.md`](DEPLOYMENT.md).

## Reviewer demo target

The high-signal live proof is intentionally short:

1. deploy `Once`;
2. deploy `OnceProtectedExecutor(once_address)`;
3. create and seal a profile whose consumer is the executor;
4. submit a canonical purchase request -> `NEW_EFFECT`;
5. submit a differently worded retry with another payload hash -> `SAME_EFFECT`, same effect ID;
6. show the canonical action hash did not change;
7. executor rejects the retry payload hash;
8. executor accepts the original hash;
9. executor rejects replay.

That demonstrates the primitive's actual reason to exist in one lifecycle.

## Live Studionet evidence (chain 61999)

All transactions below are **FINALIZED** on Studionet, chain ID `61999`,
RPC `https://studio.genlayer.com/api`. Explorer:
`https://genlayer-explorer.vercel.app`.

| Artefact | Value |
|---|---|
| `Once` address | `0xf25F26d356FD4aeccACF01A9bFbE7ea84a10dD70` |
| `Once` deploy tx | `0xc686051637969ecb981666078209ac7b7e120629acfbcaff23a4a84b18370a87` |
| `OnceProtectedExecutor` address | `0x0D97c40E422A865dD9E59824446d0A3C33400109` |
| `OnceProtectedExecutor` deploy tx | `0x53f420674b1ca2ab15226460a95ee73d03264b915825a5974a3a34b1fd644a1f` |
| Profile id | `3` |
| Profile `definition_hash` | `09a29293ad55b4b66c5f6a6d5891b5910da430c6eb8f2507bec4c3e47f282050` |
| `create_profile` tx | `0x1fc0a579534f18ac03b316c8c7302117323e023ae98ccb6ab22f3dca61a1a3a2` |
| `seal_profile` tx | `0xed78ecf6111998195470cdebe0fb2024649090a8d1c119cc7ab63cd792b555d7` |
| First attempt (`NEW_EFFECT`, effect #2) tx | `0x66ac416a1f2a294066a14d4647a507525067e8d2676e459d4d89d27225d32358` |
| Semantic retry (`SAME_EFFECT` → effect #2) tx | `0x5f5ab1be0c99bf49549f9a41ab8837ccfda88834e95b8e556c8986f5ca130c73` |
| Executor rejects alternative payload tx | `0x90a51a068036a71ff97dc3d5c7bfbe21e9a58440844a03642ef592d84426923a` |
| Executor accepts canonical payload tx | `0xe4a1ba3bdeccdf0f4992c2414fa2a87ad9b1492653b9592fcd3151424f733a74` |
| Executor rejects replay tx | `0x1c276d4183900a2e45f39ab8b547572e09f9161b6db947d39f6dd247d50a7c64` |

The retry paraphrase authorised action hash
`2222…2222`; the canonical effect kept action hash `1111…1111`. The
executor accepted `1111…1111` once and refused both `2222…2222` and a
second submission of `1111…1111`. See `deployments/studionet.json` for
the same evidence in machine-readable form.
