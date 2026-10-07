"""Regression guard: the docs build must publish a populated sitemap.

The hosted site at https://yunaremaia.github.io/driftcheck/ shipped an empty
sitemap for months:

    <?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    </urlset>

Cause: ``mkdocs.yml`` had no ``site_url``. mkdocs writes ``sitemap.xml``
unconditionally, but only fills it with ``<url>`` entries when ``site_url`` is
set -- and a build with an empty sitemap is still a green build. That is the
whole failure mode: nothing was red, so nothing got fixed.

This module guards the config half, in a form the test suite can actually run:
``mkdocs`` and ``PyYAML`` are deliberately NOT dependencies of this project, so
a test that imported either would fail in CI's ``test`` job. It therefore parses
``mkdocs.yml`` as text and asserts the properties that make sitemap generation
produce entries.

The build half -- that a real ``mkdocs build`` emits one entry per nav page --
lives in ``scripts/check_docs_sitemap.py``, which runs in the ``docs`` CI job
where mkdocs is installed. That split is deliberate: this file fails fast in
every one of the 13 matrix legs without a heavyweight dependency, while the
script checks the artifact that actually gets deployed.

The helpers are imported lazily inside the tests so a syntax error or a renamed
helper here cannot abort collection for the rest of the suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
DOCS_DIR = REPO_ROOT / "docs"
SITEMAP_CHECK = REPO_ROOT / "scripts" / "check_docs_sitemap.py"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: Where the site is actually published. Must match the Pages URL reported by
#: the API (`html_url`), not a guess: a site_url pointing somewhere else fills
#: the sitemap with URLs nobody can visit, which is a different silent failure.
PUBLISHED_SITE_URL = "https://yunaremaia.github.io/driftcheck/"


@pytest.fixture(scope="module")
def mkdocs_text() -> str:
    return MKDOCS_YML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sitemap_helpers():
    """Load the parsing helpers from the CI script.

    Imported by path because ``scripts/`` is not a package. Reusing one
    implementation for both the suite and CI means the guard cannot disagree
    with the check that actually gates the deploy.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_docs_sitemap", SITEMAP_CHECK)
    assert spec and spec.loader, f"cannot load {SITEMAP_CHECK}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_site_url_is_configured(sitemap_helpers, mkdocs_text):
    """The root cause: no site_url means an empty urlset.

    Asserted through the same parser CI uses, so a formatting change that
    hides the key from one also hides it from the other.
    """
    site_url = sitemap_helpers.parse_site_url(mkdocs_text)

    assert site_url, (
        "mkdocs.yml defines no site_url. mkdocs still writes sitemap.xml, but "
        "as a valid yet EMPTY urlset, and emits no canonical link tags -- so "
        "the site stays invisible to sitemap-based discovery with a green "
        "build. Set site_url to the published Pages URL."
    )


def test_site_url_is_https_and_matches_published_site(sitemap_helpers, mkdocs_text):
    """A wrong site_url produces a full sitemap full of dead links.

    Filling the sitemap is not enough: every entry is built by joining
    site_url to each page path, so a typo, a missing trailing slash or an
    `http://` scheme yields a populated sitemap that points at the wrong host.
    """
    site_url = sitemap_helpers.parse_site_url(mkdocs_text)

    assert site_url, "mkdocs.yml defines no site_url"
    assert site_url.startswith("https://"), (
        f"site_url is {site_url!r}; GitHub Pages is served over HTTPS, so an "
        "http:// sitemap entry would be a mixed-content downgrade"
    )
    assert site_url.endswith("/"), (
        f"site_url is {site_url!r}; without a trailing slash mkdocs joins "
        f"paths as '{site_url}<page>/' instead of under a directory"
    )
    assert site_url == PUBLISHED_SITE_URL, (
        f"site_url is {site_url!r} but the site is published at "
        f"{PUBLISHED_SITE_URL!r}; every sitemap entry and canonical tag would "
        "point at the wrong host"
    )


def test_nav_targets_exist_under_docs(sitemap_helpers, mkdocs_text):
    """Every nav page must exist, or the sitemap omits it silently.

    A nav entry pointing at a missing file is not a crash here (mkdocs warns
    and drops the page) -- it is a page that never reaches the sitemap.
    """
    nav_targets = sitemap_helpers.parse_nav_targets(mkdocs_text)

    assert nav_targets, "mkdocs.yml defines no nav: entries to check"
    missing = [t for t in nav_targets if not (DOCS_DIR / t).is_file()]
    assert not missing, f"nav targets missing from docs/: {missing}"


