"""Tests for Dockerfile multi-stage drift detection."""
import tempfile
from pathlib import Path
from driftcheck.detectors.docker_multistage import (
    parse_from_stages,
    find_dockerfile_multistage_drift,
    FROM_RE,
)


def test_parse_from_stages_basic():
    dockerfile = """FROM node:20 AS builder
WORKDIR /app
COPY . .
RUN npm build

FROM node:20-slim
COPY --from=builder /app/dist /app
CMD ["node", "app.js"]
"""
    stages = parse_from_stages(dockerfile)
    assert len(stages) == 2
    assert stages[0]["image"] == "node"
    assert stages[0]["tag"] == "20"
    assert stages[0]["alias"] == "builder"
    assert stages[1]["image"] == "node"
    assert stages[1]["tag"] == "20-slim"
    assert stages[1]["alias"] is None


def test_parse_from_stages_scratch():
    dockerfile = """FROM golang:1.21 AS builder
RUN go build -o app

FROM scratch
COPY --from=builder /app/app /app
CMD ["/app"]
"""
    stages = parse_from_stages(dockerfile)
    assert len(stages) == 2
    assert stages[1]["image"] == "scratch"
    assert stages[1]["tag"] is None


def test_parse_from_stages_empty():
    assert parse_from_stages("") == []


def test_find_dockerfile_multistage_drift_conflicting_tags():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dockerfile = """FROM node:20 AS builder
RUN npm build

FROM node:18-slim
COPY --from=builder /app/dist /app
"""
        (root / "Dockerfile").write_text(dockerfile)
        docs = {"README.md": "Some docs"}
        
        drifts = find_dockerfile_multistage_drift({"Dockerfile": dockerfile}, docs)
        assert len(drifts) == 1
        assert "node" in drifts[0]["detail"]
        assert "20" in drifts[0]["tags"]
        assert "18-slim" in drifts[0]["tags"]


def test_find_dockerfile_multistage_drift_no_conflict():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dockerfile = """FROM node:20 AS builder
RUN npm build

FROM node:20-slim
COPY --from=builder /app/dist /app
"""
        (root / "Dockerfile").write_text(dockerfile)
        docs = {"README.md": "Some docs"}
        
        # node:20 and node:20-slim have same base version — no conflict
        drifts = find_dockerfile_multistage_drift({"Dockerfile": dockerfile}, docs)
        assert len(drifts) == 0


def test_find_dockerfile_multistage_drift_no_dockerfile():
    drifts = find_dockerfile_multistage_drift({}, {"README.md": "text"})
    assert len(drifts) == 0


def test_find_dockerfile_multistage_drift_readme_mismatch():
    dockerfile = """FROM node:20-slim
CMD ["node", "app.js"]
"""
    docs = {"README.md": "Uses image node:18"}
    
    drifts = find_dockerfile_multistage_drift({"Dockerfile": dockerfile}, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_image"] == "node:18"
    assert drifts[0]["dockerfile_image"] == "node:20-slim"


def test_from_re_match():
    m = FROM_RE.search("FROM golang:1.21-alpine AS builder")
    assert m.group("image") == "golang"
    assert m.group("tag") == "1.21-alpine"
    assert m.group("alias") == "builder"


def test_docker_multistage_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dockerfile = """FROM python:3.11 AS builder
RUN pip install -r requirements.txt

FROM python:3.9-slim
COPY --from=builder /app /app
"""
        (root / "Dockerfile").write_text(dockerfile)
        (root / "README.md").write_text("Some docs")
        
        from driftcheck.detector import scan_repo
        result = scan_repo(root)
        assert "docker_multistage_drifts" in result
        assert len(result["docker_multistage_drifts"]) == 1
