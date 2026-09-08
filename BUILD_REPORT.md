# Build report

Prepared in this chat as a source-complete handoff for `Chinny070/once`.

## Completed here

- standalone Once Intelligent Contract implemented;
- typed `IOnce` reusable IC interface included;
- minimal `OnceProtectedExecutor` consumer implemented;
- semantic validator re-executes classification independently;
- `SAME_EFFECT`, `NEW_EFFECT`, and fail-closed `AMBIGUOUS` paths implemented;
- requester and deterministic scope isolation implemented before consensus;
- exact-text retry fast path implemented;
- immutable canonical action-hash binding implemented;
- consumer/profile binding implemented;
- revocation and expiry implemented;
- consumer-local replay guard implemented;
- 14 direct-mode test cases authored;
- stable Studionet lifecycle test authored;
- network guard targets chain 61999;
- deployment/submission/threat-model/architecture docs authored;
- static preflight passes;
- all Python files compile syntactically in the build environment;
- repository contains no frontend.

## Finalized on Studionet chain 61999

- `Once` at `0xf25F26d356FD4aeccACF01A9bFbE7ea84a10dD70`
- `OnceProtectedExecutor` at `0x0D97c40E422A865dD9E59824446d0A3C33400109`
- Reviewer profile id 3, `definition_hash`
  `09a29293ad55b4b66c5f6a6d5891b5910da430c6eb8f2507bec4c3e47f282050`
- Full lifecycle proven — first attempt is `NEW_EFFECT` (effect #2);
  differently worded retry with a different payload hash is
  `SAME_EFFECT` mapped to effect #2 while the canonical action hash
  stayed `11…11`; executor refused the alternative payload, accepted
  the canonical payload once, and refused the replay.
- All nine lifecycle transactions are `FINALIZED` — see
  `deployments/studionet.json` and `SUBMISSION.md` for hashes.

The lint suite (`genvm-lint check contracts/*.py`), preflight
(`scripts/preflight.py`), Studionet chain-id guard
(`scripts/check_studionet.py`), and 23-case Direct Mode suite
(`pytest tests/direct -q`) all pass locally.
