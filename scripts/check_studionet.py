"""Fail fast unless the configured RPC is stable Studionet chain 61999."""

import json
import os
import sys
import urllib.request

RPC = os.environ.get("GENLAYER_RPC", "https://studio.genlayer.com/api")
EXPECTED = 61999

payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []}).encode()
req = urllib.request.Request(
    RPC,
    data=payload,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "once-studionet-preflight/1.0",
    },
)
try:
    with urllib.request.urlopen(req, timeout=20) as response:
        body = json.loads(response.read().decode())
except Exception as exc:
    print(f"RPC check failed: {exc}", file=sys.stderr)
    raise SystemExit(2)

raw = body.get("result")
if not isinstance(raw, str):
    print(f"RPC returned no chain id: {body}", file=sys.stderr)
    raise SystemExit(2)
chain_id = int(raw, 16)
if chain_id != EXPECTED:
    print(f"Refusing to continue: expected chain {EXPECTED}, RPC reports {chain_id}", file=sys.stderr)
    raise SystemExit(3)
print(f"OK: {RPC} reports stable Studionet chain {chain_id}")
