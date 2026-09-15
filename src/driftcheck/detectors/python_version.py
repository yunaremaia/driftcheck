"""Check .python-version against the project's minimum Python requirement."""

from __future__ import annotations

import configparser
import re

_VERSION = re.compile(r"(?P<release>[0-9]+(?:\.[0-9]+){0,2})(?:(?:a|b|rc)[0-9]+)?")
_REQUIREMENT = re.compile(
    r"(?P<op>>=|>|~=|==)\s*(?P<release>[0-9]+(?:\.[0-9]+){0,2})"
    r"(?:(?:a|b|rc)[0-9]+|\.\*)?"
)


def _requires_python(pyproject: str, setup_cfg: str) -> tuple[str, str]:
    """Read a quoted project requirement, falling back to setup.cfg."""
    in_project = False
    for line in pyproject.splitlines():
        section = re.fullmatch(r"\s*\[(.+?)\]\s*(?:#.*)?", line)
        if section:
            in_project = section.group(1).strip() == "project"
        if in_project:
            match = re.fullmatch(
                r"\s*requires-python\s*=\s*(['\"])(.*?)\1\s*(?:#.*)?", line
            )
            if match:
                return match.group(2), "pyproject.toml"

    parser = configparser.ConfigParser(
        interpolation=None, inline_comment_prefixes=("#",)
    )
    try:
        parser.read_string(setup_cfg)
        return parser.get("options", "python_requires", fallback=""), "setup.cfg"
    except configparser.Error:
        return "", "setup.cfg"


def _minimum(requirement: str) -> tuple[str, bool] | None:
    """Find the strongest lower bound, ignoring upper bounds and exclusions."""
    bounds = []
    for part in requirement.split(","):
        match = _REQUIREMENT.fullmatch(part.strip())
        if match:
            release = match.group("release")
            parts = tuple(int(p) for p in release.split("."))
            strict = match.group("op") == ">"
            bounds.append((parts + (0,) * (3 - len(parts)), strict, release))
    if not bounds:
        return None
    _, strict, release = max(bounds)
    return release, strict


def find_python_version_file_drift(
    python_version_text: str | None, pyproject_text: str, setup_cfg_text: str = ""
) -> list[dict]:
    """Compare a Python pin with requires-python or setup.cfg's python_requires.

    Missing files or requirements with no lower bound produce no drift. Partial
    pins are compared at their stated precision, and prereleases use their base
    release. Unsupported pin syntax is informational, not a version mismatch.
    """
    if python_version_text is None:
        return []
    requirement, source = _requires_python(pyproject_text, setup_cfg_text)
    minimum = _minimum(requirement)
    if minimum is None:
        return []

    lines = [line.split("#", 1)[0].strip() for line in python_version_text.splitlines()]
    values = [line for line in lines if line]
    pin = values[0] if len(values) == 1 else "\n".join(values)
    match = _VERSION.fullmatch(pin)
    if not match:
        return [
            {
                "file": ".python-version",
                "tool": "Python",
                "doc_version": pin,
                "source_file": source,
                "informational": True,
                "detail": "Cannot compare .python-version: expected one numeric Python version.",
                "pos": 0,
            }
        ]

    floor, strict = minimum
    pinned_parts = tuple(int(p) for p in match.group("release").split("."))
    floor_parts = tuple(int(p) for p in floor.split("."))
    # pyenv/uv can resolve partial pins to a compatible patch or minor release.
    precision = len(pinned_parts)
    padded_floor = (floor_parts + (0,) * 3)[:precision]
    below = pinned_parts < padded_floor
    equal_strict = strict and precision == 3 and pinned_parts == padded_floor
    if not below and not equal_strict:
        return []

    operator = ">" if strict else ">="
    return [
        {
            "file": ".python-version",
            "tool": "Python",
            "doc_version": pin,
            "required_version": floor,
            "source_file": source,
            "detail": f"Python {pin} is below the required minimum {operator}{floor} ({source}).",
            "pos": 0,
        }
    ]
