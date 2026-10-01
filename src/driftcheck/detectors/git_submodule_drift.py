"""Git submodule commit drift detector.

Detects when submodules point to different commits than what's recorded
in the git index. This helps keep submodules in sync with the parent repo.
"""
import subprocess
from pathlib import Path
from typing import Optional


def _parse_gitmodules(content: str) -> list[dict]:
    """Parse .gitmodules content into a list of submodule dicts."""
    submodules = []
    current = None
    
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("[submodule"):
            if current:
                submodules.append(current)
            current = {"name": line.split('"')[1] if '"' in line else ""}
        elif current and "=" in line:
            key, value = line.split("=", 1)
            current[key.strip()] = value.strip()
    
    if current:
        submodules.append(current)
    
    return submodules


def _get_indexed_commit(root: Path, submodule_path: str) -> Optional[str]:
    """Get the commit hash recorded in the git index for a submodule."""
    try:
        result = subprocess.run(
            ["git", "ls-tree", "HEAD", submodule_path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Format: <mode> <type> <hash>\t<path>
            parts = result.stdout.strip().split()
            if len(parts) >= 3:
                return parts[2]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_submodule_head(root: Path, submodule_path: str) -> Optional[str]:
    """Get the current HEAD commit of a submodule."""
    submodule_dir = root / submodule_path
    git_file = submodule_dir / ".git"
    
    if not git_file.exists():
        return None
    
    # Read the gitdir path
    gitdir_content = git_file.read_text().strip()
    if gitdir_content.startswith("gitdir: "):
        gitdir = submodule_dir / gitdir_content[8:]
    else:
        gitdir = submodule_dir / ".git"
    
    # Try to read HEAD
    head_file = gitdir / "HEAD"
    if not head_file.exists():
        return None
    
    head_content = head_file.read_text().strip()
    if head_content.startswith("ref: "):
        # It's a symbolic ref, read the actual ref
        ref_path = gitdir / head_content[5:]
        if ref_path.exists():
            return ref_path.read_text().strip()
    else:
        # It's a detached HEAD
        return head_content
    
    return None


def find_git_submodule_drift(root: Path) -> list[dict]:
    """Find git submodules with commit drift.
    
    Args:
        root: Path to the repository root.
        
    Returns:
        List of drift dictionaries with keys:
        - type: "submodule"
        - name: submodule name
        - path: submodule path
        - indexed_commit: commit recorded in parent repo index
        - current_commit: current HEAD of submodule
    """
    drifts = []
    gitmodules_path = root / ".gitmodules"
    
    if not gitmodules_path.exists():
        return drifts
    
    content = gitmodules_path.read_text(encoding="utf-8")
    submodules = _parse_gitmodules(content)
    
    for sub in submodules:
        path = sub.get("path", "")
        name = sub.get("name", path)
        
        if not path:
            continue
        
        indexed_commit = _get_indexed_commit(root, path)
        current_commit = _get_submodule_head(root, path)
        
        if indexed_commit and current_commit and indexed_commit != current_commit:
            drifts.append({
                "type": "submodule",
                "name": name,
                "path": path,
                "indexed_commit": indexed_commit[:12],
                "current_commit": current_commit[:12],
            })
    
    return drifts
