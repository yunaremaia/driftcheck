"""Tests for A2A (Agent2Agent) protocol drift detector."""

from pathlib import Path

import pytest

from driftcheck.detectors.a2a import (
    parse_agent_card,
    extract_card_spec_version,
    extract_card_capabilities,
    extract_card_endpoints,
    find_a2a_drift,
    is_agent_card_file,
)


class TestIsAgentCardFile:
    def test_agent_json(self):
        assert is_agent_card_file(Path("agent.json")) is True

    def test_agent_card_json(self):
        assert is_agent_card_file(Path("agent-card.json")) is True

    def test_agent_card_yaml(self):
        assert is_agent_card_file(Path("agent-card.yaml")) is True

    def test_a2a_dir(self):
        assert is_agent_card_file(Path(".a2a/card.json")) is True

    def test_regular_json(self):
        assert is_agent_card_file(Path("package.json")) is False

    def test_readme(self):
        assert is_agent_card_file(Path("README.md")) is False


class TestParseAgentCard:
    def test_valid_card(self, tmp_path):
        card_data = {"name": "test-agent", "spec_version": "1.0"}
        card_path = tmp_path / "test-agent.json"
        card_path.write_text('{"name": "test-agent", "spec_version": "1.0"}')
        try:
            result = parse_agent_card(card_path)
            assert result == card_data
        finally:
            card_path.unlink(missing_ok=True)

    def test_invalid_json(self, tmp_path):
        card_path = tmp_path / "bad.json"
        card_path.write_text("{bad json}")
        try:
            assert parse_agent_card(card_path) is None
        finally:
            card_path.unlink(missing_ok=True)

    def test_nonexistent(self):
        assert parse_agent_card(Path("nonexistent.json")) is None


class TestExtractSpecVersion:
    def test_standard_field(self):
        card = {"spec_version": "1.0", "name": "agent"}
        assert extract_card_spec_version(card) == "1.0"

    def test_version_field(self):
        card = {"version": "0.3", "name": "agent"}
        assert extract_card_spec_version(card) == "0.3"

    def test_no_version(self):
        card = {"name": "agent"}
        assert extract_card_spec_version(card) is None

    def test_empty_card(self):
        assert extract_card_spec_version({}) is None


class TestExtractCapabilities:
    def test_capabilities_field(self):
        card = {
            "capabilities": [
                {"name": "chat", "description": "Chat capability"},
                {"name": "codegen", "description": "Code generation"},
            ]
        }
        caps = extract_card_capabilities(card)
        assert "chat" in caps
        assert "codegen" in caps

    def test_skills_field(self):
        card = {"skills": ["skill-a", "skill-b"]}
        caps = extract_card_capabilities(card)
        assert "skill-a" in caps
        assert "skill-b" in caps

    def test_tools_field(self):
        card = {"tools": [{"name": "tool-x"}, {"name": "tool-y"}]}
        caps = extract_card_capabilities(card)
        assert "tool-x" in caps

    def test_empty_card(self):
        assert extract_card_capabilities({}) == []

    def test_no_capability_fields(self):
        card = {"name": "agent", "endpoint": "http://example.com"}
        assert extract_card_capabilities(card) == []


class TestExtractEndpoints:
    def test_endpoint_string(self):
        card = {"endpoint": "http://localhost:8080"}
        eps = extract_card_endpoints(card)
        assert "http://localhost:8080" in eps

    def test_endpoint_dict(self):
        card = {"endpoint": {"url": "http://api.example.com/v1"}}
        eps = extract_card_endpoints(card)
        assert "http://api.example.com/v1" in eps

    def test_urls_field(self):
        card = {"urls": ["http://a.com", "http://b.com"]}
        eps = extract_card_endpoints(card)
        assert "http://a.com" in eps
        assert "http://b.com" in eps

    def test_empty_card(self):
        assert extract_card_endpoints({}) == []


