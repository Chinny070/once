# Architecture notes

## Why semantic idempotency is not ordinary deduplication

Byte-level idempotency treats two payloads as identical only when an exact identifier matches. Agent systems routinely regenerate text and structured payloads during retries. Once preserves hard deterministic dimensions and delegates only the residual semantic-equivalence question to consensus.

## Two-key model

Every admitted effect has two kinds of identity:

1. **Semantic identity:** profile + requester + scope + canonical description.
2. **Execution identity:** immutable `canonical_action_hash` consumed by the registered contract.

The second never changes when the first is matched by a retry.

## Why the first request does not call an LLM

There is nothing to compare. A first request in an empty requester/scope domain is deterministically new. Consensus begins only when at least one live candidate exists.

## Why exact text retries do not call an LLM

Exact canonical text already proves equivalence under the same requester and scope. Skipping consensus reduces cost and removes unnecessary nondeterminism.

## Why candidate action hashes are not shown to the LLM

Hashes carry no semantic information. Including them could bias the model toward treating byte differences as semantic differences. The protocol intentionally separates semantic classification from exact execution commitment.

## Why a registered consumer is part of the profile hash

A permit should not become portable to an arbitrary downstream contract. Binding a consumer makes the reuse boundary explicit and prevents a permit created for one executor from being interpreted as approval for another.

## Why duplicates of revoked effects do not mint fresh effects

Revocation should not be bypassed by paraphrasing the same request. Until the idempotency window closes, equivalent retries continue to resolve to the revoked effect. After the window, a fresh request may become a new effect.

## Composition

A production consumer can combine Once with authorization, escrow, SLA, or settlement primitives:

```text
authority check
      |
      v
Once idempotency permit
      |
      v
application-specific execution
      |
      v
consumer-local consumed marker
```

Each component owns one narrow security property.
