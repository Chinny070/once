"""Machine-readable verifier for the live evidence recorded in
``deployments/studionet.json``.

For a clean-checkout reviewer, this script hits the Studionet RPC directly
and confirms:

* the RPC really reports chain id ``61999``;
* every documented transaction is `FINALIZED` on-chain;
* every write-transaction that was supposed to succeed reports
  ``execution_result == "SUCCESS"``, and every write that was supposed to
  revert reports ``execution_result == "ERROR"``;
* the deploy transactions actually created the addresses recorded in
  ``studionet.json``;
* the deployed contract bodies still declare the two expected contract
  classes (``Once`` and ``OnceProtectedExecutor``).

Runs with only the Python standard library so it can be invoked from any
clean checkout with no dependencies installed.

Usage::

    python scripts/verify_live_evidence.py

Exit code is nonzero on any mismatch. All findings are printed as
one-line ``PASS``/``FAIL`` records so a reviewer or CI can diff them.
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "deployments" / "studionet.json"
EXPECTED_CHAIN_ID = 61999


def _rpc(url: str, method: str, params: list) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "once-live-evidence-verifier/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


class Verifier:
    def __init__(self, evidence: dict):
        self.evidence = evidence
        self.rpc = evidence["rpc"]
        self.expected_chain_id = int(evidence["chain_id"])
        self.failures: list[str] = []
        self.checks = 0

    def _pass(self, label: str) -> None:
        self.checks += 1
        print(f"PASS  {label}")

    def _fail(self, label: str, detail: str = "") -> None:
        self.checks += 1
        msg = f"FAIL  {label}"
        if detail:
            msg += f" -- {detail}"
        self.failures.append(msg)
        print(msg)

    def check_chain_id(self) -> None:
        if self.expected_chain_id != EXPECTED_CHAIN_ID:
            self._fail(
                "studionet.json declares expected chain id",
                f"got {self.expected_chain_id}, want {EXPECTED_CHAIN_ID}",
            )
            return
        try:
            resp = _rpc(self.rpc, "eth_chainId", [])
        except urllib.error.URLError as exc:
            self._fail("RPC eth_chainId reachable", str(exc))
            return
        result = resp.get("result")
        if not isinstance(result, str):
            self._fail("RPC eth_chainId returns hex string", repr(resp))
            return
        got = int(result, 16)
        if got != EXPECTED_CHAIN_ID:
            self._fail(
                f"RPC {self.rpc} reports chain {EXPECTED_CHAIN_ID}",
                f"reports {got} instead",
            )
        else:
            self._pass(f"RPC {self.rpc} reports chain {EXPECTED_CHAIN_ID}")

    def _get_tx(self, tx_hash: str) -> dict | None:
        try:
            resp = _rpc(self.rpc, "eth_getTransactionByHash", [tx_hash])
        except urllib.error.URLError as exc:
            self._fail(f"RPC lookup {tx_hash}", str(exc))
            return None
        result = resp.get("result")
        if not isinstance(result, dict):
            self._fail(f"tx {tx_hash} returns object", repr(resp)[:200])
            return None
        return result

    def _execution_result(self, tx: dict) -> str | None:
        cd = tx.get("consensus_data")
        if not isinstance(cd, dict):
            return None
        lr = cd.get("leader_receipt")
        if not isinstance(lr, list) or not lr:
            return None
        first = lr[0]
        if not isinstance(first, dict):
            return None
        value = first.get("execution_result")
        return value if isinstance(value, str) else None

    def check_tx_finalized(
        self,
        label: str,
        tx_hash: str,
        expect_success: bool,
        expect_to: str | None = None,
    ) -> dict | None:
        tx = self._get_tx(tx_hash)
        if tx is None:
            return None
        status = tx.get("status")
        if status != "FINALIZED":
            self._fail(f"{label} FINALIZED", f"status={status!r} for {tx_hash}")
        else:
            self._pass(f"{label} FINALIZED ({tx_hash})")

        exec_result = self._execution_result(tx)
        if expect_success:
            if exec_result != "SUCCESS":
                self._fail(f"{label} execution SUCCESS", f"got {exec_result!r}")
            else:
                self._pass(f"{label} execution SUCCESS")
        else:
            if exec_result != "ERROR":
                self._fail(f"{label} execution ERROR (revert)", f"got {exec_result!r}")
            else:
                self._pass(f"{label} execution ERROR (revert)")

        if expect_to is not None:
            got_to = str(tx.get("to_address", "")).lower()
            want_to = expect_to.lower()
            if got_to != want_to:
                self._fail(f"{label} to_address matches", f"got {got_to}, want {want_to}")
            else:
                self._pass(f"{label} to_address matches {expect_to}")
        return tx

    def check_deploy_body(self, label: str, tx: dict | None, must_contain: str) -> None:
        if tx is None:
            return
        data = tx.get("data")
        if not isinstance(data, dict):
            self._fail(f"{label} embeds contract code", "tx.data missing")
            return
        code_b64 = data.get("contract_code")
        if not isinstance(code_b64, str) or not code_b64:
            self._fail(f"{label} embeds contract code", "contract_code missing")
            return
        try:
            code = base64.b64decode(code_b64).decode("utf-8", errors="replace")
        except Exception as exc:
            self._fail(f"{label} contract code decodes", str(exc))
            return
        if must_contain not in code:
            self._fail(
                f"{label} deployed body contains `{must_contain}`",
                "class marker missing from decoded source",
            )
        else:
            self._pass(f"{label} deployed body contains `{must_contain}`")

    def run(self) -> int:
        self.check_chain_id()

        once_addr = self.evidence["once_address"]
        exec_addr = self.evidence["protected_executor_address"]

        deploy_specs = [
            ("Once deploy",       self.evidence["once_deploy_tx"],                 True,  once_addr, "class Once"),
            ("Executor deploy",   self.evidence["protected_executor_deploy_tx"],   True,  exec_addr, "class OnceProtectedExecutor"),
        ]
        for label, tx_hash, ok, addr, needle in deploy_specs:
            tx = self.check_tx_finalized(label, tx_hash, expect_success=ok, expect_to=addr)
            self.check_deploy_body(label, tx, needle)

        state_specs = [
            ("create_profile",             self.evidence["profile_create_tx"],             True,  once_addr),
            ("seal_profile",               self.evidence["profile_seal_tx"],               True,  once_addr),
            ("first submit_attempt",       self.evidence["first_attempt_tx"],              True,  once_addr),
            ("semantic retry",             self.evidence["semantic_retry_tx"],             True,  once_addr),
            ("executor rejects alt hash",  self.evidence["alternative_payload_rejection_tx"], False, exec_addr),
            ("executor accepts canonical", self.evidence["canonical_execution_tx"],        True,  exec_addr),
            ("executor rejects replay",    self.evidence["replay_rejection_tx"],           False, exec_addr),
        ]
        for label, tx_hash, ok, addr in state_specs:
            self.check_tx_finalized(label, tx_hash, expect_success=ok, expect_to=addr)

        print()
        if self.failures:
            print(f"{len(self.failures)} FAILURE(S) out of {self.checks} checks:")
            for msg in self.failures:
                print(f"  {msg}")
            return 1
        print(f"OK — {self.checks} live-evidence checks passed")
        return 0


def main() -> int:
    if not EVIDENCE.exists():
        print(f"missing evidence file: {EVIDENCE}", file=sys.stderr)
        return 2
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    return Verifier(evidence).run()


if __name__ == "__main__":
    raise SystemExit(main())