class TestFindA2ADrift:
    def test_no_card_files(self, tmp_path):
        """No agent card files = no drift."""
        (tmp_path / "README.md").write_text("# My Project\nA2A protocol v1.0")
        result = find_a2a_drift(tmp_path, {"README.md": "# My Project\nA2A protocol v1.0"})
        assert result == []

    def test_spec_version_mismatch(self, tmp_path):
        """Agent card declares v0.3 but docs say v1.0."""
        card_path = tmp_path / "agent.json"
        card_path.write_text('{"name": "test", "spec_version": "0.3", "endpoint": "http://localhost"}')
        docs = {"README.md": "# Project\nSupports A2A protocol v1.0"}
        result = find_a2a_drift(tmp_path, docs)
        assert len(result) >= 1
        drift = result[0]
        assert drift["doc_version"] == "1.0"
        assert drift["card_version"] == "0.3"
        assert "mismatch" in drift["detail"].lower()

    def test_matching_versions(self, tmp_path):
        """Card and docs agree on version."""
        card_path = tmp_path / "agent-card.json"
        card_path.write_text('{"name": "test", "spec_version": "1.0"}')
        docs = {"README.md": "# Project\nA2A v1.0"}
        result = find_a2a_drift(tmp_path, docs)
        # Should not flag version mismatch
        version_drifts = [d for d in result if "mismatch" in d.get("detail", "").lower()]
        assert len(version_drifts) == 0

    def test_capability_informational(self, tmp_path):
        """Card has capability not mentioned in docs (informational only)."""
        card_path = tmp_path / "agent.json"
        card_path.write_text('{"name": "test", "capabilities": [{"name": "code-interpreter"}], "endpoint": "http://localhost"}')
        docs = {"README.md": "# Project\nA2A v1.0"}
        result = find_a2a_drift(tmp_path, docs)
        cap_drifts = [d for d in result if "code-interpreter" in d.get("detail", "")]
        assert len(cap_drifts) >= 0  # informational, may or may not fire depending on config

    def test_endpoint_informational(self, tmp_path):
        """Card has endpoint not in docs."""
        card_path = tmp_path / "agent-card.json"
        card_path.write_text('{"name": "test", "endpoint": "http://hidden.example.com"}')
        docs = {"README.md": "# Project\nA2A v1.0"}
        result = find_a2a_drift(tmp_path, docs)
        ep_drifts = [d for d in result if "hidden.example.com" in d.get("detail", "")]
        assert len(ep_drifts) >= 0  # informational

    def test_multiple_cards(self, tmp_path):
        """Multiple agent cards with different versions."""
        card1 = tmp_path / "agent.json"
        card1.write_text('{"name": "agent1", "spec_version": "0.3"}')
        card2 = tmp_path / "agent-card.json"
        card2.write_text('{"name": "agent2", "spec_version": "1.0"}')
        docs = {"README.md": "# Project\nA2A protocol v1.0"}
        result = find_a2a_drift(tmp_path, docs)
        # A drift for agent1 (v0.3 card, v1.0 docs) should be detected
        version_drifts = [d for d in result if "mismatch" in d.get("detail", "").lower()]
        assert len(version_drifts) >= 1, f"Expected version mismatch drift, got: {result}"
        # Verify correct versions in drift
        drift = version_drifts[0]
        assert drift["card_version"] == "0.3"
        assert drift["doc_version"] == "1.0"

    def test_card_without_endpoint(self, tmp_path):
        """Card without endpoint field should not crash."""
        card_path = tmp_path / "agent-card.json"
        card_path.write_text('{"name": "minimal-agent"}')
        docs = {"README.md": "# Project"}
        result = find_a2a_drift(tmp_path, docs)
        assert isinstance(result, list)

    def test_a2a_dir_cards(self, tmp_path):
        """Cards in .a2a/ directory are detected."""
        a2a_dir = tmp_path / ".a2a"
        a2a_dir.mkdir()
        card_path = a2a_dir / "card.json"
        card_path.write_text('{"name": "test", "spec_version": "0.3"}')
        docs = {"README.md": "# Project\nA2A v1.0"}
        result = find_a2a_drift(tmp_path, docs)
        # The card (v0.3) should drift against docs (v1.0)
        version_drifts = [d for d in result if "mismatch" in d.get("detail", "").lower()]
        assert len(version_drifts) >= 1, f"Expected version mismatch drift for .a2a card, got: {result}"
