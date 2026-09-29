"""Drift between requirements.txt pins and pyproject.toml PEP 621 dependencies.

Compares ``[project].dependencies`` and ``[project.optional-dependencies]``
with ``requirements.txt``. Flags specs that cannot be satisfied together,
and packages present on only one side of the required set.
"""
from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(?P<spec>.*?)\s*$"
)
_SPEC_RE = re.compile(
    r"(?P<op>==|!=|<=|>=|~=|<|>)\s*(?P<ver>\d+(?:\.\d+)*)"
)
_QUOTED_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')


def normalize_name(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _cmp(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    a = left + (0,) * (width - len(left))
    b = right + (0,) * (width - len(right))
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def parse_specifiers(spec: str) -> list[tuple[str, tuple[int, ...]]]:
    """Parse a PEP 440 specifier set into (op, version) pairs."""
    spec = spec.split(";", 1)[0]
    spec = spec.split("--", 1)[0]
    return [
        (match.group("op"), _version_tuple(match.group("ver")))
        for match in _SPEC_RE.finditer(spec)
    ]


def _satisfies(version: tuple[int, ...], constraints: list[tuple[str, tuple[int, ...]]]) -> bool:
    for op, bound in constraints:
        cmp = _cmp(version, bound)
        if op == "==" and cmp != 0:
            return False
        if op == "!=" and cmp == 0:
            return False
        if op == ">=" and cmp < 0:
            return False
        if op == ">" and cmp <= 0:
            return False
        if op == "<=" and cmp > 0:
            return False
        if op == "<" and cmp >= 0:
            return False
        if op == "~=":
            if cmp < 0:
                return False
            # ~=1.2.3 → <1.3.0 ; ~=1.2 → <2.0
            if len(bound) >= 2:
                ceiling = bound[:-1]
                ceiling = ceiling[:-1] + (ceiling[-1] + 1,)
                if _cmp(version, ceiling) >= 0:
                    return False
    return True


def _lower_bound(constraints: list[tuple[str, tuple[int, ...]]]) -> tuple[int, ...] | None:
    for op, version in constraints:
        if op in {"==", ">=", ">", "~="}:
            return version
    return None


def _exact_pin(constraints: list[tuple[str, tuple[int, ...]]]) -> tuple[int, ...] | None:
    pins = [version for op, version in constraints if op == "=="]
    if len(pins) == 1 and all(op == "==" for op, _ in constraints):
        return pins[0]
    return None


def specs_conflict(left: str, right: str) -> bool:
    """Return True when two requirement specifiers cannot both be true."""
    left_c = parse_specifiers(left)
    right_c = parse_specifiers(right)
    if not left_c or not right_c:
        return False
    left_pin = _exact_pin(left_c)
    right_pin = _exact_pin(right_c)
    if left_pin is not None and not _satisfies(left_pin, right_c):
        return True
    if right_pin is not None and not _satisfies(right_pin, left_c):
        return True
    if left_pin is None and right_pin is None:
        left_floor = _lower_bound(left_c)
        right_floor = _lower_bound(right_c)
        if left_floor and right_floor and left_floor[0] != right_floor[0]:
            return True
    return False


def parse_requirements(text: str) -> dict[str, str]:
    """Return {normalized_name: specifier} from a requirements.txt body."""
    packages: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = _NAME_RE.match(line)
        if not match:
            continue
        name = normalize_name(match.group("name"))
        if name in {"pip", "setuptools", "wheel", "python"}:
            continue
        packages[name] = match.group("spec").strip()
    return packages


def _section_name(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped[1:-1].strip()
    return None


def _quoted_strings(text: str) -> list[str]:
    return [a or b for a, b in _QUOTED_RE.findall(text)]


def _store_requirements(target: dict[str, str], blob: str) -> None:
    for item in _quoted_strings(blob):
        match = _NAME_RE.match(item.strip())
        if not match:
            continue
        target[normalize_name(match.group("name"))] = match.group("spec").strip()


def parse_pyproject_dependencies(text: str) -> tuple[dict[str, str], dict[str, str], bool]:
    """Parse PEP 621 dependency tables.

    Returns:
        required packages, optional packages, and whether
        ``[project].dependencies`` was present.
    """
    required: dict[str, str] = {}
    optional: dict[str, str] = {}
    found_required = False
    section = ""
    capture: dict[str, str] | None = None
    buf: list[str] = []

    def _flush() -> None:
        nonlocal capture, buf
        if capture is None:
            return
        _store_requirements(capture, "\n".join(buf))
        capture = None
        buf = []

    for raw in text.splitlines():
        header = _section_name(raw)
        if header is not None:
            _flush()
            section = header
            continue
        stripped = raw.split("#", 1)[0].strip()
        if capture is not None:
            buf.append(stripped)
            if "]" in stripped:
                _flush()
            continue
        if section == "project" and stripped.startswith("dependencies"):
            found_required = True
            _, _, value = stripped.partition("=")
            value = value.strip()
            if "[" not in value:
                continue
            if "]" in value:
                _store_requirements(required, value)
            else:
                capture = required
                buf = [value]
            continue
        if section == "project.optional-dependencies" and "=" in stripped:
            _, _, value = stripped.partition("=")
            value = value.strip()
            if not value.startswith("["):
                continue
            if "]" in value:
                _store_requirements(optional, value)
            else:
                capture = optional
                buf = [value]
    _flush()
    return required, optional, found_required


def _expand_includes(text: str, root: Path | None, seen: set[str]) -> str:
    """Inline ``-r`` includes one level deep when ``root`` is provided."""
    if root is None:
        return text
    chunks = [text]
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        rel = ""
        if line.startswith("-r "):
            rel = line[3:].strip()
        elif line.startswith("--requirement "):
            rel = line.split(None, 1)[1].strip()
        if not rel or rel in seen:
            continue
        path = (root / rel).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        if not path.is_file():
            continue
        seen.add(rel)
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def find_python_req_drift(
    req_text: str,
    pyproject_text: str,
    root: Path | None = None,
) -> list[dict]:
    """Detect drift between requirements.txt and PEP 621 dependencies.

    Returns findings with ``file``, ``package``, ``detail``, and ``pos``.
    """
    if not req_text.strip():
        return []
    required, optional, found = parse_pyproject_dependencies(pyproject_text)
    if not found:
        return []

    reqs = parse_requirements(_expand_includes(req_text, root, set()))
    declared = {**optional, **required}
    drifts: list[dict] = []

    for name, req_spec in sorted(reqs.items()):
        if name not in declared:
            drifts.append({
                "file": "requirements.txt",
                "package": name,
                "requirements_spec": req_spec,
                "detail": (
                    f"{name} is in requirements.txt but missing from "
                    "pyproject.toml [project] dependencies"
                ),
                "pos": 0,
            })
            continue
        pp_spec = declared[name]
        if specs_conflict(req_spec, pp_spec):
            drifts.append({
                "file": "requirements.txt",
                "package": name,
                "requirements_spec": req_spec,
                "pyproject_spec": pp_spec,
                "detail": (
                    f"{name} is {req_spec or '(unspecified)'} in requirements.txt "
                    f"but {pp_spec or '(unspecified)'} in pyproject.toml"
                ),
                "pos": 0,
            })

    for name, pp_spec in sorted(required.items()):
        if name not in reqs:
            drifts.append({
                "file": "pyproject.toml",
                "package": name,
                "pyproject_spec": pp_spec,
                "detail": (
                    f"{name} is in pyproject.toml [project].dependencies "
                    "but missing from requirements.txt"
                ),
                "pos": 0,
            })
    return drifts
