"""Tests for Dockerfile instruction drift detection."""
from driftcheck.detectors.dockerfile_instructions import (
    parse_dockerfile_instructions,
    find_dockerfile_instruction_drift,
)


def test_parse_dockerfile_instructions():
    dockerfile = """FROM python:3.11
WORKDIR /app
EXPOSE 8080
USER appuser
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8080/health
ENTRYPOINT ["python", "app.py"]
"""
    result = parse_dockerfile_instructions(dockerfile)
    assert result["WORKDIR"] == "/app"
    assert result["EXPOSE"] == "8080"
    assert result["USER"] == "appuser"
    assert "HEALTHCHECK" in result
    assert "ENTRYPOINT" in result


def test_find_dockerfile_instruction_drift_expose():
    dockerfiles = {"Dockerfile": "FROM python:3.11\nEXPOSE 8080\n"}
    docs = {"README.md": "This service exposes port 9090"}
    drifts = find_dockerfile_instruction_drift(dockerfiles, docs)
    assert len(drifts) == 1
    assert drifts[0]["instruction"] == "EXPOSE"
    assert drifts[0]["doc_value"] == "9090"
    assert drifts[0]["dockerfile_value"] == "8080"


def test_find_dockerfile_instruction_drift_workdir():
    dockerfiles = {"Dockerfile": "FROM python:3.11\nWORKDIR /app\n"}
    docs = {"README.md": "Working directory is /srv"}
    drifts = find_dockerfile_instruction_drift(dockerfiles, docs)
    assert len(drifts) == 1
    assert drifts[0]["instruction"] == "WORKDIR"
    assert drifts[0]["doc_value"] == "/srv"
    assert drifts[0]["dockerfile_value"] == "/app"


def test_find_dockerfile_instruction_drift_no_drift():
    dockerfiles = {"Dockerfile": "FROM python:3.11\nEXPOSE 8080\n"}
    docs = {"README.md": "This service exposes port 8080"}
    drifts = find_dockerfile_instruction_drift(dockerfiles, docs)
    assert len(drifts) == 0


def test_find_dockerfile_instruction_drift_no_dockerfile():
    dockerfiles = {}
    docs = {"README.md": "This service exposes port 8080"}
    drifts = find_dockerfile_instruction_drift(dockerfiles, docs)
    assert len(drifts) == 0


def test_find_dockerfile_instruction_drift_multiple():
    dockerfiles = {"Dockerfile": "FROM python:3.11\nEXPOSE 8080\nWORKDIR /app\n"}
    docs = {"README.md": "Exposes port 9090, working directory /srv"}
    drifts = find_dockerfile_instruction_drift(dockerfiles, docs)
    assert len(drifts) == 2
    instructions = {d["instruction"] for d in drifts}
    assert "EXPOSE" in instructions
    assert "WORKDIR" in instructions
