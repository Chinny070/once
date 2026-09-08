# Once threat model

## Security objective

For one sealed operation profile, requester, deterministic scope, and idempotency window, semantically equivalent retries must not obtain multiple independently executable side-effect permits.

## Trust boundary

Consensus decides only semantic equivalence between a new natural-language request and a bounded set of live canonical descriptions. Deterministic code owns profile immutability, candidate domain filtering, action-hash binding, expiry, revocation, and consumer checks.

## Threats and mitigations

### Paraphrase replay

**Threat:** the same action is restated with different words to bypass byte-level idempotency.

**Mitigation:** independent GenLayer semantic classification can map the attempt to the existing effect ID.

### Payload substitution

**Threat:** a retry looks semantically equivalent but carries a different low-level payload.

**Mitigation:** a `SAME_EFFECT` result never changes `canonical_action_hash`. Consumers check the original hash exactly.

### Cross-user collision

**Threat:** one user's request suppresses another user's legitimate action.

**Mitigation:** candidate selection is partitioned by `requester` before semantic consensus.

### Scope confusion

**Threat:** unrelated resources are compared because semantic language is broad.

**Mitigation:** exact `scope_key` equality is required before an effect enters the semantic candidate set.

### Candidate omission

**Threat:** a bounded candidate limit silently omits a duplicate and creates another permit.

**Mitigation:** Once rejects the submission if one requester/scope has more than the allowed live candidate count. It never truncates silently.

### Malicious or faulty leader invents a match

**Threat:** leader returns an effect ID that was not offered.

**Mitigation:** output-shape validation requires `SAME_EFFECT.effect_id` to be an exact member of the deterministic candidate set. Validators independently classify the same bounded data.

### Ambiguous equivalence

**Threat:** uncertain descriptions are forced into either duplicate or new.

**Mitigation:** `AMBIGUOUS` is a first-class terminal attempt outcome and creates no effect.

### Revoked permit replay

**Threat:** an already cancelled effect is later executed.

**Mitigation:** `is_executable` requires `ISSUED`; revocation changes status. Semantic retries during the original window still map to the revoked effect instead of minting a replacement.

### Expired permit replay

**Threat:** an old effect is executed outside its configured idempotency window.

**Mitigation:** `is_executable` checks the transaction timestamp against `expires_at`; `expire_effect` can also materialize `EXPIRED` state.

### Wrong consumer

**Threat:** the same permit is presented to another contract.

**Mitigation:** profile hash commits to one consumer address and `is_executable` checks it exactly.

### Consumer replay

**Threat:** a valid canonical permit is submitted twice to the intended consumer.

**Mitigation:** the reference `OnceProtectedExecutor` keeps a consumed-effect map and rejects the second execution. Real consumers must implement equivalent idempotent consumption.

### Prompt-control strings

**Threat:** request/rule text tries to become instructions to the model.

**Mitigation:** prompts label all dynamic text as untrusted data, known control-like phrases are rejected at registration/submission boundaries, and the model has no tools/action authority.

## Explicit limitations

- Once does not observe whether a side effect actually occurred outside the consumer contract.
- The semantic rule is only as good as the profile owner's frozen definition.
- A compliant consumer must enforce one-time local consumption; Once cannot synchronously mutate itself from a view call.
- A caller must choose sufficiently narrow deterministic scope keys.
- The primitive is not an authorization system. A caller can be authorized and still submit a duplicate; Once solves duplication, not authority.
