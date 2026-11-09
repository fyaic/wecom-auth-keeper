## 2026-11-06 本机真实验收与企业切换修复

- 修正 5.0.13 企业菜单入口、切换后窗口重建和当前企业菜单关闭逻辑；精确企业行及选中标记核验，未知版本停止。
- 保留双 Bot 身份验证与多权限提前续期/冷却/关页；两个 Bot 的四项权限经过 launchd 实际预续期。
- 分发包加入验收证据；Windows 明确未实现 UIA，不宣称跨平台可用。

# Changelog

## Unreleased

### First-run Bot and chat entry preparation — 2026-11-09

- Recover exact official renewal URLs from existing authorized CLI profiles; do not reinitialize because a scope expired or a chat is missing. Preserve native URL parameters in both installer and legacy Bridge link delivery.
- Recognize creator-only, organization and deleted-Bot errors inside the identity-bound permission page. Stop before permission actions, retain the original reason through cleanup, and document a temporary own-account diagnostic carrier without treating it as a Bot-chat or renewal pass.
- Separate first-time Bot selection/binding, organization verification and private-chat link preparation from recurring renewal; do not search history before an entry exists.
- Add a private one-time message generator (never sends) and a GUI launchd entry verifier that starts from another chat/organization, checks the selected CLI identity and official page, reads configured rows, and closes the page.
- New onboarding configs block maintenance and schedule generation until their device/config-bound entry receipt exists; existing deployed configs are not migrated automatically. Persist both CLI and Node paths for launchd, verified against two existing profiles under a minimal PATH on the remote Mac.
- Record the installer’s private-chat provenance separately from machine-verified chat title/link/navigation; keep first grants, real renewal and scheduled execution as distinct acceptance stages.
- Harden authorization actions to live controls inside the bound page, with no mouse fallback. Allow passive existing-page inspection and bound page cleanup without changing legacy Bridge.
- Recognize the native contacts Bot directory reached by “查看更多机器人”: AXOutline rows and Bot badges, distinct from management cards. Report visible candidates without exposing contact names or claiming full enumeration/identity verification.
- Allow native-only GUI inspection before Bot configuration exists, using an explicit execution Python; it lists visible Bot candidates without permitting renewal, messages or grants. Permit empty candidate-chat navigation when needed to inspect identity, while keeping identity verification before sending.
- Document “更多 → 通讯录 → 智能机器人” for portals without “查看更多机器人”; independently navigate five remote organizations with before/after native selection checks. Directory discovery remains separate from Bot identity and renewal acceptance.
- These are internal preview changes. The new first-run flow and remote unattended renewal still require live acceptance; unit tests do not establish business release readiness.

### Remote acceptance fixes — 2026-11-06

- Apply optional Bridge monitor coordination to scheduled maintenance, including navigation and window cleanup. The supervising parent holds the desktop lock and restores the prior mode after worker timeout.
- Record restoration errors as failures instead of reporting a successful cycle.
- Use a dedicated cleanup child after timeout so cleanup does not reacquire the supervising parent's desktop lock.
- Prefer a locally verified authorization link in the target Bot's private chat; require reopening it from another conversation in device acceptance.
- Remote device acceptance is still in progress; these changes do not establish general macOS compatibility.

### Agent-assisted distribution preview — 2026-11-06

- Audit all branches against main 1722b10; preserve existing production worktrees and deployment state.
- Add portable device detection, identity-checked private macOS configuration, an agent installation runbook and business-user handoff.
- Build a source ZIP from an explicit committed allowlist with a manifest and external checksum; exclude business-specific configuration and raw AX diagnostic tools.
- Document Windows backend design and acceptance gates without claiming Windows automation support or current multi-organization reliability.


### Reusable multi-permission scheduling — 2026-10-23

- Add standalone `maintain.py`: default hourly scheduling and a 24-hour pre-expiry window for an explicit combination of capability labels, without Gateway or Codex dependencies.
- Persist each permission's progress, cooldown and pre-action intent; prioritize pending recovery, reconcile completed grants after interruptions, and retain exponential failure backoff.
- Hold the shared desktop lock through navigation, renewal, verification and cleanup; bound the GUI worker lifetime with a supervisor and attempt cleanup after timeouts.
- Add capability discovery, historical status, a minimal multi-permission config and launchd generation. Legacy document probes remain unchanged; GUI evidence never claims business verification.


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
