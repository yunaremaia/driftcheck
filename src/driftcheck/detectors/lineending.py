"""Line ending drift detection: missing CRLF-safe .gitattributes."""
from __future__ import annotations
import re
from pathlib import Path

EOL_ATTR_RE = re.compile(r'^\s*\*?\s*text\s*=\s*auto', re.MULTILINE)
EOL_LINE_RE = re.compile(r'^\s*\*.*eol\s*=\s*lf', re.MULTILINE)


def find_lineending_drift(root: Path) -> list[dict]:
    """Detect missing CRLF-safe .gitattributes.

    A repo that ships text source but lacks `* text=auto eol=lf` in
    .gitattributes can check out with CRLF working-tree bytes on Windows
    (core.autocrlf=true) while the index stores LF -- silently breaking
    byte-exact checks. Returns a drift if .gitattributes is absent or does
    not normalize line endings.
    
    Only fires when the repo has source files (to avoid noise on empty dirs).
    """
    # Check if repo has any source files that would need line ending normalization
    source_patterns = [
        "*.py", "*.js", "*.ts", "*.tsx", "*.jsx", "*.rs", "*.go", "*.java",
        "*.kt", "*.kts", "*.c", "*.cpp", "*.h", "*.hpp", "*.rb", "*.php",
        "*.cs", "*.fs", "*.swift", "*.m", "*.mm", "*.scala", "*.clj",
        "*.sh", "*.bash", "*.zsh", "*.fish", "*.ps1", "*.bat", "*.cmd",
        "*.xml", "*.json", "*.yaml", "*.yml", "*.toml", "*.ini", "*.cfg",
        "*.conf", "*.config", "*.properties", "*.gradle", "*.sbt",
        "Makefile", "Dockerfile", "*.md", "*.rst", "*.txt",
    ]
    has_source = False
    for pattern in source_patterns:
        if list(root.glob(pattern)):
            has_source = True
            break
    if not has_source:
        # Check common subdirectories
        for subdir in ["src", "lib", "app", "test", "tests", "scripts", "bin", "pkg", "cmd"]:
            subpath = root / subdir
            if subpath.exists():
                for pattern in source_patterns:
                    if list(subpath.glob(pattern)):
                        has_source = True
                        break
            if has_source:
                break
    
    if not has_source:
        return []  # Empty repo or no source files — skip lineending check

    ga = root / ".gitattributes"
    if not ga.exists():
        return [{
            "file": ".gitattributes",
            "kind": "lineending",
            "detail": "missing .gitattributes with `* text=auto eol=lf`",
        }]
    text = ga.read_text(encoding="utf-8", errors="replace")
    if not (EOL_ATTR_RE.search(text) and EOL_LINE_RE.search(text)):
        return [{
            "file": ".gitattributes",
            "kind": "lineending",
            "detail": ".gitattributes does not set `* text=auto eol=lf`",
        }]
    return []
