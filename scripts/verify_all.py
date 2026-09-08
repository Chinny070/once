"""End-to-end verification for a clean checkout of Once.

Runs every gate the CI enforces, in the order a reviewer would:

  1. Every Python file under contracts/, scripts/, and tests/ compiles.
  2. Static preflight (scripts/preflight.py).
  3. GenVM lint + validation for both contracts.
  4. Direct-mode test suite (pytest tests/direct -q).
  5. Integration-test collection (pytest --collect-only) — proves the
     Studionet lifecycle test is importable and enumerable even when no
     Studionet key is configured.
  6. Live-evidence verifier — hits Studionet RPC (skipped when
     ``ONCE_SKIP_LIVE=1`` is set, e.g. an air-gapped CI).
  7. Studionet chain-id guard (skipped when the live check was skipped).

Exits nonzero on any failure. All step boundaries are printed so a CI log
is easy to scan.
"""

from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run(label: str, cmd: list[str], env: dict | None = None) -> bool:
    print(f"\n===> {label}")
    print("  $ " + " ".join(cmd))
    proc_env = os.environ.copy()
    # Force UTF-8 so Windows cp1252 does not blow up on the linter's OK.
    proc_env.setdefault("PYTHONIOENCODING", "utf-8")
    proc_env.setdefault("PYTHONUTF8", "1")
    if env:
        proc_env.update(env)
    result = subprocess.run(cmd, cwd=ROOT, env=proc_env)
    if result.returncode != 0:
        print(f"  !! FAIL ({label}) exit={result.returncode}")
        return False
    print(f"  OK OK ({label})")
    return True


def _compile_all() -> bool:
    print("\n===> Python compilation of contracts/, scripts/, tests/")
    ok = True
    for base in ("contracts", "scripts", "tests"):
        for path in (ROOT / base).rglob("*.py"):
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                print(f"  !! {path.relative_to(ROOT)}: {exc.msg}")
                ok = False
    if ok:
        print("  OK OK (Python compilation)")
    return ok


def main() -> int:
    steps: list[tuple[str, bool]] = []

    steps.append(("Python compilation", _compile_all()))
    steps.append(("preflight",
                  _run("preflight", [PYTHON, "scripts/preflight.py"])))
    steps.append(("genvm-lint once.py",
                  _run("genvm-lint once.py",
                       [PYTHON, "-m", "genvm_linter.cli", "check", "contracts/once.py"])))
    steps.append(("genvm-lint protected_executor.py",
                  _run("genvm-lint protected_executor.py",
                       [PYTHON, "-m", "genvm_linter.cli", "check", "contracts/protected_executor.py"])))
    steps.append(("direct tests",
                  _run("direct tests", [PYTHON, "-m", "pytest", "tests/direct", "-q"])))
    steps.append(("integration collect",
                  _run("integration collect",
                       [PYTHON, "-m", "pytest", "tests/integration", "--collect-only", "-q"])))

    if os.environ.get("ONCE_SKIP_LIVE") == "1":
        print("\n===> Live-evidence + chain check skipped (ONCE_SKIP_LIVE=1)")
    else:
        steps.append(("Studionet chain guard",
                      _run("Studionet chain guard",
                           [PYTHON, "scripts/check_studionet.py"])))
        steps.append(("live evidence verifier",
                      _run("live evidence verifier",
                           [PYTHON, "scripts/verify_live_evidence.py"])))

    print("\n===> Summary")
    failed = [name for name, ok in steps if not ok]
    for name, ok in steps:
        marker = "OK  " if ok else "FAIL"
        print(f"  {marker}  {name}")
    if failed:
        print(f"\n{len(failed)} step(s) failed: {', '.join(failed)}")
        return 1
    print(f"\n{len(steps)} step(s) passed. Repository is verifiable end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
