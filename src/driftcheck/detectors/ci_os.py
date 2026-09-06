"""CI OS drift detection: deprecated GitHub Actions runners."""
from __future__ import annotations
import re
from pathlib import Path

CI_OS_DEPRECATED = {
    "ubuntu-18.04": "ubuntu-22.04",
    "ubuntu-20.04": "ubuntu-22.04",
    "macos-10.15": "macos-13",
    "macos-11": "macos-13",
    "windows-2016": "windows-2022",
    "windows-2019": "windows-2022",
}

CI_OS_RE = re.compile(r'runs-on:\s*(?P<runner>[^\s#]+)', re.I)


def find_ci_os_drift(root: Path) -> list[dict]:
    """Detect deprecated CI runners in GitHub Actions workflows."""
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []

    drifts = []
    for wf in list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
        try:
            text = wf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(wf.relative_to(root))
        for m in CI_OS_RE.finditer(text):
            runner = m.group("runner").lower()
            if runner in CI_OS_DEPRECATED:
                drifts.append({
                    "file": rel,
                    "runner": runner,
                    "suggested": CI_OS_DEPRECATED[runner],
                    "pos": m.start(),
                    "detail": f"deprecated runner {runner} → {CI_OS_DEPRECATED[runner]}",
                })
    return drifts
