# Once — Intelligent Contract submission notes

## Category

Standalone GenLayer Intelligent Contract / reusable primitive.

There is no frontend. The second contract is a minimal consumer proving composability, not a product flow.

## One-line purpose

Once provides semantic exactly-once admission for autonomous side effects: differently worded retries can resolve to one canonical effect and one immutable execution payload.

## Why GenLayer is necessary

Traditional smart contracts can compare hashes, IDs, fields and timestamps, but cannot safely determine that two differently worded autonomous requests mean the same economic/protocol side effect. Once uses GenLayer only for that semantic boundary and keeps every enforceable consequence deterministic.

## Consensus boundary

The leader classifies one new description against a deterministic bounded candidate set as:

- `SAME_EFFECT` + an existing candidate ID;
- `NEW_EFFECT`;
- `AMBIGUOUS`.

Validators independently rerun the classification. The relation and selected candidate ID must match. Unknown candidate IDs are rejected by code.

## Deterministic state design

The contract enforces:

- immutable sealed profiles;
- exact requester partitioning;
- exact deterministic scope partitioning;
- bounded live candidate sets with fail-closed overflow;
- immutable canonical action hash;
- expiry window;
- revocation;
- profile/consumer binding;
- immutable effect and request hashes.

The LLM cannot change any of those.

## Reuse proof

`OnceProtectedExecutor` calls `Once.is_executable(...)` through a typed IC interface and performs a real state transition only when profile hash, canonical action hash, requester and consumer all match. The executor also rejects replay locally.

## High-signal lifecycle

Target live evidence on stable Studionet chain 61999:

1. finalized Once deployment;
2. finalized consumer deployment;
3. profile created and sealed;
4. first request -> `NEW_EFFECT`;
5. paraphrased retry with different action hash -> `SAME_EFFECT` and same effect ID;
6. effect still holds first action hash;
7. alternative retry action hash rejected by consumer;
8. original action hash accepted;
9. second execution rejected as replay.

## Reviewer-facing invariant

> Semantic equivalence can collapse retries, but it can never authorize new execution bytes.

That invariant is the core of the primitive.

## Live evidence — Studionet chain 61999

All transactions are **FINALIZED** on stable GenLayer Studionet, chain ID
`61999`, RPC `https://studio.genlayer.com/api`.

- `Once` deployment: `0xc686051637969ecb981666078209ac7b7e120629acfbcaff23a4a84b18370a87`
  → address `0xf25F26d356FD4aeccACF01A9bFbE7ea84a10dD70`
- `OnceProtectedExecutor` deployment: `0x53f420674b1ca2ab15226460a95ee73d03264b915825a5974a3a34b1fd644a1f`
  → address `0x0D97c40E422A865dD9E59824446d0A3C33400109`
- Profile create: `0x1fc0a579534f18ac03b316c8c7302117323e023ae98ccb6ab22f3dca61a1a3a2`
- Profile seal: `0xed78ecf6111998195470cdebe0fb2024649090a8d1c119cc7ab63cd792b555d7`
- Profile id `3`, `definition_hash`
  `09a29293ad55b4b66c5f6a6d5891b5910da430c6eb8f2507bec4c3e47f282050`
- First attempt (`NEW_EFFECT`, effect #2, canonical action hash `11…11`):
  `0x66ac416a1f2a294066a14d4647a507525067e8d2676e459d4d89d27225d32358`
- Semantic retry (`SAME_EFFECT`, same effect #2, alternative action hash
  `22…22`, canonical hash unchanged):
  `0x5f5ab1be0c99bf49549f9a41ab8837ccfda88834e95b8e556c8986f5ca130c73`
- Executor rejects alternative payload (`EXPECTED: Once permit is not
  executable`):
  `0x90a51a068036a71ff97dc3d5c7bfbe21e9a58440844a03642ef592d84426923a`
- Executor accepts canonical payload once:
  `0xe4a1ba3bdeccdf0f4992c2414fa2a87ad9b1492653b9592fcd3151424f733a74`
- Executor rejects replay (`EXPECTED: effect already consumed`):
  `0x1c276d4183900a2e45f39ab8b547572e09f9161b6db947d39f6dd247d50a7c64`

Validator consensus for the semantic retry recorded five validators with
`MAJORITY_AGREE` (`AGREE`/`IDLE` split reported on-chain). The reviewer
demo target listed above is therefore fully proven on-chain.

The same evidence in machine-readable form is in `deployments/studionet.json`.
