from driftcheck.cli import _print_informational
from driftcheck.detectors.typosquat import find_typosquat_drift


def test_typosquat_details_appear_in_informational_output(tmp_path, capsys):
    (tmp_path / "requirements.txt").write_text("reqeusts==2.32.0\n", encoding="utf-8")
    drifts = find_typosquat_drift(tmp_path)
    assert drifts

    _print_informational({"typosquat_drifts": drifts})

    output = capsys.readouterr().out
    assert "driftcheck: info: requirements.txt:" in output
    assert "reqeusts" in output
    assert "requests" in output
    assert "suspected typosquat" in output


def test_no_typosquat_findings_produce_no_output(capsys):
    _print_informational({"typosquat_drifts": []})
    assert capsys.readouterr().out == ""
