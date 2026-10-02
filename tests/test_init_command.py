"""Tests for `driftcheck init` subcommand."""
import io
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from driftcheck.cli import _detect_detectors, _generate_init_config, _detect_project_files

# Vendored dependency trees, build output and VCS metadata. `driftcheck init`
# has no business descending into any of them, and on a real repo they hold
# the overwhelming majority of the files.
VENDORED_DIRS = [
    "node_modules", ".git", "vendor", ".venv", "venv", "dist", "build",
    "target", "__pycache__", ".mypy_cache", ".tox", ".eggs",
]


@contextmanager
def count_scanned_dirs():
    """Record every directory the block actually scans.

    Both `Path.rglob` and `os.walk` reach the filesystem through
    `os.scandir`, so counting that one call measures how much of the tree a
    piece of code really visited -- without depending on which of the two it
    happens to use.
    """
    visited = []
    real_scandir = os.scandir

    def counting_scandir(path=".", *args, **kwargs):
        visited.append(Path(path))
        return real_scandir(path, *args, **kwargs)

    os.scandir = counting_scandir
    try:
        yield visited
    finally:
        os.scandir = real_scandir


@contextmanager
def count_bytes_read():
    """Total the characters a block actually pulls out of files.

    Counting at the stream (rather than timing the call) makes this a
    deterministic assertion instead of a flaky benchmark.
    """
    total = 0
    real_io_open = io.open
    real_path_open = Path.open

    class _CountingTextStream:
        def __init__(self, inner):
            self._inner = inner

        def read(self, *args, **kwargs):
            nonlocal total
            data = self._inner.read(*args, **kwargs)
            total += len(data)
            return data

        def __iter__(self):
            nonlocal total
            for chunk in self._inner:
                total += len(chunk)
                yield chunk

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return self._inner.__exit__(*exc)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def counting_io_open(file, mode="r", *args, **kwargs):
        handle = real_io_open(file, mode, *args, **kwargs)
        reading = "r" in mode and not any(c in mode for c in "wax+")
        if reading and isinstance(file, (str, bytes, os.PathLike)):
            return _CountingTextStream(handle)
        return handle

    io.open = counting_io_open
    Path.open = lambda self, *a, **k: counting_io_open(self, *a, **k)
    try:
        yield lambda: total
    finally:
        io.open = real_io_open
        Path.open = real_path_open


def test_detect_detectors_empty_repo():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        detected = _detect_detectors(root)
        assert detected == []


def test_detect_detectors_rust_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Cargo.toml").write_text("[package]\nname = 'test'\nversion = '0.1.0'\n")
        detected = _detect_detectors(root)
        assert "rust_drifts" in detected


def test_detect_detectors_node_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"name": "test"}')
        detected = _detect_detectors(root)
        assert "node_drifts" in detected
        assert "bun_drifts" in detected


def test_detect_detectors_python_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\nrequires-python = '>=3.11'\n")
        detected = _detect_detectors(root)
        assert "python_drifts" in detected


def test_detect_detectors_go_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "go.mod").write_text("module test\ngo 1.21\n")
        detected = _detect_detectors(root)
        assert "go_drifts" in detected


def test_detect_detectors_docker_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Dockerfile").write_text("FROM python:3.11\n")
        detected = _detect_detectors(root)
        assert "docker_drifts" in detected


def test_detect_detectors_ci_workflows():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: CI\non: push\n")
        detected = _detect_detectors(root)
        assert "actions_drifts" in detected
        assert "gh_actions_version_drifts" in detected


def test_detect_detectors_version_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".node-version").write_text("20.11.0\n")
        detected = _detect_detectors(root)
        assert "node_version_drifts" in detected


def test_generate_init_config_empty_repo():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        config = _generate_init_config(root)
        assert "[driftcheck]" in config
        assert "No project-specific files detected" in config


def test_generate_init_config_rust_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Cargo.toml").write_text("[package]\nname = 'test'\nversion = '0.1.0'\n")
        config = _generate_init_config(root)
        assert "[driftcheck]" in config
        assert "rust" in config.lower()
        assert "Cargo.toml" in config


def test_generate_init_config_node_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"name": "test"}')
        config = _generate_init_config(root)
        assert "[driftcheck]" in config
        assert "package.json" in config


def test_detect_project_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Cargo.toml").write_text("[package]\nname = 'test'\n")
        (root / "package.json").write_text('{"name": "test"}')
        files = _detect_project_files(root)
        assert "Cargo.toml" in files
        assert "package.json" in files


def test_detect_project_files_empty():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        files = _detect_project_files(root)
        assert files == []


def _make_vendored_noise(root: Path, per_dir: int = 40) -> int:
    """Fill `root` with vendored/build noise and return the file count."""
    written = 0
    for name in VENDORED_DIRS:
        for pkg in range(3):
            pkg_dir = root / name / f"pkg{pkg}"
            pkg_dir.mkdir(parents=True, exist_ok=True)
            for i in range(per_dir):
                (pkg_dir / f"m{i}.yaml").write_text("key: value\n")
                written += 1
    return written


