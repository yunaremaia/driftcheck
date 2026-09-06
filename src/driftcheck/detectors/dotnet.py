""".NET / C# drift detection: .csproj <TargetFramework> vs README mentions."""
from __future__ import annotations
import re

DOTNET_TF_RE = re.compile(r'<TargetFrameworks?\s*>\s*(?P<tf>[^<]+)</TargetFrameworks?>', re.I)
DOTNET_DOC_RE = re.compile(r'\.NET\s+(?:Core\s+|Runtime\s+|SDK\s+)?(?P<ver>[0-9]+(?:\.[0-9]+)?)', re.I)


def parse_dotnet_tfm(csproj_text: str) -> str | None:
    """Parse .NET TargetFramework from a .csproj file. Returns major.minor (e.g., '8.0')."""
    m = DOTNET_TF_RE.search(csproj_text)
    if not m:
        return None
    tfm = m.group("tf").strip()
    first = tfm.split(";")[0].strip()  # multi-targeting → first TFM
    if first.startswith("net"):
        return first[3:]  # "net8.0" → "8.0"
    return None


def find_dotnet_drift(csproj_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect .NET version drift between .csproj <TargetFramework> and docs mentions.

    Returns list of {file, doc_version, csproj_version, pos}.
    Only flags when doc version differs from the csproj TFM.
    """
    if not csproj_files:
        return []
    versions = set()
    for text in csproj_files.values():
        v = parse_dotnet_tfm(text)
        if v:
            versions.add(v)
    if not versions:
        return []
    csproj_ver = max(versions, key=lambda v: tuple(int(x) for x in v.split(".")))
    drifts = []
    for fname, doc_content in docs.items():
        for m in DOTNET_DOC_RE.finditer(doc_content):
            dv = m.group("ver")
            if dv != csproj_ver:
                drifts.append({"file": fname, "doc_version": dv, "csproj_version": csproj_ver, "pos": m.start()})
                break
    return drifts
