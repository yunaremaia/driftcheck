"""Tests for .NET / C# drift detection: .csproj TargetFramework vs README."""
from pathlib import Path
import tempfile

from driftcheck.detectors.dotnet import (
    parse_dotnet_tfm,
    find_dotnet_drift,
    DOTNET_TF_RE,
    DOTNET_DOC_RE,
)


class TestParseDotnetTfm:
    def test_basic_target_framework(self):
        csproj = '<Project><TargetFramework>net8.0</TargetFramework></Project>'
        assert parse_dotnet_tfm(csproj) == "8.0"

    def test_target_frameworks_multi(self):
        csproj = '<Project><TargetFrameworks>net6.0;net7.0;net8.0</TargetFrameworks></Project>'
        assert parse_dotnet_tfm(csproj) == "6.0"

    def test_no_target_framework(self):
        csproj = '<Project><PropertyGroup><Version>1.0</Version></PropertyGroup></Project>'
        assert parse_dotnet_tfm(csproj) is None

    def test_empty_string(self):
        assert parse_dotnet_tfm("") is None

    def test_non_standard_tfm(self):
        csproj = '<Project><TargetFramework>netstandard2.0</TargetFramework></Project>'
        assert parse_dotnet_tfm(csproj) == "standard2.0"

    def test_case_insensitive(self):
        csproj = '<Project><TargetFramework>NET8.0</TargetFramework></Project>'
        assert parse_dotnet_tfm(csproj) == "8.0"


class TestFindDotnetDrift:
    def test_no_drift(self):
        csproj = {"MyApp.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>'}
        docs = {"README.md": "This project targets .NET 8.0"}
        assert find_dotnet_drift(csproj, docs) == []

    def test_drift_detected(self):
        csproj = {"MyApp.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>'}
        docs = {"README.md": "This project targets .NET 7.0"}
        drifts = find_dotnet_drift(csproj, docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_version"] == "7.0"
        assert drifts[0]["csproj_version"] == "8.0"

    def test_no_csproj_files(self):
        assert find_dotnet_drift({}, {"README.md": ".NET 8.0"}) == []

    def test_no_docs(self):
        csproj = {"MyApp.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>'}
        assert find_dotnet_drift(csproj, {}) == []

    def test_multiple_csproj_picks_latest(self):
        csproj = {
            "LibA.csproj": '<Project><TargetFramework>net6.0</TargetFramework></Project>',
            "LibB.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>',
        }
        docs = {"README.md": "Targets .NET 7.0"}
        drifts = find_dotnet_drift(csproj, docs)
        assert len(drifts) == 1
        assert drifts[0]["csproj_version"] == "8.0"

    def test_doc_mentions_core(self):
        csproj = {"MyApp.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>'}
        docs = {"README.md": "Built with .NET Core 3.1"}
        drifts = find_dotnet_drift(csproj, docs)
        assert len(drifts) == 1

    def test_doc_mentions_runtime(self):
        csproj = {"MyApp.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>'}
        docs = {"README.md": "Requires .NET Runtime 7.0"}
        drifts = find_dotnet_drift(csproj, docs)
        assert len(drifts) == 1

    def test_same_version_no_drift(self):
        csproj = {"MyApp.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>'}
        docs = {"README.md": "Uses .NET 8.0 and C# 12"}
        assert find_dotnet_drift(csproj, docs) == []

    def test_no_version_in_docs(self):
        csproj = {"MyApp.csproj": '<Project><TargetFramework>net8.0</TargetFramework></Project>'}
        docs = {"README.md": "A great .NET application"}
        assert find_dotnet_drift(csproj, docs) == []
