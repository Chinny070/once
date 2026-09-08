from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "contracts" / "once.py",
    ROOT / "contracts" / "protected_executor.py",
    ROOT / "tests" / "direct" / "test_once.py",
    ROOT / "tests" / "integration" / "test_once_studionet.py",
    ROOT / "README.md",
    ROOT / "SUBMISSION.md",
    ROOT / "DEPLOYMENT.md",
    ROOT / "docs" / "THREAT_MODEL.md",
]
errors = []
for path in required:
    if not path.exists():
        errors.append(f"missing {path.relative_to(ROOT)}")

# Constructed at runtime so this scanner file itself does not match its own scan.
DEPLOYABLE_HEADER = "".join(['# { "', "Depends", '":'])
GL_CONTRACT_MARKER = "gl" + "." + "Contract"

# The deployable set is EXACTLY these two files. Anything else with a py-genlayer
# runner header or a contract-class marker elsewhere in the tree would confuse
# a repository-wide validator and must not exist.
allowed_contracts = {
    (ROOT / "contracts" / "once.py").resolve(),
    (ROOT / "contracts" / "protected_executor.py").resolve(),
}

for path in (ROOT / "contracts").glob("*.py"):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        errors.append(f"syntax {path.name}: {exc}")

# Repository-wide scans (skip caches / virtualenvs / build artifacts).
IGNORED_DIR_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".cache",
    "artifacts",
    "node_modules",
}

def _iter_project_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_PARTS for part in path.relative_to(ROOT).parts):
            continue
        yield path


# 1. Refuse any forbidden preview-chain id anywhere in the repository.
for path in _iter_project_files():
    if path.suffix not in {".py", ".md", ".yaml", ".yml", ".example", ".txt", ".json"}:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    forbidden = "619" + "97"
    if forbidden in text:
        errors.append(f"forbidden preview-chain reference in {path.relative_to(ROOT)}")


# 2. Refuse any deployable-shaped file outside the two known contract files.
#    A repository-wide validator that greps for the runner header or for the
#    marker string must find only once.py and protected_executor.py.
for path in _iter_project_files():
    if path.suffix != ".py":
        continue
    resolved = path.resolve()
    if resolved in allowed_contracts:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    if DEPLOYABLE_HEADER in text:
        errors.append(
            f"non-contract file has deployable runner header: {path.relative_to(ROOT)}"
        )
    if GL_CONTRACT_MARKER in text:
        errors.append(
            f"non-contract file references {GL_CONTRACT_MARKER}: {path.relative_to(ROOT)}"
        )

main = (ROOT / "contracts" / "once.py").read_text(encoding="utf-8") if (ROOT / "contracts" / "once.py").exists() else ""
for needle in (
    "run_nondet_unsafe",
    "validator_fn",
    "SAME_EFFECT",
    "NEW_EFFECT",
    "AMBIGUOUS",
    "is_executable",
    "definition_hash",
    "canonical_action_hash",
):
    if needle not in main:
        errors.append(f"main contract missing expected mechanism: {needle}")

if errors:
    print("PREFLIGHT FAILED")
    for err in errors:
        print("-", err)
    raise SystemExit(1)

print("PREFLIGHT PASS")
print(f"checked {len(required)} required artifacts")
print("target chain: 61999")
