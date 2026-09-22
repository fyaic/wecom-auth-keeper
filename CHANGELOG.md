# Changelog

## Unreleased

### Runtime hardening — 2026-09-22

- Built-in PyObjC adapter with pinned native dependencies; bridge source is no longer required.
- Lazy GUI imports, local doctor, explicit authorization evidence and bot-bound windows.
- Experimental `--pre-renew --existing-window` with a due-time threshold, durable pending-recovery record, and recovery before processing another permission.
- Process-lifetime locks, post-operation atomic state, scoped confirmations and negative coordinate support.
- Python probe/keepalive runners with CLI path discovery, bounded subprocesses, structured errors, verified recovery and deduplicated optional notifications.
- Cross-platform regression tests plus native geometry tests on macOS.
- Incorporated upstream September 21 production observations without conflating them with the new implementation.

**Migration:** shell wrappers now output one JSON object and return nonzero on failure. `--check` no longer sends messages or changes monitor mode. Configure `venv_python` for this repository's native environment. See [setup](docs/getting-started.md).

**Validation boundary:** the new state machine is covered by automated failure tests; live reauthorization and automatic management-page navigation remain pending.

### Repository preparation — 2026-09-21

- Reorganized Chinese and English entry points, setup and project status.
- Added a live pre-expiry renewal record with before/after expiry times and explicit verification limits.
- Documented known runtime issues and a staged acceptance roadmap.
- Completed probe fields in the example configuration.
- Added community guidelines, issue/PR templates and credential-free repository checks.

The September 21 repository-preparation change did not alter runtime behavior; the September 22 update above does.

## Initial source snapshot — 2026-09-15

The initial commit introduced expired-permission renewal, CLI probes, a launchd example and authorization-model notes. “v1.0” in the original documentation describes that source snapshot; this changelog does not imply a GitHub release or tag was published.
