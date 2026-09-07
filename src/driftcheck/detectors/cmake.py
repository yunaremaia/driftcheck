"""CMake drift detection: CMakeLists.txt version vs README."""
from __future__ import annotations
import re

CMAKE_VERSION_RE = re.compile(
    r'cmake_minimum_required\s*\(\s*VERSION\s+([\d.]+)',
    re.I,
)
CMAKE_DOC_RE = re.compile(
    r'(?:cmake|require[s]?\s+cmake)\s*v?(\d+\.\d+(?:\.\d+)?)',
    re.I,
)


def parse_cmake_version(text: str) -> str | None:
    """Parse CMake version from CMakeLists.txt.

    Expects: cmake_minimum_required(VERSION 3.16)
    Returns: "3.16"
    """
    m = CMAKE_VERSION_RE.search(text)
    return m.group(1) if m else None


def find_cmake_drift(cmake_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect CMake version drift between CMakeLists.txt and README.

    Args:
        cmake_text: content of CMakeLists.txt
        docs: {relative_path: content} of README/CONTRIBUTING files

    Returns list of {file, doc_version, cmake_version, pos}.
    """
    cmake_ver = parse_cmake_version(cmake_text)
    if not cmake_ver:
        return []

    drifts = []
    for rel_path, text in docs.items():
        for m in CMAKE_DOC_RE.finditer(text):
            doc_ver = m.group(1)
            doc_parts = doc_ver.split(".")
            cmake_parts = cmake_ver.split(".")
            if doc_parts[:2] != cmake_parts[:2]:
                drifts.append({
                    "file": rel_path,
                    "doc_version": doc_ver,
                    "cmake_version": cmake_ver,
                    "pos": m.start(),
                })
                break
    return drifts
