# Consolidated main publication

Date: 2026-10-23. Owner explicitly authorized publishing the current combined
work to main, with a follow-up requirement to keep private information out.
Scope: M0–M4 accumulated implementation and current US-01/02 conversation policy;
this publication does not complete deferred carrier, latency, notification or
production acceptance gates.

## Snapshot and history

All 23 pre-publication local branch tips were ancestors of the working branch;
there were no separate unmerged implementations. The accumulated work was saved
on the existing branch, then squash-integrated onto origin/main in a publication
branch. The staged tree matched the saved working tree before adding this report
and correcting stale CI documentation. Original local branches are preserved.
Only the consolidated main commit is intended for publication; local agent session
checkpoint refs and unpublished author metadata are excluded. The new commit uses
a GitHub noreply author/committer address. Existing remote history is not rewritten.
The already-staged workflow deletion is preserved; hosted CI remains unconfigured.

## Privacy review

- The 215-file source/asset candidate excludes private .local configuration,
  captures, real recordings, databases, caches and build outputs.
- detect-secrets 1.5.0 ran locally with network verification disabled. Its 73
  findings were reviewed: public model/file hashes and the explicit example
  database credential placeholder, not live secrets.
- Exact comparison on Linux against seven distinct private configuration and
  database-derived values found no matches. Local private connection values
  also had no matches. Values were neither printed nor added to the report.
- Credential-format, phone/address/path and private-transcript literal checks
  found no private content. Number-like hits were synthetic fixtures or hashes;
  a network-like version was a pinned dependency version.
- WAV assets are documented generated speech fixtures/openings, not caller
  recordings. Product-approved owner/assistant names remain in product content.
- Secret scanners cannot prove absence of every possible private datum; these
  are concrete checks of the outgoing snapshot, not a universal guarantee.

## Validation

Linux native build completed with no pending work; all nine CTests passed in
2.32 s. Ruff lint and formatting (53 Python files), clang-format, and handwritten
source whitespace checks passed. The full staged diff reports the pinned gRPC
generator's final blank line in voice.grpc.pb.cc; disabling only blank-at-eof
passes. Keep canonical generated output instead of hand-editing it.
All six generated protobuf files were byte-identical
after regeneration. The first regeneration attempt lacked uv in the noninteractive
PATH; it was rerun with the documented user tool directory and passed.
The complete Linux pytest run passed: 255 passed in 815.44 s, no skips, with
one known Python audioop deprecation warning. No carrier call, new GPU inference
benchmark or hosted CI run is claimed by this publication check.