def test_every_nav_page_gets_a_sitemap_entry(sitemap_helpers, mkdocs_text):
    """One <url> per nav page -- the property the sitemap must actually have.

    This derives the URLs mkdocs publishes each page at and checks each is
    covered. It is the suite-level counterpart of the real build check: it
    cannot prove the sitemap is populated, but it pins the mapping so the
    artifact check has a fixed expectation to compare against.
    """
    site_url = sitemap_helpers.parse_site_url(mkdocs_text)
    assert site_url, "mkdocs.yml defines no site_url"

    nav_targets = sitemap_helpers.parse_nav_targets(mkdocs_text)
    expected = sitemap_helpers.expected_urls(site_url, nav_targets)

    assert expected, "no sitemap URLs derived from nav:"
    # The home page must map to the site root, not to /index/.
    assert expected[0] == site_url, (
        f"first nav entry maps to {expected[0]!r}, not the site root "
        f"{site_url!r}"
    )
    assert len(expected) == len(nav_targets)
    assert len(set(expected)) == len(expected), (
        f"duplicate sitemap URLs derived from nav: {expected}"
    )


def test_docs_job_verifies_the_built_sitemap():
    """The `docs` job must check the artifact, not just build it.

    `mkdocs build` exits 0 with an empty sitemap, so without this step the CI
    suite is blind to the exact regression it is meant to prevent. The build is
    the only place mkdocs exists, which is why the check lives here rather than
    in the test matrix.
    """
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    assert SITEMAP_CHECK.is_file(), (
        f"{SITEMAP_CHECK.name} is missing: the docs job would build a site "
        "without verifying its sitemap"
    )
    assert "scripts/check_docs_sitemap.py" in source, (
        "no CI step runs scripts/check_docs_sitemap.py; the deployed sitemap "
        "is unverified"
    )

    # The check must run before the artifact is uploaded, or a failing build is
    # still published.
    check_at = source.index("scripts/check_docs_sitemap.py")
    upload_at = source.index("upload-pages-artifact")
    assert check_at < upload_at, (
        "the sitemap check runs after upload-pages-artifact, so a site with an "
        "empty sitemap would already be published by the time it fails"
    )


def test_sitemap_check_fails_on_an_empty_sitemap(tmp_path, mkdocs_text):
    """The deployed check must actually bite on an empty sitemap.

    Executed, not inspected: a check that returns 0 on a hand-built empty
    urlset would leave the deploy ungated while this suite reported green.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(SITEMAP_CHECK),
            "--repo-root",
            str(REPO_ROOT),
            "--site-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    # No sitemap.xml was written into tmp_path at all.
    assert result.returncode != 0, (
        "the sitemap check passed against a site directory containing no "
        "sitemap.xml"
    )
    assert "sitemap.xml was not produced" in result.stderr


def test_sitemap_check_fails_on_an_empty_urlset(tmp_path, sitemap_helpers, mkdocs_text):
    """A valid-but-empty urlset is the regression; it must be rejected.

    This is the precise artifact that shipped: well-formed XML, zero entries.
    A check that merely parsed the file would accept it.
    """
    (tmp_path / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "</urlset>\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SITEMAP_CHECK),
            "--repo-root",
            str(REPO_ROOT),
            "--site-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, (
        "the sitemap check accepted a zero-entry urlset, which is exactly the "
        "artifact that was published"
    )
    assert "zero <url> entries" in result.stderr


def test_sitemap_check_fails_when_a_nav_page_is_absent(tmp_path, sitemap_helpers, mkdocs_text):
    """A sitemap missing one nav page must fail, not merely be non-empty.

    Guards against a check that only asserts "the sitemap has some entries":
    dropping a single page would still leave the other seven and go unnoticed.
    """
    site_url = sitemap_helpers.parse_site_url(mkdocs_text)
    nav_targets = sitemap_helpers.parse_nav_targets(mkdocs_text)
    assert site_url and nav_targets

    # Build a sitemap covering every nav page but the last one.
    published = sitemap_helpers.expected_urls(site_url, nav_targets)[:-1]
    body = "".join(f"    <url><loc>{url}</loc></url>\n" for url in published)
    (tmp_path / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}"
        "</urlset>\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SITEMAP_CHECK),
            "--repo-root",
            str(REPO_ROOT),
            "--site-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    omitted = sitemap_helpers.expected_urls(site_url, nav_targets)[-1]
    assert result.returncode != 0, (
        f"the sitemap check accepted a sitemap missing {omitted}"
    )
    assert f"no entry for {omitted}" in result.stderr


def test_sitemap_check_passes_on_the_real_build(tmp_path, sitemap_helpers, mkdocs_text):
    """Positive control: a complete sitemap must exit 0.

    Without this, a check that always returns 1 would satisfy every failure
    test above and gate every future deploy on a false alarm.
    """
    site_url = sitemap_helpers.parse_site_url(mkdocs_text)
    nav_targets = sitemap_helpers.parse_nav_targets(mkdocs_text)
    assert site_url and nav_targets

    body = "".join(
        f"    <url><loc>{url}</loc></url>\n"
        for url in sitemap_helpers.expected_urls(site_url, nav_targets)
    )
    (tmp_path / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}"
        "</urlset>\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SITEMAP_CHECK),
            "--repo-root",
            str(REPO_ROOT),
            "--site-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"the sitemap check rejected a complete sitemap:\n{result.stderr}"
    )


def test_sitemap_check_script_has_no_third_party_imports():
    """It runs as a bare script in CI, so only the stdlib may be imported.

    Importing yaml or mkdocs here would work on this machine (both are
    installed for the docs build) and fail in the job that runs it.
    """
    source = SITEMAP_CHECK.read_text(encoding="utf-8")
    imports = [
        line.split()[1].split(".")[0]
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    forbidden = {"yaml", "mkdocs"}
    assert not forbidden.intersection(imports), (
        f"{SITEMAP_CHECK.name} imports {sorted(forbidden.intersection(imports))}, "
        "which are not installed in the docs job"
    )


def test_pyproject_does_not_add_docs_build_deps_to_the_test_matrix():
    """mkdocs must stay out of the runtime deps.

    It is installed explicitly by the docs job. Adding it to `[project]
    dependencies` would pull a documentation toolchain into every one of the 13
    matrix legs to protect against a two-line config guard.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dependencies_block = pyproject.split("dependencies = [", 1)[-1].split("]", 1)[0]

    assert "mkdocs" not in dependencies_block, (
        "mkdocs was added to the runtime dependencies; it belongs to the docs "
        "job only"
    )


