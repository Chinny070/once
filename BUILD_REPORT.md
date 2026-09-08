# Build report

Final state of the `Chinny070/once` repository — a standalone reusable
GenLayer Intelligent Contract primitive with no frontend, targeted at
stable Studionet chain id `61999` and RPC `https://studio.genlayer.com/api`.

## Contract surface

- `contracts/once.py` — reusable primitive. Ten public methods
  (`create_profile`, `seal_profile`, `submit_attempt`, `revoke_effect`,
  `expire_effect`, plus `get_profile`, `get_effect`, `get_attempt`,
  `current_profile_hash`, `is_executable`).
- `contracts/protected_executor.py` — minimal consumer proving
  IC-to-IC reuse. Three methods (`execute`, `is_consumed`,
  `get_receipt`).
- Semantic validator independently re-runs classification; `SAME_EFFECT`
  requires matching verdict + candidate id against the deterministic
  bounded candidate set.
- Requester and deterministic scope filtering happen before consensus;
  bounded candidate overflow fails closed.
- Immutable canonical action-hash binding; exact-text retry fast path
  bypasses consensus deterministically.
- Consumer/profile binding via `definition_hash`; revocation, expiry,
  and consumer-local replay guard enforced deterministically.

## Test surface

- `tests/direct/test_once.py` — 27 direct-mode cases.
- `tests/integration/test_once_studionet.py` — one Studionet lifecycle
  test resolving contract paths from the repository root; asserts each
  write succeeds, reaches `FINALIZED`, and matches a canonical read.
- `tests/` deliberately contains no `gl.Contract` subclass and no
  py-genlayer runner header — enforced by
  `scripts/preflight.py` so a repository-wide validator cannot
  mis-detect a test file as a deployable contract.

## Verifier / gate surface

- `scripts/preflight.py` — required files present, syntactic compile,
  forbidden preview-chain id absent from any file, no rogue deployable
  files outside `contracts/`.
- `scripts/check_studionet.py` — refuses any RPC not reporting chain
  `61999`; sends a `User-Agent` so Cloudflare-fronted RPCs answer.
- `scripts/verify_live_evidence.py` — 30 machine-readable checks
  against Studionet, confirming chain id, tx finality, expected
  execution result per tx, deployment addresses, and that the deployed
  bodies still declare `class Once` / `class OnceProtectedExecutor`.
- `scripts/verify_all.py` — one command that runs Python compilation,
  preflight, GenVM lint, direct suite, integration collection, chain
  guard, and live-evidence verifier. Exits nonzero on any failure. Set
  `ONCE_SKIP_LIVE=1` to skip the two live steps for air-gapped CI.
- `.github/workflows/ci.yml` — a `verify` job that runs the offline
  gates on every push/PR to `main` (Python compilation, static
  preflight, GenVM AST lint of both contracts, direct-suite pytest
  collection, integration-suite pytest collection), plus a
  `verify-live` job that runs the Studionet chain-id guard and the
  live-evidence verifier on pushes to `main`. Steps that need the 128 MB
  GenVM release bundle (full `genvm-lint check`, runtime execution of
  the direct-mode suite) run locally against `scripts/verify_all.py`;
  their output is captured verbatim below.

## Pinned toolchain (captured in `requirements-dev.txt`)

- `genlayer-test==0.29.2`
- `genvm-linter==0.10.0`
- `pytest==9.1.1`
- Python `3.12`
- Contract runner: `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`
  (pinned in the `Depends` header of both contracts).

## Local verification (captured output)

```text
$ python scripts/preflight.py
PREFLIGHT PASS
checked 8 required artifacts
target chain: 61999

$ python scripts/check_studionet.py
OK: https://studio.genlayer.com/api reports stable Studionet chain 61999

$ genvm-lint check contracts/once.py
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: Once
  Methods: 10 (5 view, 5 write)

$ genvm-lint check contracts/protected_executor.py
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: OnceProtectedExecutor
  Methods: 3 (2 view, 1 write)

$ pytest tests/direct -q
...........................                                              [100%]
27 passed

$ pytest tests/integration --collect-only -q
tests/integration/test_once_studionet.py: 1

$ python scripts/verify_live_evidence.py
OK — 30 live-evidence checks passed

$ python scripts/verify_all.py
8 step(s) passed. Repository is verifiable end-to-end.
```

## Finalized on Studionet chain 61999

- `Once` at `0xf25F26d356FD4aeccACF01A9bFbE7ea84a10dD70`
- `OnceProtectedExecutor` at `0x0D97c40E422A865dD9E59824446d0A3C33400109`
- Reviewer profile id `3`, `definition_hash`
  `09a29293ad55b4b66c5f6a6d5891b5910da430c6eb8f2507bec4c3e47f282050`
- All nine lifecycle transactions (deploy Once, deploy executor,
  create_profile, seal_profile, first submit, semantic retry, alt
  payload rejection, canonical execution, replay rejection) reached
  `FINALIZED` — see `deployments/studionet.json` for the full list of
  transaction hashes in machine-readable form.
