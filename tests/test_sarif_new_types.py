"""Tests for newly-added SARIF drift types: devcontainer, compose_override, helm_values."""
from driftcheck.sarif import to_sarif


class TestSarifDevcontainer:
    def test_devcontainer_image_drift(self):
        result = {
            "devcontainer_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.68",
                    "devcontainer_version": "1.70",
                    "feature": "image:rust",
                    "pos": 42,
                }
            ]
        }
        sarif = to_sarif(result, version="0.1.40")
        assert len(sarif["runs"][0]["results"]) == 1
        r = sarif["runs"][0]["results"][0]
        assert r["ruleId"] == "devcontainer-version-drift"
        assert "1.68" in r["message"]["text"]
        assert "1.70" in r["message"]["text"]
        assert r["level"] == "error"

    def test_devcontainer_feature_drift(self):
        result = {
            "devcontainer_drifts": [
                {
                    "file": "docs/setup.md",
                    "doc_version": "1",
                    "devcontainer_version": "2",
                    "feature": "docker-in-docker",
                    "pos": 0,
                }
            ]
        }
        sarif = to_sarif(result, version="0.1.40")
        assert len(sarif["runs"][0]["results"]) == 1
        assert "docker-in-docker" in sarif["runs"][0]["results"][0]["message"]["text"]


class TestSarifComposeOverride:
    def test_compose_override_drift(self):
        result = {
            "compose_override_drifts": [
                {"detail": "nginx:1.26 in prod vs 1.25 in base", "file": "docker-compose.prod.yml"}
            ]
        }
        sarif = to_sarif(result, version="0.1.40")
        assert len(sarif["runs"][0]["results"]) == 1
        r = sarif["runs"][0]["results"][0]
        assert r["ruleId"] == "compose-override-drift"
        assert "nginx" in r["message"]["text"]


class TestSarifHelmValues:
    def test_helm_values_drift(self):
        result = {
            "helm_values_drifts": [
                {
                    "key": "replicaCount",
                    "override_value": "3",
                    "default_value": "1",
                    "file": "values.prod.yaml",
                }
            ]
        }
        sarif = to_sarif(result, version="0.1.40")
        assert len(sarif["runs"][0]["results"]) == 1
        r = sarif["runs"][0]["results"][0]
        assert r["ruleId"] == "helm-values-drift"
        assert "replicaCount" in r["message"]["text"]


class TestSarifVersionAuto:
    def test_version_none_uses_package_version(self):
        """When version=None, should auto-detect from package __version__."""
        result = {"drifts": [{"doc_version": "1.0", "toolchain_version": "2.0", "file": "README.md"}]}
        sarif = to_sarif(result, version=None)
        assert sarif["runs"][0]["tool"]["driver"]["version"] == "0.1.40"

    def test_version_explicit(self):
        result = {"drifts": [{"doc_version": "1.0", "toolchain_version": "2.0", "file": "README.md"}]}
        sarif = to_sarif(result, version="0.9.9")
        assert sarif["runs"][0]["tool"]["driver"]["version"] == "0.9.9"
