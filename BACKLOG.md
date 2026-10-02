# Backlog

Curated list of open work, grouped by kind. Every entry here is an issue that is
still open and still actionable as written.

Last batch triage: 2026-10-02 (see [Triage log](#triage-log)).

## Refactors

| Issue | Title | Notes |
|-------|-------|-------|
| [#141](https://github.com/yunaremaia/driftcheck/issues/141) | Reduce `scan_repo()` cyclomatic complexity | Absorbs the older per-function decomposition asks. |
| [#147](https://github.com/yunaremaia/driftcheck/issues/147) | Remove dead `_read_files_parallel()` | One function, zero callers. Small. |
| [#191](https://github.com/yunaremaia/driftcheck/issues/191) | Introduce `DriftFinding`/`DetectorResult` dataclasses | Prerequisite for typed SARIF output and per-finding severity. |
| [#236](https://github.com/yunaremaia/driftcheck/issues/236) | Decompose `cli.py` into submodules | |

## Performance

| Issue | Title | Notes |
|-------|-------|-------|
| [#120](https://github.com/yunaremaia/driftcheck/issues/120) | Incremental cache to skip unchanged files | Canonical cache issue. |
| [#240](https://github.com/yunaremaia/driftcheck/issues/240) | Read each toolchain file once in `scan_repo()` | Canonical I/O-dedup issue. Pairs with #120. |

## Fix-path safety

`--fix` rewrites documentation in place. These three bound the blast radius.

| Issue | Title | Notes |
|-------|-------|-------|
| [#177](https://github.com/yunaremaia/driftcheck/issues/177) | Backup/restore for `--fix` | Canonical backup issue. |
| [#214](https://github.com/yunaremaia/driftcheck/issues/214) | `--fix-deny` list | Land this before widening fix coverage. |
| [#186](https://github.com/yunaremaia/driftcheck/issues/186) | `fix.py` corrupts files on non-version matches | Confirmed: `replace(old, new, 1)` at `src/driftcheck/detectors/fix.py:144,156`. |
| [#197](https://github.com/yunaremaia/driftcheck/issues/197) | Bidirectional `--fix` with direction auto-detection | |

## Bug fixes (verified on `main`)

| Issue | Title | Evidence |
|-------|-------|----------|
| [#143](https://github.com/yunaremaia/driftcheck/issues/143) | `_parse_toml` fails on inline comments and multi-line arrays | Reproduced against `src/driftcheck/config.py:57`. |
| [#295](https://github.com/yunaremaia/driftcheck/issues/295) | `_print_informational` drops `typosquat_drifts` | `INFORMATIONAL_DRIFTS` at `src/driftcheck/cli.py:17` lists it; `_print_informational` never prints it. |
| [#301](https://github.com/yunaremaia/driftcheck/issues/301) | `_detect_detectors` rglobs the whole repo for YAML | `src/driftcheck/cli.py:174,176`. |

## Security

| Issue | Title | Notes |
|-------|-------|-------|
| [#140](https://github.com/yunaremaia/driftcheck/issues/140) | Replace silent `except Exception` handlers | Partly landed (#309); remaining sites listed in the issue. |
| [#177](https://github.com/yunaremaia/driftcheck/issues/177) | Backup/restore for `--fix` | See above. |
| [#189](https://github.com/yunaremaia/driftcheck/issues/189) | Symlink containment for intra-repo cross-references | Paired with #235. |
| [#344](https://github.com/yunaremaia/driftcheck/issues/344) | Supply chain risk detector | Typosquat half exists; dependency confusion and unmaintained do not. |

## Output and reporting

| Issue | Title | Notes |
|-------|-------|-------|
| [#152](https://github.com/yunaremaia/driftcheck/issues/152) | Severity levels in SARIF output | Pairs with #234. |
| [#195](https://github.com/yunaremaia/driftcheck/issues/195) | SARIF `codeFlows`/`threadFlow` | |
| [#234](https://github.com/yunaremaia/driftcheck/issues/234) | Drift severity classification per detector | Depends on #191. |
| [#249](https://github.com/yunaremaia/driftcheck/issues/249) | JSON Schema for `.driftcheck.toml` | |
| [#288](https://github.com/yunaremaia/driftcheck/issues/288) | SARIF suppressions for accepted drift | Canonical suppressions issue. |

## Scanning modes and config

| Issue | Title | Notes |
|-------|-------|-------|
| [#119](https://github.com/yunaremaia/driftcheck/issues/119) | Watch mode | |
| [#124](https://github.com/yunaremaia/driftcheck/issues/124) | Config validation subcommand | `doctor` already covers unknown keys (`src/driftcheck/doctor.py:119`); the subcommand itself is new. |
| [#131](https://github.com/yunaremaia/driftcheck/issues/131) | Monorepo support | |
| [#176](https://github.com/yunaremaia/driftcheck/issues/176) | Normalized version matching | False-positive reduction. |

## Detectors

Ecosystems with no coverage today. Each follows the pattern in
`docs/detectors.md` and the `driftcheck-detector-pattern` skill: a `find_*`
function, a `scan_repo()` key, an `__init__.py` export, and a test file.

| Issue | Ecosystem | Size |
|-------|-----------|------|
| [#313](https://github.com/yunaremaia/driftcheck/issues/313) | AI-generated content markers | S |
| [#315](https://github.com/yunaremaia/driftcheck/issues/315) | Monorepo dependency consistency | M |
| [#321](https://github.com/yunaremaia/driftcheck/issues/321) | Pixi environments | M |
| [#332](https://github.com/yunaremaia/driftcheck/issues/332) | Windows CI (AppVeyor, Azure Pipelines) | M |
| [#337](https://github.com/yunaremaia/driftcheck/issues/337) | API version drift | M |
| [#352](https://github.com/yunaremaia/driftcheck/issues/352) | C/C++ package managers (vcpkg, Conan, Meson) | M |
| [#353](https://github.com/yunaremaia/driftcheck/issues/353) | Haskell / Cabal | M |
| [#363](https://github.com/yunaremaia/driftcheck/issues/363) | GitHub Actions reusable workflows | S |
| [#365](https://github.com/yunaremaia/driftcheck/issues/365) | Docker image tag drift across three files | M |

## Tests and docs

| Issue | Title |
|-------|-------|
| [#93](https://github.com/yunaremaia/driftcheck/issues/93) | Real-world drift examples in the README |
| [#250](https://github.com/yunaremaia/driftcheck/issues/250) | Property-based testing with `hypothesis` |
| [#358](https://github.com/yunaremaia/driftcheck/issues/358) | Detector prioritization roadmap |

## Triage log

**2026-10-02 — batch triage of 77 open issues.**

The backlog had grown into a detector wishlist that had largely been built
already. Rather than reviewing 77 issues one at a time, the batch was grouped
by category and each group verified against the source tree:

- `grep` for the detector or symbol named in the issue body across
  `src/driftcheck/`, then a real call into the function, then the dedicated
  test file. A claim was only accepted as implemented if the test file existed
  and passed.
- End-to-end confirmation through the installed CLI: a purpose-built fixture
  repo per ecosystem, run with `driftcheck --json --only <detector>`, with the
  emitted finding quoted in the closing comment.
- Full suite run on `main` before and after: 1593 passed.

Outcome:

| Category | Count |
|----------|-------|
| Closed as implemented (`completed`) | 28 |
| Closed as duplicate (`not planned`) | 11 |
| Closed as not this repository (`not planned`) | 1 |
| Left open | 37 |
| Closed as contradicted by design | 0 |

77 open at the start, 40 closed, 37 remaining. Nothing was closed as contradicted
or out of date: every close names a source file, a test file, the issue it
duplicates, or the repository the work actually belongs to. Two issues (#143,
#147) were left open with a comment recording that a CHANGELOG entry claims they
were already fixed when no code changed.

Two CHANGELOG claims did not survive verification and are worth flagging:

- "Replaced hand-rolled TOML parser with `tomllib` (#151)" — commit `070dccc`
  carries that message but is empty; `_parse_toml()` is still hand-rolled and
  still has the inline-comment and multi-line-array defects (#143).
- "Removed ... dead `_read_files_parallel` (#146, #147)" — commit `dffd414`
  removed the `drifts` alias but not the function; it is still defined at
  `src/driftcheck/detector.py:246` with no callers (#147).

Two duplicate labels existed, `good first issue` and `good-first-issue`.
Issues using the misspelled variant were moved to the canonical one.