def test_detect_detectors_does_not_walk_vendored_directories():
    """Vendored dependency/build trees must not be descended into.

    Issue #301. Detection used to `rglob` the entire repo for YAML, so on a
    repo with a populated node_modules/.venv/.git the cost scaled with the
    vendored file count -- which is where effectively all of the files are.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        noise_files = _make_vendored_noise(root)
        (root / "k8s").mkdir()
        (root / "k8s" / "deploy.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n"
        )

        with count_scanned_dirs() as visited:
            detected = _detect_detectors(root)

        assert "k8s_drifts" in detected, "k8s manifest in k8s/ must still be found"
        descended = [
            p for p in visited
            if VENDORED_DIRS[0] in p.parts
            or any(part in VENDORED_DIRS for part in p.parts)
        ]
        assert descended == [], (
            f"scanned {len(descended)} vendored dirs despite {noise_files} noise files; "
            f"first offenders: {[str(p) for p in descended[:5]]}"
        )


def test_detect_detectors_scan_is_bounded_by_repo_files_not_all_files():
    """Adding vendored noise must not add to the directories scanned.

    The load-bearing regression guard for #301: with the old rglob walk, every
    noise directory added was another directory visited on every `--init`.
    """
    with tempfile.TemporaryDirectory() as td:
        quiet = Path(td) / "quiet"
        noisy = Path(td) / "noisy"
        (quiet / "k8s").mkdir(parents=True)
        (quiet / "k8s" / "deploy.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n"
        )
        _make_vendored_noise(noisy, per_dir=25)
        (noisy / "k8s").mkdir()
        (noisy / "k8s" / "deploy.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n"
        )

        with count_scanned_dirs() as quiet_visits:
            _detect_detectors(quiet)
        with count_scanned_dirs() as noisy_visits:
            _detect_detectors(noisy)

        # Both repos are 1 marker deep; the noisy one carries 900 extra files.
        # Without pruning, `noisy` costs strictly more scans than `quiet`.
        assert len(noisy_visits) <= len(quiet_visits), (
            f"vendored noise increased scans: {len(quiet_visits)} -> {len(noisy_visits)}"
        )


def test_detect_detectors_reads_only_a_head_of_each_yaml():
    """Detection must not slurp whole files to inspect their first 2000 chars.

    `f.read_text()[:2000]` materialises the entire file (and the whole decode)
    before throwing all but 2 kB away. One 16 MiB manifest cost 16 MiB of I/O
    and allocation per call.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        big = root / "k8s"
        big.mkdir()
        (big / "huge.yaml").write_text(
            "name: big\n" + "# filler comment line\n" * 1_000_000
        )

        with count_bytes_read() as chars_read:
            detected = _detect_detectors(root)

        assert "k8s_drifts" not in detected, "filler-only YAML is not a k8s manifest"
        assert chars_read() < 200_000, (
            f"read {chars_read():,} chars to inspect YAML heads "
            f"(file is ~24 MB); should be bounded by the head size"
        )


def test_detect_detectors_does_not_read_vendored_yaml():
    """Vendored YAML must not be opened at all, not merely not descended into."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        vendored = root / "node_modules" / "some-pkg"
        vendored.mkdir(parents=True)
        # A vendored copy of a k8s manifest must not switch k8s detection on.
        (vendored / "deploy.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n"
        )

        with count_bytes_read() as chars_read:
            detected = _detect_detectors(root)

        assert "k8s_drifts" not in detected, (
            "a manifest vendored under node_modules/ must not enable k8s detection"
        )
        assert chars_read() == 0, (
            f"read {chars_read():,} chars out of node_modules/"
        )


def test_detect_detectors_still_finds_nested_and_root_manifests():
    """Cheap discovery must not narrow what counts as a k8s manifest.

    Guards the behaviour the old walk provided: any first-party YAML anywhere
    in the tree, not just inside k8s/.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        nested = root / "infra" / "prod"
        nested.mkdir(parents=True)
        (nested / "statefulset.yaml").write_text(
            "apiVersion: apps/v1\nkind: StatefulSet\n"
        )
        assert "k8s_drifts" in _detect_detectors(root)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "manifest.yaml").write_text("apiVersion: v1\nkind: Namespace\n")
        assert "k8s_drifts" in _detect_detectors(root)


def test_detect_detectors_handles_unreadable_yaml():
    """A file that cannot be decoded must be skipped, as before the fix."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        d = root / "k8s"
        d.mkdir()
        # Lone surrogates are undecodable under strict UTF-8.
        (d / "broken.yaml").write_bytes(b"apiVersion: v1\nkind: \xff\xfe\n")
        detected = _detect_detectors(root)
        assert isinstance(detected, list)
