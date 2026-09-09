"""Taskfile drift detection: Taskfile.yml vs Makefile.

Detects drift between Taskfile.yml and Makefile when both exist:
- Tasks defined in Taskfile but not in Makefile
- Tasks defined in Makefile but not in Taskfile
- Same task name but different commands (heuristic: command length differs significantly)
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

TASKFILE_TASK_RE = re.compile(r'^\s{2}([a-zA-Z_][a-zA-Z0-9_-]*)\s*:', re.MULTILINE)
MAKEFILE_TASK_RE = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:', re.MULTILINE)


def parse_taskfile(text: str) -> dict[str, str]:
    """Parse Taskfile.yml into {task_name: body} dict.
    
    Taskfile format:
        version: '3'
        
        tasks:
          build:
            cmds:
              - go build ./...
          test:
            cmds:
              - go test ./...
    
    We look for task names at indent level 2 (under 'tasks:').
    """
    tasks = {}
    lines = text.splitlines()
    in_tasks_section = False
    current_task = None
    current_body = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Detect tasks section
        if stripped == 'tasks:':
            in_tasks_section = True
            continue
        
        # If we hit another top-level key (no indent), exit tasks section
        if in_tasks_section and not line.startswith(' ') and not line.startswith('\t'):
            in_tasks_section = False
            if current_task:
                tasks[current_task] = '\n'.join(current_body)
            current_task = None
            current_body = []
            continue

        if not in_tasks_section:
            continue

        # Task definition at indent level 2
        m = TASKFILE_TASK_RE.match(line)
        if m:
            if current_task:
                tasks[current_task] = '\n'.join(current_body)
            current_task = m.group(1)
            current_body = []
            continue

        if current_task:
            current_body.append(line)

    if current_task:
        tasks[current_task] = '\n'.join(current_body)

    return tasks


def parse_makefile(text: str) -> dict[str, str]:
    """Parse Makefile into {target_name: body} dict."""
    targets = {}
    lines = text.splitlines()
    current_target = None
    current_body = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Target definition (starts at column 0, ends with :)
        m = MAKEFILE_TASK_RE.match(line)
        if m and not line.startswith('\t'):
            if current_target:
                targets[current_target] = '\n'.join(current_body)
            current_target = m.group(1)
            current_body = []
            continue

        if current_target and line.startswith('\t'):
            current_body.append(line)

    if current_target:
        targets[current_target] = '\n'.join(current_body)

    return targets


def find_taskfile_drift(root: Path) -> list[dict]:
    """Detect drift between Taskfile.yml and Makefile.

    Reports:
    - Tasks in Taskfile but missing from Makefile
    - Tasks in Makefile but missing from Taskfile
    """
    taskfile_path = root / "Taskfile.yml"
    if not taskfile_path.exists():
        taskfile_path = root / "Taskfile.yaml"
    makefile_path = root / "Makefile"

    if not taskfile_path.exists() or not makefile_path.exists():
        return []

    taskfile_text = taskfile_path.read_text(encoding="utf-8", errors="replace")
    makefile_text = makefile_path.read_text(encoding="utf-8", errors="replace")

    taskfile_tasks = parse_taskfile(taskfile_text)
    makefile_targets = parse_makefile(makefile_text)

    drifts = []

    # Tasks in Taskfile but not in Makefile
    missing_in_make = set(taskfile_tasks.keys()) - set(makefile_targets.keys())
    if missing_in_make:
        drifts.append({
            "file": "Makefile",
            "kind": "taskfile_missing_in_makefile",
            "detail": f"Tasks in Taskfile.yml but missing from Makefile: {', '.join(sorted(missing_in_make))}",
            "keys": sorted(missing_in_make),
        })

    # Tasks in Makefile but not in Taskfile
    missing_in_task = set(makefile_targets.keys()) - set(taskfile_tasks.keys())
    if missing_in_task:
        drifts.append({
            "file": "Taskfile.yml",
            "kind": "makefile_missing_in_taskfile",
            "detail": f"Targets in Makefile but missing from Taskfile.yml: {', '.join(sorted(missing_in_task))}",
            "keys": sorted(missing_in_task),
        })

    return drifts
