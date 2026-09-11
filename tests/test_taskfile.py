"""Tests for Taskfile drift detection."""
import pytest
from pathlib import Path
from driftcheck.detectors.taskfile import (
    parse_taskfile,
    parse_makefile,
    find_taskfile_drift,
)


class TestParseTaskfile:
    def test_parse_simple_taskfile(self):
        text = """version: '3'

tasks:
  build:
    cmds:
      - go build ./...
  test:
    cmds:
      - go test ./...
"""
        result = parse_taskfile(text)
        assert "build" in result
        assert "test" in result
        assert "version" not in result  # Not a task

    def test_parse_taskfile_with_descriptions(self):
        text = """version: '3'

tasks:
  build:
    desc: Build the project
    cmds:
      - go build ./...
  test:
    desc: Run tests
    cmds:
      - go test ./...
"""
        result = parse_taskfile(text)
        assert "build" in result
        assert "test" in result
        assert len(result) == 2

    def test_parse_taskfile_empty(self):
        result = parse_taskfile("")
        assert result == {}

    def test_parse_taskfile_no_tasks_section(self):
        text = """version: '3'

includes:
  other:
    taskfile: ./other/Taskfile.yml
"""
        result = parse_taskfile(text)
        assert result == {}

    def test_parse_taskfile_with_vars(self):
        text = """version: '3'

vars:
  APP: myapp

tasks:
  build:
    cmds:
      - go build -o {{.APP}} ./...
"""
        result = parse_taskfile(text)
        assert "build" in result
        assert "vars" not in result


class TestParseMakefile:
    def test_parse_simple_makefile(self):
        text = """build:
\tgo build ./...

test:
\tgo test ./...
"""
        result = parse_makefile(text)
        assert "build" in result
        assert "test" in result

    def test_parse_makefile_with_variables(self):
        text = """APP=myapp

build:
\tgo build -o $(APP) ./...
"""
        result = parse_makefile(text)
        assert "build" in result
        assert "APP" not in result  # Variable, not target

    def test_parse_makefile_empty(self):
        result = parse_makefile("")
        assert result == {}

    def test_parse_makefile_with_comments(self):
        text = """# This is a comment
build:
\tgo build ./...
"""
        result = parse_makefile(text)
        assert "build" in result
        assert len(result) == 1


class TestFindTaskfileDrift:
    def test_no_drift_when_identical(self, tmp_path):
        (tmp_path / "Taskfile.yml").write_text("""version: '3'

tasks:
  build:
    cmds:
      - go build ./...
  test:
    cmds:
      - go test ./...
""")
        (tmp_path / "Makefile").write_text("""build:
\tgo build ./...

test:
\tgo test ./...
""")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 0

    def test_drift_taskfile_has_extra_tasks(self, tmp_path):
        (tmp_path / "Taskfile.yml").write_text("""version: '3'

tasks:
  build:
    cmds:
      - go build ./...
  test:
    cmds:
      - go test ./...
  lint:
    cmds:
      - golangci-lint run
""")
        (tmp_path / "Makefile").write_text("""build:
\tgo build ./...

test:
\tgo test ./...
""")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "taskfile_missing_in_makefile"
        assert "lint" in drifts[0]["detail"]

    def test_drift_makefile_has_extra_targets(self, tmp_path):
        (tmp_path / "Taskfile.yml").write_text("""version: '3'

tasks:
  build:
    cmds:
      - go build ./...
""")
        (tmp_path / "Makefile").write_text("""build:
\tgo build ./...

deploy:
\tkubectl apply -f k8s/
""")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "makefile_missing_in_taskfile"
        assert "deploy" in drifts[0]["detail"]

    def test_drift_both_sides(self, tmp_path):
        (tmp_path / "Taskfile.yml").write_text("""version: '3'

tasks:
  build:
    cmds:
      - go build ./...
  lint:
    cmds:
      - golangci-lint run
""")
        (tmp_path / "Makefile").write_text("""build:
\tgo build ./...

deploy:
\tkubectl apply -f k8s/
""")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 2

    def test_no_taskfile(self, tmp_path):
        (tmp_path / "Makefile").write_text("""build:
\tgo build ./...
""")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 0

    def test_no_makefile(self, tmp_path):
        (tmp_path / "Taskfile.yml").write_text("""version: '3'

tasks:
  build:
    cmds:
      - go build ./...
""")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 0

    def test_yaml_extension(self, tmp_path):
        (tmp_path / "Taskfile.yaml").write_text("""version: '3'

tasks:
  build:
    cmds:
      - go build ./...
  lint:
    cmds:
      - golangci-lint run
""")
        (tmp_path / "Makefile").write_text("""build:
\tgo build ./...
""")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 1
        assert "lint" in drifts[0]["detail"]

    def test_empty_files(self, tmp_path):
        (tmp_path / "Taskfile.yml").write_text("")
        (tmp_path / "Makefile").write_text("")
        drifts = find_taskfile_drift(tmp_path)
        assert len(drifts) == 0