def test_site_url_matches_pyproject_documentation_urls():
    """The sitemap URLs and the packaging metadata must name the same host.

    pyproject already advertises the site in project.urls. If the sitemap's
    site_url drifts from it, visitors are directed to a different site than the
    one PyPI sends them to.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    homepage = None
    for line in pyproject.splitlines():
        stripped = line.strip()
        if stripped.startswith("Homepage"):
            homepage = stripped.split("=", 1)[-1].strip().strip('"').rstrip(",")
            break

    assert homepage, "pyproject.toml has no Homepage project URL to compare"
    assert homepage == PUBLISHED_SITE_URL, (
        f"pyproject Homepage is {homepage!r} but mkdocs.yml site_url is "
        f"{PUBLISHED_SITE_URL!r}"
    )


def test_no_absolute_local_paths_in_mkdocs_config():
    """A machine-specific path would break the docs build elsewhere.

    Guards the same failure class -- a build that succeeds on one machine and
    produces something else on another -- for the config this PR now makes
    load-bearing for sitemap URLs.
    """
    text = MKDOCS_YML.read_text(encoding="utf-8")

    for marker in (os.sep + "root" + os.sep, os.sep + "home" + os.sep, "C:" + os.sep):
        assert marker not in text, (
            f"mkdocs.yml contains the absolute path fragment {marker!r}"
        )


def test_site_description_is_configured(sitemap_helpers, mkdocs_text):
    """The root cause: no site_description means no <meta name="description">.

    mkdocs writes the tag only when site_description is set. Without it the
    build is still green and search engines get no snippet -- the same silent
    shape as the empty sitemap, one tag over.
    """
    site_description = sitemap_helpers.parse_site_description(mkdocs_text)

    assert site_description, (
        "mkdocs.yml defines no site_description, so mkdocs emits no "
        '<meta name="description"> and search results have no snippet to show. '
        "Set it to pyproject.toml's description."
    )


def test_site_description_matches_pyproject(sitemap_helpers, mkdocs_text):
    """site_description must be the description the package already ships.

    The expected value is read from pyproject.toml rather than written here: a
    hand-copied string cannot notice the copy drifting, and a hardcoded list of
    accepted values cannot notice the value missing from it.
    """
    expected = _pyproject_description()
    actual = sitemap_helpers.parse_site_description(mkdocs_text)

    assert expected, "pyproject.toml has no description field"
    assert actual == expected, (
        f"mkdocs.yml site_description is {actual!r} but pyproject.toml "
        f"description is {expected!r}: the docs site would describe the tool "
        "differently from the package that links to it"
    )


def test_theme_custom_dir_points_at_the_overrides_directory(sitemap_helpers, mkdocs_text):
    """og:/twitter: tags need theme.custom_dir; material emits none on its own."""
    custom_dir = sitemap_helpers.parse_custom_dir(mkdocs_text)

    assert custom_dir, (
        "mkdocs.yml theme has no custom_dir, so overrides/main.html is never "
        "loaded and no og:/twitter: meta tags are emitted"
    )
    assert (REPO_ROOT / custom_dir).is_dir(), (
        f"mkdocs.yml theme.custom_dir is {custom_dir!r} but that directory does "
        "not exist in the repository"
    )


def test_overrides_template_is_tracked_and_references_the_og_tags(sitemap_helpers, mkdocs_text):
    """The override must exist, be tracked, and emit every tag the site needs.

    The tag list comes from the same constant the CI check uses, so the suite
    and the deploy gate cannot disagree about what "has social metadata" means.
    """
    custom_dir = sitemap_helpers.parse_custom_dir(mkdocs_text)
    assert custom_dir, "mkdocs.yml theme has no custom_dir"

    override = REPO_ROOT / custom_dir / "main.html"
    assert override.is_file(), (
        f"{override.relative_to(REPO_ROOT)} is missing; without it mkdocs "
        "emits no Open Graph tags"
    )

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(override.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{override.relative_to(REPO_ROOT)} is not tracked by git: the CI docs "
        "job builds from the repository, so an ignored override would produce a "
        "site with no social metadata and a green build"
    )

    content = override.read_text(encoding="utf-8")
    for marker, label in sitemap_helpers.REQUIRED_META_TAGS:
        # The template writes the attribute itself, so compare on the tag name
        # rather than on the rendered attribute quoting.
        tag_name = marker.split('"')[1]
        assert tag_name in content, (
            f"overrides/main.html does not reference {tag_name}, so the built "
            f"HTML will have no {label}"
        )


def test_home_page_title_does_not_use_an_undefined_page_attribute(sitemap_helpers, mkdocs_text):
    """A page attribute that does not exist renders as the "Home" placeholder.

    mkdocs-material exposes ``page.is_homepage``; testing a near miss such as
    ``page.is_home`` yields undefined, the else branch runs, and the home page
    -- the one page every link preview of the site resolves to -- ships titled
    "Home - <site>". Exercised against rendered HTML fixtures because a real
    build does not fail, it just publishes the wrong title.
    """
    custom_dir = sitemap_helpers.parse_custom_dir(mkdocs_text)
    override = (REPO_ROOT / custom_dir / "main.html").read_text(encoding="utf-8")

    for near_miss in ("page.is_home ", "page.is_home %}", "page.is_home %"):
        assert near_miss not in override, (
            f"overrides/main.html tests {near_miss.strip()!r}, which "
            "mkdocs-material does not define; Jinja renders it as undefined and "
            'the home page ships with the placeholder title "Home - <site>" '
            "instead of the project name"
        )

    site_name = sitemap_helpers.parse_site_name(mkdocs_text)

    def head_with_title(title: str) -> str:
        return (
            "<head>"
            '<meta name="description" content="a description" />'
            '<meta property="og:type" content="website" />'
            f'<meta property="og:title" content="{title}" />'
            '<meta property="og:description" content="a description" />'
            '<meta property="og:url" content="https://example.test/" />'
            '<meta name="twitter:card" content="summary" />'
            "</head>"
        )

    assert not sitemap_helpers.meta_tag_failures(
        head_with_title(site_name), site_name, "index.html"
    ), "a correctly titled home page must pass the meta tag check"

    failures = sitemap_helpers.meta_tag_failures(
        head_with_title(f"Home - {site_name}"), site_name, "index.html"
    )
    assert any("og:title" in failure for failure in failures), (
        f"the meta tag check does not flag a home page titled 'Home - "
        f"{site_name}'; the guard would not catch the bug it exists for"
    )


def test_docs_job_runs_the_metadata_check():
    """The check has to run where mkdocs is installed, or it never runs.

    The test job has no mkdocs, so a config-only guard here cannot prove the
    built HTML. The docs job is the only place the artifact exists; if that
    step is dropped the guard silently stops executing.
    """
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "check_docs_sitemap.py" in workflow, (
        "the docs job no longer runs scripts/check_docs_sitemap.py, so nothing "
        "verifies the built HTML for social metadata"
    )
    assert "mkdocs build" in workflow, (
        "the docs job no longer builds the site; the sitemap and meta tag "
        "checks would run against a stale or absent site/"
    )


def test_meta_tag_check_ignores_tags_outside_the_head(sitemap_helpers):
    """A tag in <body> is not read by a crawler or a link preview."""
    html = (
        "<head><title>x</title></head>"
        '<body><meta property="og:title" content="nope" /></body>'
    )

    assert "og:title" not in sitemap_helpers.parse_meta_tags(html)


def _pyproject_description() -> str:
    """The `description` value of pyproject.toml, read as text.

    Read as text for the same reason the module reads mkdocs.yml that way: this
    suite must run in every matrix leg without adding a parser dependency, and
    the layout differs between the checkout and the sdist.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in pyproject.splitlines():
        stripped = line.strip()
        if stripped.startswith("description =") and not stripped.startswith(
            "description = ["
        ):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
