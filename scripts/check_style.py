"""Concision, dependency, and privacy hygiene gate (D-38, D-43)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import ast
import re
import subprocess

from core.paths import ROOT

LENGTH_LIMITS = {"core": (250, 40), "api": (250, 40), "scripts": (250, 40), "tests": (350, 60)}
FORBIDDEN_IMPORTS = {
    "pandas", "numpy", "sentence_transformers", "torch",
    "sklearn", "requests", "httpx", "flask", "fastapi", "django",
}
ALLOWED_REQUIREMENTS = {"anthropic", "pydantic", "rapidfuzz"}
TEXT_EXTENSIONS = {".py", ".md", ".js", ".html", ".css", ".json", ".txt", ".ini", ".toml"}
HOME_PATH_PATTERN = re.compile("/" + "Users/" + r"[^/\s]+/")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)
HOURS_PATTERN = re.compile(r"\b\d+(\.\d+)?\s?(h|hrs|hours)\b", re.I)
HOURS_ALLOWLIST: set[str] = set()


def _shipped_files() -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if line]


def _check_lengths() -> list[str]:
    failures = []
    for top, (max_file, max_func) in LENGTH_LIMITS.items():
        for path in sorted((ROOT / top).rglob("*.py")):
            failures.extend(_check_one_file_length(path, max_file, max_func))
    return failures


def _check_one_file_length(path: pathlib.Path, max_file: int, max_func: int) -> list[str]:
    source = path.read_text()
    rel = path.relative_to(ROOT)
    failures = []
    n_lines = len(source.splitlines())
    if n_lines > max_file:
        failures.append(f"{rel}: {n_lines} lines > {max_file}")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if length > max_func:
                failures.append(f"{rel}:{node.name} {length} lines > {max_func}")
    return failures


def _check_imports() -> list[str]:
    failures = []
    for top in ("core", "api"):
        for path in sorted((ROOT / top).rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                failures.extend(_forbidden_names_in_node(node, path))
    return failures


def _forbidden_names_in_node(node: ast.AST, path: pathlib.Path) -> list[str]:
    names = []
    if isinstance(node, ast.Import):
        names = [a.name.split(".")[0] for a in node.names]
    elif isinstance(node, ast.ImportFrom) and node.module:
        names = [node.module.split(".")[0]]
    rel = path.relative_to(ROOT)
    return [f"{rel}: forbidden import {n}" for n in names if n in FORBIDDEN_IMPORTS]


def _check_requirements() -> list[str]:
    failures = []
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        name = re.split(r"[=<>~\[]", line, maxsplit=1)[0].strip()
        if name not in ALLOWED_REQUIREMENTS:
            failures.append(f"requirements.txt: {name} not in {sorted(ALLOWED_REQUIREMENTS)}")
    return failures


def _forbidden_terms() -> list[str]:
    path = ROOT / "private" / "forbidden_terms.txt"
    if not path.exists():
        print("NOTICE: private/forbidden_terms.txt is absent - forbidden-terms check skipped")
        return []
    return [t.strip().casefold() for t in path.read_text().splitlines() if t.strip()]


def _check_text_files(files: list[pathlib.Path]) -> list[str]:
    failures = []
    terms = _forbidden_terms()
    for path in files:
        if path.suffix not in TEXT_EXTENSIONS or not path.exists():
            continue
        failures.extend(_check_one_text_file(path, terms))
    return failures


def _check_one_text_file(path: pathlib.Path, terms: list[str]) -> list[str]:
    text = path.read_text(errors="ignore")
    rel = path.relative_to(ROOT)
    failures = []
    if HOME_PATH_PATTERN.search(text):
        failures.append(f"{rel}: absolute home-directory path")
    if EMAIL_PATTERN.search(text):
        failures.append(f"{rel}: email address pattern")
    for m in HOURS_PATTERN.finditer(text):
        if m.group(0).strip().casefold() not in HOURS_ALLOWLIST:
            failures.append(f"{rel}: hours phrase '{m.group(0)}'")
    lowered = text.casefold()
    for term in terms:
        if term in lowered:
            failures.append(f"{rel}: forbidden term '{term}'")
    return failures


def main() -> None:
    files = _shipped_files()
    checks = {
        "lengths (file/function)": _check_lengths(),
        "imports (core/api forbidden deps)": _check_imports(),
        "requirements.txt allowlist": _check_requirements(),
        "text (paths/emails/hours/forbidden terms)": _check_text_files(files),
    }
    failed = False
    for name, failures in checks.items():
        if failures:
            failed = True
            print(f"FAIL {name}: {len(failures)} issue(s)")
            for f in failures:
                print(f"  - {f}")
        else:
            print(f"PASS {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
