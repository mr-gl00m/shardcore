# Security Policy

## Supported versions

The format specification is at v1.9; the reference library is at 1.9.x and
may have breaking API changes between minor releases. Security fixes target
the `main` branch and the most recent released tag.

| Version          | Supported |
|------------------|-----------|
| `main`           | yes       |
| latest 1.9.x tag | yes       |
| older            | no        |

## Reporting a vulnerability

Email **security@shardcore.dev** with the details. If PGP matters to
you, mention that in your first message and we will arrange a key
exchange before you send the payload.

Please do **not** open a public GitHub issue for a vulnerability before
we have had a chance to respond. "Vulnerability" here means anything a
malicious bundle or malicious runtime could do that the spec or
library did not intend: code execution, sandbox escape, resource
exhaustion beyond documented limits, manifest-integrity bypass.

What to include:

- The bundle, or a minimal reconstruction that triggers the issue.
- The exact command, output, and Python + OS version.
- Your estimate of severity and why.
- Whether you want attribution in the eventual advisory.

We aim to acknowledge within 72 hours and to ship a fix or a public
advisory within 30 days. Coordinated disclosure is the default; we
will not publicize before a fix is available unless the reporter
asks us to.

## Threat model

The spec and the reference library treat a `.shard` as **untrusted
input**. A bundle arrives over a network, off a USB stick, or from a
stranger's git repo, and a conformant runtime must either load it
safely or refuse it with a clear error.

### In scope for this project

- **Manifest integrity.** Every file the manifest lists is SHA-256 hashed
  and compared against its declared digest. Any mismatch must fail
  verification. This is normative (spec section 9).
- **Schema validation.** Malformed pillars must be rejected, not
  silently defaulted. Unknown fields and unowned `x_*` namespaces are
  preserved on round-trip but do not gain meaning.
- **No extraction, no zip-slip.** The reader reads members into memory by
  name and never builds a filesystem path from a member name, so a hostile
  entry like `../evil.json` has no extraction path to escape through. A
  reader that does extract to disk MUST resolve each member against the
  extraction root and reject absolute paths, traversal, and symlinks.
- **Atomic, reversible writes.** The library writes a bundle to a temp file
  and `os.replace`s it into position, so a crash mid-write cannot leave a
  half-written `.shard`. A `manifest.immutable` bundle is never written in
  place. The full backup-and-restore-on-failure envelope belongs to a batch
  migration tool that wraps the library.
- **Reflex sandbox.** If a bundle declares symbolic reflex or validation
  conditions, the evaluator uses an AST whitelist (no `exec`, no `eval`, no
  attribute access, no imports, no subscripts, no comprehensions). A
  condition cannot escape into the host process.
- **Neuronshard numerical bounds.** The LIF integrator clamps inputs and
  resets on spike, so a malicious neuronshard cannot drive the runtime into
  NaN / Inf storms past the configured tick budget.
- **Bundle size cap.** The reader caps the bundle size it will load into
  memory rather than opening an unbounded archive.

### Out of scope

- **LLM prompt safety.** SHARDCORE does not ship an LLM. If a downstream app
  feeds soulshard or mindshard text into an LLM, prompt injection inside
  that text is that app's problem. We do not sanitize free-form character
  prose for you.
- **Image / media content.** Bundles may carry assets under `assets/` and
  reference image paths in shellshard. The library does not fetch, decode,
  or validate media. Treat referenced paths like any other untrusted URL.
- **Private key material inside bundles.** We do not define a place in the
  spec for bundles to ship credentials, and we do not recommend you put any
  there.
- **Side-channel attacks** on the SHA-256 verification (timing, cache).
  These are out of scope for a file-format library.

## Known sharp edges

These are documented and intentional (not vulnerabilities), but worth
naming.

- **Skill payloads are experimental.** v1.9 keeps skills under `assets/`
  experimental. A skill can declare behavior a runtime may execute; treat
  skills from untrusted bundles as code and sandbox them accordingly.
- **Verify before tick.** `python -m shardcore neuron <bundle>` trusts the
  caller to have run `verify` first. A bundle whose manifest disagrees with
  its contents can still be ticked if you skip the verify step.
- **Integrity, not authorship.** SHA-256 proves internal integrity (contents
  match the manifest), not origin. The optional `attestation` and `lineage`
  manifest fields carry provenance when present, but a bare bundle is
  unsigned. If you need to prove origin, require an attestation or wrap the
  bundle in a detached signature.
- **App writers can down-convert.** A first-party app that has not yet been
  routed through this library may re-save a bundle with the legacy manifest
  layout. That is a compatibility regression, not a security issue; run
  `shardcore migrate` to restore v1.9.

## Hardening checklist for downstream apps

If you are integrating `shardcore` as a library, please:

1. Always call `verify` (or `read_bundle` + integrity check) before using a
   bundle for anything other than inspection.
2. Pin the `shardcore` version in your lockfile. The tick engine's exact
   numerical output is part of the spec, but error messages and loader
   ergonomics may change across patch versions.
3. If your app lets users import arbitrary bundles from the network, log the
   SHA-256 of the entire bundle alongside any diagnostic output. It makes
   later forensics much easier.
4. Treat every string field in every pillar as arbitrary user input before
   feeding it to any other system (databases, shells, LLMs, template
   engines).

## Credits

Responsibly disclosed issues are credited in the release notes of the
version that fixes them, unless the reporter asks to remain anonymous.
