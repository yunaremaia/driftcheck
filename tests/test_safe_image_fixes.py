"""Regression tests for position-aware Helm and Compose image tag fixes."""
import pytest

from driftcheck.detectors.fix import apply_fixes


@pytest.mark.parametrize(
    ("kind", "target_key"),
    [("helm_drifts", "helm_image"), ("dc_drifts", "compose_image")],
)
def test_image_fix_does_not_modify_earlier_url(tmp_path, kind, target_key):
    content = "See https://registry.example.com/docs/nginx:1.20\nUses nginx:1.20 in production\n"
    (tmp_path / "README.md").write_text(content)
    expected = content.replace("Uses nginx:1.20", "Uses nginx:1.21")
    pos = content.index("nginx:1.20", content.index("\n")) - 1
    result = {
        kind: [{
            "file": "README.md",
            "pos": pos,
            "doc_version": "nginx:1.20",
            target_key: "nginx:1.21",
        }],
    }
    assert apply_fixes(tmp_path, result) == ["README.md"]
    assert (tmp_path / "README.md").read_text() == expected


@pytest.mark.parametrize(
    ("kind", "target_key"),
    [("helm_drifts", "helm_image"), ("dc_drifts", "compose_image")],
)
def test_image_fix_changes_only_reported_occurrence(tmp_path, kind, target_key):
    content = "```\nnginx:1.20\n```\nProduction uses nginx:1.20\n"
    (tmp_path / "README.md").write_text(content)
    pos = content.index("nginx:1.20", content.index("Production")) - 1
    result = {
        kind: [{
            "file": "README.md",
            "pos": pos,
            "doc_version": "nginx:1.20",
            target_key: "nginx:1.21",
        }],
    }
    assert apply_fixes(tmp_path, result) == ["README.md"]
    assert (tmp_path / "README.md").read_text() == content.replace(
        "Production uses nginx:1.20", "Production uses nginx:1.21"
    )


@pytest.mark.parametrize(
    ("kind", "target_key"),
    [("helm_drifts", "helm_image"), ("dc_drifts", "compose_image")],
)
def test_image_fix_refuses_stale_reported_position(tmp_path, kind, target_key):
    content = "Uses nginx:1.20\nUses nginx:1.20\n"
    (tmp_path / "README.md").write_text(content)
    result = {kind: [{
        "file": "README.md",
        "pos": 999,
        "doc_version": "nginx:1.20",
        target_key: "nginx:1.21",
    }]}
    assert apply_fixes(tmp_path, result) == []
    assert (tmp_path / "README.md").read_text() == content


@pytest.mark.parametrize(
    ("kind", "target_key"),
    [("helm_drifts", "helm_image"), ("dc_drifts", "compose_image")],
)
def test_image_fix_legacy_result_skips_ambiguous_versions(tmp_path, kind, target_key):
    content = "First nginx:1.20\nSecond nginx:1.20\n"
    (tmp_path / "README.md").write_text(content)
    result = {kind: [{
        "file": "README.md",
        "doc_version": "nginx:1.20",
        target_key: "nginx:1.21",
    }]}
    assert apply_fixes(tmp_path, result) == []
    assert (tmp_path / "README.md").read_text() == content


@pytest.mark.parametrize(
    ("kind", "target_key"),
    [("helm_drifts", "helm_image"), ("dc_drifts", "compose_image")],
)
def test_image_fix_legacy_single_tag_is_supported(tmp_path, kind, target_key):
    (tmp_path / "README.md").write_text("Uses nginx:1.20 from Helm chart")
    result = {kind: [{
        "file": "README.md",
        "doc_version": "1.20",
        target_key: "1.21",
    }]}
    assert apply_fixes(tmp_path, result) == ["README.md"]
    assert (tmp_path / "README.md").read_text() == "Uses nginx:1.21 from Helm chart"
