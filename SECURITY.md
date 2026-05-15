# Security Policy

## Supported versions

The format specification is frozen at v1.0; the reference library is
at 0.1.x and may have breaking API changes between releases. Security
fixes target the `main` branch and the most recent released tag.

| Version          | Supported |
|------------------|-----------|
| `main`           | yes       |
| latest 0.1.x tag | yes       |
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

- **Manifest integrity.** Every file in the bundle is SHA-256 hashed
  and compared against the manifest. Any mismatch must fail
  verification. This is normative (spec §2).
- **Schema validation.** Malformed pillars must be rejected, not
  silently defaulted. Unknown fields are preserved on round-trip but
  do not gain meaning.
- **Reflex sandbox.** If a bundle declares symbolic reflex conditions,
  the evaluator uses an AST whitelist (no `exec`, no `eval`, no
  attribute access on arbitrary objects). A reflex condition cannot
  escape into the host process.
- **Neuronshard numerical bounds.** The LIF integrator clamps inputs
  and resets on spike, so a malicious neuronshard cannot drive the
  runtime into NaN / Inf storms that would waste CPU indefinitely
  past the configured tick budget.
- **Zip handling.** The loader caps total decompressed size and
  refuses zip entries with absolute or traversal paths (`/foo`,
  `../foo`, drive letters on Windows).

### Out of scope

- **LLM prompt safety.** SHARDCORE does not ship an LLM. If a
  downstream app feeds soulshard/mindshard text into an LLM, prompt
  injection inside that text is that app's problem. We do not sanitize
  free-form character prose for you.
- **Image / media content.** Bundles may reference image paths in
  shellshard (`identity_image_path`, `appearance_image_path`). The
  library does not fetch, decode, or validate these. Treat them like
  any other untrusted URL.
- **Private key material inside bundles.** We do not define a place
  in the spec for bundles to ship credentials, and we do not
  recommend you put any there.
- **Side-channel attacks** on the SHA-256 verification (timing,
  cache). These are out of scope for a file-format library.

## Known sharp edges

These are documented and intentional (not vulnerabilities), but worth
naming.

- **Skill payloads are experimental.** The v1.0 spec leaves the
  `skills/` folder experimental. A skill can declare behavior a
  runtime may execute; treat skills from untrusted bundles as code
  and sandbox them accordingly. We will tighten this in v1.1.
- **Verify before tick.** `python -m shardcore neuron <bundle>`
  currently trusts the caller to have run `verify` first. A bundle
  whose manifest disagrees with its contents can still be ticked if
  you skip the verify step. We will fold verify into the neuron
  entry point in a follow-up release.
- **No bundle-level signature.** v1.0 guarantees internal
  integrity (contents match manifest) but does not carry an author
  signature. If you need to prove origin, wrap the bundle in a
  detached signature yourself.

## Hardening checklist for downstream apps

If you are integrating `shardcore` as a library, please:

1. Always call `verify` before using a bundle for anything other
   than inspection.
2. Pin the `shardcore` version in your lockfile. The tick engine's
   exact numerical output is part of the spec, but we may improve
   error messages or loader ergonomics across patch versions.
3. If your app lets users import arbitrary bundles from the network,
   log the SHA-256 of the entire bundle alongside any diagnostic
   output. It makes later forensics much easier.
4. Treat every string field in every pillar as arbitrary user input
   before feeding it to any other system (databases, shells, LLMs,
   template engines).

## Credits

Responsibly disclosed issues are credited in the release notes of the
version that fixes them, unless the reporter asks to remain anonymous.
