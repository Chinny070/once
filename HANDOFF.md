# Chinny agent handoff

This package is the source-complete Once implementation prepared for `Chinny070/once`.

The original ChatGPT connection could read the repository but could not push to it because the connected GitHub account had no write permission. Do not rebuild the idea from scratch. Audit and finish this package.

## Non-negotiable target

- stable GenLayer Studionet
- chain ID **61999**
- RPC `https://studio.genlayer.com/api`
- no frontend
- repository category: standalone reusable Intelligent Contract

## Your job

1. Unzip this package and open the `once/` directory.
2. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, and `SUBMISSION.md` before changing the protocol.
3. Install the current stable GenLayer tooling compatible with Studionet.
4. Run:
   - `python scripts/check_studionet.py`
   - `python scripts/preflight.py`
   - `genvm-lint check contracts/once.py`
   - `genvm-lint check contracts/protected_executor.py`
   - `pytest tests/direct -q`
5. Fix any SDK/linter/runtime incompatibility you find without weakening these invariants:
   - semantic duplicates reuse an existing effect ID;
   - `AMBIGUOUS` creates no permit;
   - deterministic requester + scope filtering happens before consensus;
   - candidate overflow fails closed;
   - a duplicate retry can never overwrite `canonical_action_hash`;
   - profile hash binds the consumer;
   - revocation/expiry block execution;
   - consumer rejects replay.
6. Deploy `Once` on chain 61999 and wait for finalization.
7. Deploy `OnceProtectedExecutor` with the finalized Once address and wait for finalization.
8. Create/seal the demo profile using the finalized executor address.
9. Run the semantic retry lifecycle in `DEPLOYMENT.md` and the integration test.
10. Capture real finalized transaction hashes and addresses. Never invent evidence.
11. Update `deployments/studionet.json`, `README.md`, and `SUBMISSION.md` with the real evidence.
12. Run the whole preflight/test suite again after documentation updates.
13. Push the finished repository to `https://github.com/Chinny070/once` on `main`.
14. Return a concise final report with:
    - final commit SHA;
    - Once address;
    - executor address;
    - deployment hashes;
    - semantic retry hash;
    - canonical execution hash;
    - replay-rejection hash;
    - test counts;
    - any remaining honest limitations.

## Do not add

- a frontend;
- fake deployment evidence;
- another chain configuration;
- payment/escrow logic just to make the repo larger;
- model-generated action payloads;
- an LLM decision over deterministic hashes, requester identity, expiry, or replay state.

The goal is a sharp primitive, not a product.
