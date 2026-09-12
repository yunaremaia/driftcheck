"""Tests for Dockerfile base image drift detection."""
import pytest
from driftcheck.detectors.docker_bases import (
    parse_dockerfile_bases,
    find_dockerfile_bases_drift,
    FROM_LINE_RE,
    FLOATING_TAGS,
)


class TestParseDockerfileBases:
    def test_single_pinned(self):
        content = "FROM node:20-slim\nRUN echo hello"
        result = parse_dockerfile_bases(content)
        assert len(result) == 1
        assert result[0]['image'] == 'node'
        assert result[0]['tag'] == '20-slim'
        assert result[0]['floating'] is False

    def test_implicit_latest(self):
        content = "FROM python\nRUN echo hello"
        result = parse_dockerfile_bases(content)
        assert len(result) == 1
        assert result[0]['tag'] is None
        assert result[0]['floating'] is True

    def test_explicit_latest(self):
        content = "FROM node:latest\nRUN echo hello"
        result = parse_dockerfile_bases(content)
        assert result[0]['floating'] is True

    def test_stable_tag(self):
        content = "FROM golang:stable\nRUN echo hello"
        result = parse_dockerfile_bases(content)
        assert result[0]['floating'] is True

    def test_nightly_tag(self):
        content = "FROM python:nightly\nRUN echo hello"
        result = parse_dockerfile_bases(content)
        assert result[0]['floating'] is True

    def test_multi_stage(self):
        content = (
            "FROM golang:1.21 AS build\nRUN echo build\n"
            "FROM alpine:3.18\nRUN echo runtime"
        )
        result = parse_dockerfile_bases(content)
        assert len(result) == 2
        assert result[0]['alias'] == 'build'
        assert result[1]['tag'] == '3.18'
        assert result[1]['floating'] is False

    def test_platform_flag(self):
        content = "FROM --platform=linux/amd64 node:20-slim\nRUN echo hello"
        result = parse_dockerfile_bases(content)
        assert len(result) == 1
        assert result[0]['image'] == 'node'


class TestFindDockerfileBasesDrift:
    def test_clean_pinned(self):
        dockerfiles = {"Dockerfile": "FROM node:20-slim\nRUN echo hello"}
        result = find_dockerfile_bases_drift(dockerfiles)
        assert result == []

    def test_floating_latest_detected(self):
        dockerfiles = {"Dockerfile": "FROM node:latest\nRUN echo hello"}
        result = find_dockerfile_bases_drift(dockerfiles)
        assert len(result) == 1
        assert result[0]['image'] == 'node'
        assert result[0]['tag'] == 'latest'

    def test_implicit_latest_detected(self):
        dockerfiles = {"Dockerfile": "FROM node\nRUN echo hello"}
        result = find_dockerfile_bases_drift(dockerfiles)
        assert len(result) == 1
        assert '(none)' in result[0]['tag']

    def test_sibling_different_versions(self):
        dockerfiles = {
            "Dockerfile.dev": "FROM node:18\nRUN echo dev",
            "Dockerfile.prod": "FROM node:20\nRUN echo prod",
        }
        result = find_dockerfile_bases_drift(dockerfiles)
        assert len(result) >= 1
        sibling = [r for r in result if 'pinned differently' in r.get('detail', '')]
        assert len(sibling) == 1
        assert set(sibling[0]['tags']) == {'18', '20'}

    def test_sibling_same_versions_no_drift(self):
        dockerfiles = {
            "Dockerfile.dev": "FROM node:20\nRUN echo dev",
            "Dockerfile.prod": "FROM node:20\nRUN echo prod",
        }
        result = find_dockerfile_bases_drift(dockerfiles)
        assert result == []

    def test_multiple_floating(self):
        dockerfiles = {
            "Dockerfile": "FROM python:latest\nRUN echo hello\nFROM alpine:3.18\nRUN echo second"
        }
        result = find_dockerfile_bases_drift(dockerfiles)
        floating = [r for r in result if 'floating' in r.get('detail', '')]
        assert len(floating) == 1
        assert floating[0]['image'] == 'python'

    def test_mixed_floating_and_sibling(self):
        dockerfiles = {
            "Dockerfile.dev": "FROM node:18\nRUN echo dev",
            "Dockerfile.prod": "FROM node:latest\nRUN echo prod",
        }
        result = find_dockerfile_bases_drift(dockerfiles)
        # node:latest is floating + siblings differ
        assert len(result) >= 2
