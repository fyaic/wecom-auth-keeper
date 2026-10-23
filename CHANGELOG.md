# Changelog

## Unreleased

### Native history navigation — 2026-10-23

- Add opt-in `chat_history_navigation`: locate the configured chat through native search, verify its heading,
  search its history for an existing official authorization link, and retain both Bot identifiers and page checks.
- Add `--close-window` for identity-verified native window cleanup without navigation or overwriting health/recovery evidence. Gateway can invoke it after a complete cycle.
- Document the tested 5.0.12.95037 Chinese client and explicitly leave older-client compatibility unverified; navigation stays opt-in.
- No link messages or bridge service are needed for this route. Existing-window-only mode remains strict.
- Guard keyboard input with foreground/window/search-field checks; preserve pasteboard formats and concurrent copies.
- Validate a complete launchd pre-renewal for the existing message capability on WeCom 5.0.12, followed by a same-Bot
  read-only business probe; install hourly maintenance with a 24-hour pre-renew window. See [validation](docs/validation.md).

### Live validation and documentation — 2026-09-22

- Validated standalone document read/write and contacts pre-renewal on WeCom `5.0.11.99998`: all three expiries changed from September 22 18:39 to September 29 16:18, verified after reopening the page.
- Filter windowless duplicate processes, distinguish contacts headings from repeated descriptions, scroll controls into the verified page viewport, and allow mouse events to settle.
- Added regression coverage (44 local tests passed) and permission-selection examples.
- Aligned Chinese/English guides with the live evidence and documented the temporary workaround. Hourly keepalive remains post-expiry recovery, not pre-expiry scheduling.

### Runtime hardening — 2026-09-22

- Built-in PyObjC adapter with pinned native dependencies; bridge source is no longer required.
- Lazy GUI imports, local doctor, explicit authorization evidence and bot-bound windows.
- Experimental `--pre-renew --existing-window` with a due-time threshold, durable pending-recovery record, and recovery before processing another permission.
- Process-lifetime locks, post-operation atomic state, scoped confirmations and negative coordinate support.
- Python probe/keepalive runners with CLI path discovery, bounded subprocesses, structured errors, verified recovery and deduplicated optional notifications.
- Cross-platform regression tests plus native geometry tests on macOS.
- Incorporated upstream September 21 production observations without conflating them with the new implementation.

**Migration:** shell wrappers now output one JSON object and return nonzero on failure. `--check` no longer sends messages or changes monitor mode. Configure `venv_python` for this repository's native environment. See [setup](docs/getting-started.md).

**Validation boundary:** the new state machine is covered by automated failure tests; live existing-window reauthorization is now recorded above; automatic management-page navigation, business API revalidation and multi-cycle operation remain pending.

### Repository preparation — 2026-09-21

- Reorganized Chinese and English entry points, setup and project status.
- Added a live pre-expiry renewal record with before/after expiry times and explicit verification limits.
- Documented known runtime issues and a staged acceptance roadmap.
- Completed probe fields in the example configuration.
- Added community guidelines, issue/PR templates and credential-free repository checks.

The September 21 repository-preparation change did not alter runtime behavior; the September 22 update above does.

## Initial source snapshot — 2026-09-15

The initial commit introduced expired-permission renewal, CLI probes, a launchd example and authorization-model notes. “v1.0” in the original documentation describes that source snapshot; this changelog does not imply a GitHub release or tag was published.
