# Contributing to SHARDCORE

Thanks for reading this far. This document covers three things: how to
propose a change to the **spec**, how to propose a change to the
**reference library**, and how to file a bug or compatibility report.

The two halves move on different clocks. The spec changes slowly and
deliberately, because it is a contract between independent implementations. The
library moves faster, as long as it remains conformant.

---

## TL;DR

- **Bugs / compatibility issues**: open a GitHub issue with a minimal
  reproduction and the output of `python -m shardcore diagnose <bundle>`.
- **Library PRs**: fork, branch, install the dev extras, write a failing
  test, make it pass, open a PR.
- **Spec changes**: open a `spec:` issue first with a short RFC.
  Do not open a spec PR before the RFC has rough consensus.

---

## Dev setup

Requirements: Python 3.10 or newer. The only runtime dependency is
`numpy` (needed for the neuron substrate; the bundle I/O core is
standard-library only). The dev extras add `pytest` and `ruff`.

```bash
git clone https://github.com/mr-gl00m/shardcore.git
cd shardcore

# with uv (recommended)
uv venv
uv pip install -e ".[dev]"

# or with venv + pip
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the full check locally before opening a PR:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m shardcore verify examples/standard.shard
python -m shardcore diagnose examples/standard.shard
```

The CI matrix runs this on ubuntu / macos / windows x Python 3.10 to 3.13.
A PR that fails on one OS but passes on another is still failing.

---

## Proposing a library change

Scope that fits the reference library:

- Reader, verifier, diagnoser, and migration correctness, and clearer
  error messages.
- The migration chain: new migrations, idempotence and loss-free fixes.
- The schema-id registry: mapping new members to schema ids.
- Neuronshard runtime: numerical fixes, small performance wins that do
  not change observable output.
- Conformance tests, especially bundles we currently mis-classify that
  the spec says we should reject or migrate.
- Docs, typos, readable examples.

Scope that does **not** fit here and belongs in a downstream app:

- LLM integration, prompt assembly, chat UIs.
- Persistent session storage beyond bundle I/O.
- GUI or web surfaces.
- The full batch-migration safety envelope (backup, run-log, rollback).
  The library exposes atomic `migrate_bundle`; a tool wraps it.

Process:

1. Open an issue if the change is non-trivial (more than ~20 lines or
   touches public API). Describe the problem first, the fix second.
2. Write a failing test. This is the most load-bearing rule in this
   document. A behavior change without a test is a behavior change
   nobody will notice regressing later.
3. Keep the PR focused. One logical change per PR.
4. Update `CHANGELOG.md` under the `## [Unreleased]` section.

### Commits and messages

We do not enforce a specific commit-message format. We do ask that the
subject line reads as an imperative sentence ("fix manifest digest
comparison", not "fixed" or "fixes"), and that the body explains **why**
when the reason is not obvious from the diff.

Squash or merge is up to the maintainer at merge time.

---

## Proposing a spec change

The spec is **normative**. A byte-for-byte disagreement between two
conformant runtimes is a bug, and the thing we optimize for is that a
second implementer can read the spec once and build against it.

That makes spec changes expensive. Please do not open a spec PR cold.

### RFC flow

1. Open an issue titled `spec: <short summary>`. Include:
   - What the current spec says.
   - What you want it to say.
   - The concrete use case that motivates the change.
   - Any runtime-compatibility impact (does this break v1.0 or v1.9
     bundles?).
2. Discussion happens on the issue. Other implementers get a chance to
   weigh in.
3. If there is rough consensus, the change lands as a PR against
   `SHARDCORE_Spec_v1.9.md` (for clarifications that do not change
   behavior) or as a new optional pillar (a new row in the pillar
   registry with its own `schema` id) for additive changes, with a
   milestone update in `ROADMAP.md`.
4. Normative changes **must** ship alongside conformance tests that
   exercise them. A spec change with no test is a footnote, not a
   contract.

### What counts as a breaking spec change

- Removing a required field from any pillar.
- Changing the meaning (not just the wording) of an existing field.
- Changing the manifest integrity algorithm.
- Changing Neuronshard serialization in a way that breaks
  round-trip of pre-existing bundles.

Breaking changes do not land in v1.x. They go on the roadmap for a
future major version and require explicit backward-compatibility notes.
Additive changes (a new optional pillar, a new schema id) stay within
the v1 line.

---

## Reporting compatibility issues

A "compatibility issue" is: **a bundle that one conformant runtime
accepts and another conformant runtime rejects**, or the reverse.

These are the highest-priority bugs in this project because they are
the failure mode the spec exists to prevent.

When filing one, please include:

- The bundle (or a minimal reconstruction of it).
- The exact command and output from each runtime.
- Which runtime you believe is correct, and why.

If you cannot share the bundle itself, a trimmed-down reproduction that
still exhibits the disagreement is acceptable.

---

## Code of conduct

By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Do not open a public issue for a security vulnerability. See
[SECURITY.md](SECURITY.md) for the disclosure process.
