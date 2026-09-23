# Public launch preparation

Publication checklist and reusable announcement copy. Upstream replies are recorded below; no versioned release is claimed.

## Positioning

**WeCom CLI permission renewal through macOS desktop automation.**

For developers whose scheduled document workflows stop when business permissions expire. The strongest demonstration is the observed expiry timestamp moving seven days forward after revoke/re-grant, followed by a reopened-page verification.

Do not claim zero downtime, official support, cross-platform operation, fully automatic pre-expiry navigation, or a success rate without evidence.

## Repository discovery

Suggested About description:

> WeCom CLI permission renewal via macOS desktop automation. 企业微信七天能力授权续期：到期恢复与预续期实机验证。

Suggested Topics: `wecom`, `wecom-cli`, `wechat-work`, `macos`, `desktop-automation`, `accessibility`, `python`, `authorization`, `automation`.

GitHub explains [community profiles](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories) and [repository topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics). These improve clarity and discovery; they do not guarantee traffic or stars.

## Before wider promotion

- [x] Merge repository documentation and verify Linux/macOS CI.
- [x] Fix the known false-success and bot/window selection issues with regression coverage.
- [x] Implement an experimental standalone existing-window pre-expiry state machine.
- [x] Complete single-account existing-window live renewal of document read/write and contacts.
- [ ] Complete clean-Mac deployment, business API revalidation and multi-cycle operation.
- [ ] Capture a new, explicitly recorded demo; remove account names, bot IDs, links and enterprise content. Do not label a reenactment as the original live run.
- [ ] Publish a versioned release with exact supported conditions and validation scope.
- [x] Share targeted reproduction evidence in upstream #138 and #134 (2026-09-22).

## Draft announcement (中文)

我们在用 wecom-cli 做后台文档自动化时遇到一个问题：访问 token 能刷新，但业务能力授权会在七天后到期，任务因此中断。

wecom-auth-keeper 尝试用 macOS 企业微信桌面自动化处理授权恢复。最近实机验证了未到期预续期：在“已授权”下拉中取消后重新授权，独立脚本将文档读写和通讯录三项有效期更新为操作时刻七天后，重开页面复核一致。

当前仓库支持到期恢复脚本；预续期已有实验性现有窗口状态机，目标行自动滚动已实现，管理列表导航、业务 API 复探和跨周期验收仍待完成。欢迎有同类场景的开发者参与导航、状态验证和跨周期测试。

https://github.com/fyaic/wecom-auth-keeper

## Draft announcement (English)

We built wecom-auth-keeper after seven-day business permission expiry interrupted our WeCom CLI document workflows. It uses macOS desktop automation to interact with the authorization UI.

The standalone script has demonstrated pre-expiry renewal of document read/write and contacts on an already-open permissions page, verified after reopening it. Controls scroll automatically. Navigation into that page was assisted; business API revalidation, clean-Mac deployment and multi-cycle operation remain pending. Hourly keepalive handles post-expiry recovery, not proactive renewal.

We welcome reproducibility reports and contributions to navigation, state validation and multi-cycle testing.

https://github.com/fyaic/wecom-auth-keeper


## Published upstream replies — 2026-09-22

- [wecom-cli #138: temporary desktop workaround and prerequisites](https://github.com/WecomTeam/wecom-cli/issues/138#issuecomment-5773557352)
- [wecom-cli #134: document read/write renewal evidence and verification limits](https://github.com/WecomTeam/wecom-cli/issues/134#issuecomment-5773558029)

Both replies disclose the community project relationship, distinguish UI expiry renewal from business API verification, and retain the request for official permission observability and renewal support. Message permission renewal was not tested and is not claimed.


## External community follow-up — 2026-09-22

Published and verified: [shiliai/dsh-plugins #53 — authorization monitoring and renewal](https://github.com/shiliai/dsh-plugins/issues/53#issuecomment-5773806927).

The issue explicitly reports a one-week authorization lifetime. Its completed watchdog work covers token/connection failures and 90-day data-permission reminders. Our follow-up adds evidence for the separate seven-day bot capability authorization layer and links the [temporary desktop workaround](workaround.md), without claiming to replace that watchdog or the 90-day callback flow.

The reply discloses our relationship to this project and the tested document read/write and contacts scope. It states that an interactive, logged-in Mac and an already-open target permissions page are required, revocation creates a temporary permission gap, and business API revalidation and multi-cycle operation remain unverified.

Searches covered GitHub Issues and Discussions using Chinese and English terms for WeCom CLI, authorization expiry, renewal, seven-day permissions and `850003`. Other inspected threads concerned document-reader integration, token refresh, message history or WebSocket bridges rather than this renewal need; no promotional replies were posted there. Previously answered upstream issues were not posted to again. This search is a dated snapshot, not an exhaustive inventory or an ongoing monitor.


## Official status and follow-up — 2026-09-23

- [Official support review](official-status.md): npm 1.3.2, official documentation and pinned source review found no documented unattended renewal path for seven-day capability grants. Token refresh remains distinct.
- Published and verified [wecom-cli #87 follow-up](https://github.com/WecomTeam/wecom-cli/issues/87#issuecomment-5788396913): current auth command/refresh implementation and the community experiment. The reply explicitly states that message permission renewal has not been live-tested.
- Searched issues mentioning wecom-cli and reviewed downstream integration threads. No additional external thread with a confirmed expiry requirement was found in this pass; existing replies in #138, #134 and dsh-plugins #53 were not repeated.
- Excluded [wecom-openclaw-plugin #148](https://github.com/WecomTeam/wecom-openclaw-plugin/issues/148) (forbidden MCP tool, no expiry evidence), [#28](https://github.com/WecomTeam/wecom-openclaw-plugin/issues/28) (document membership), [pi #184](https://github.com/TGYD-helige/pi/issues/184) (resolved command/skill compatibility, Windows), and [CowAgent #2866](https://github.com/zhayujie/CowAgent/issues/2866) (MCP/CLI integration inquiry). These are not demonstrated fixes for this project's desktop renewal path.


## Downstream scheduled-notification discussion — 2026-09-23

Published and verified: [LazyAGI/LazyMind #758 — scheduled multi-channel notifications](https://github.com/LazyAGI/LazyMind/pull/758#issuecomment-5788505443).

The open PR discusses WeCom CLI provider rejection classification and login renewal. Its `wecom/service.py` handles outer/inner `853004` with token refresh, while other business errors become a generic request failure. The reply suggests retaining a sanitized capability-reauthorization reason for `850003` and adding regression cases for both response envelopes. It is a prospective integration consideration, not a claim that LazyMind has a reproduced expiry failure.

The comment links this community project as an optional desktop recovery reference, discloses maintainership, and explicitly excludes verified LazyMind integration, message-permission renewal and Compose/Linux compatibility. No second reply was added to earlier upstream/community threads.

This pass expanded searches to authorization expiry, weekly operation, CLI failures and scheduled workflows across Issues, PR discussions and GitHub Discussions. Generic OAuth, trial tokens and unrelated integration topics were not treated as evidence of this specific renewal need.


## Downstream adoption and further outreach — 2026-09-23

LazyMind's PR author [confirmed adopting the error-classification suggestion](https://github.com/LazyAGI/LazyMind/pull/758#issuecomment-5789451671). We inspected [commit e8fe3d76](https://github.com/LazyAGI/LazyMind/commit/e8fe3d7693e413c03f3a3e972b98161a24c311d9): both `850003` response envelopes map to `WECOM_CAPABILITY_REAUTH_REQUIRED`, the worker preserves that reason, and Chinese/English UI text asks for reauthorization. Regression cases assert a failed result, sanitized diagnostics and exactly one send attempt. The author reports 233 passing gateway tests; we reviewed the diff but did not independently run their suite. This is adoption of error handling advice, not integration or validation of this project's renewal runtime. Published and verified our [acknowledgment](https://github.com/LazyAGI/LazyMind/pull/758#issuecomment-5790074053).

Two additional directly relevant discussions received tailored replies:

- [CoreMan #50](https://github.com/wxkingstar/CoreMan/pull/50#issuecomment-5790074587): the merged PR documents per-member capability grants, seven-day expiry reminders and desktop-only renewal. Our reply offers the experiment for a member's own logged-in Mac, emphasizes robot identity and explicit permission selection, and does not suggest one shared desktop can renew every member's grants. CoreMan integration remains unverified.
- [agentcore-notifier #7](https://github.com/cloud2ai/agentcore-notifier/pull/7#issuecomment-5790075049): the merged PR reports actual seven-day message authorization expiry followed by repeated send failures and adds a self-built-app channel. Our reply acknowledges that approach and offers this experiment only as a reference for remaining AI Bot users. Message permission renewal and notifier integration remain untested.

Both replies disclose project maintainership and link the reproduction guide. They retain the interactive-Mac and preopened-page requirements, temporary revocation gap, and pending business API/multi-cycle verification. Published bodies were read back through the GitHub API and compared with their drafts.

Searches also covered `850003`, seven-day grants and recent Chinese authorization-expiry discussions across issues and PR comments. HoeTee/wecom-aibot #5 mentions stopping on expiry, but received no reply in this pass; broad token/integration matches were not used for outreach. This record is a dated search snapshot, not an ongoing monitor.


## Document-workflow recovery follow-up — 2026-09-23

Published and verified: [HoeTee/wecom-aibot #5](https://github.com/HoeTee/wecom-aibot/pull/5#issuecomment-5790221478). The PR explicitly stops on `850003` instead of looping; its README describes document/smart-sheet workflows using a remote MCP endpoint. Our reply preserves that fail-fast behavior and suggests checking the previous write outcome before replaying an append.

The reply discloses maintainership and links the desktop experiment, but explicitly distinguishes their remote MCP path from our tested CLI path. Matching error codes alone do not prove a shared authorization object: the operator must first establish that the MCP uses the same bot and desktop-managed grants. No integration or post-renewal smart-sheet write has been verified. Interactive macOS, an already-open correct permissions page, the temporary revocation gap and pending API/multi-cycle verification remain stated limitations. The published comment was fetched and matched against its draft.

This pass searched Chinese/English renewal, reauthorization, seven-day and `850003` terms in issue bodies and comments, including PR discussions. Additional inspected candidates received no comment:

- WecomTeam/wecom-unified #6/#7 and desirecore/market #136 discuss chat-history windows and corporation/document access boundaries, not demonstrated grant renewal needs.
- tobby888/Photolib #73 implements self-built-app access-token refresh; multica-ai/multica #6590 handles WebSocket acknowledgments.
- GnaixEuy/threadferry #10 concerns migration to per-agent bot credentials; CherryHQ/cherry-studio-app #917 describes gateway integration/token renewal without a demonstrated seven-day expiry report.
- awesome-dsh-plugin/awesome-dsh-plugin #1191 concerns listing accuracy and approval identity checks.

Previously contacted threads were not reposted to. This is a bounded search snapshot; it does not establish that all relevant discussions have been found.


## Joint Gateway / Auth Keeper article — 2026-09-23

Prepared [a Chinese community article](agent-to-wecom-story.md) introducing Gateway as the Agent-to-WeCom middleware and Auth Keeper as an optional desktop experiment for selected business capability grants. It explicitly distinguishes supported reference Adapters from arbitrary plug-and-play compatibility, basic Bot chat from CLI business authorization, and complementary projects from a tested integrated suite.

Suggested title for a standalone community post:

> 把已有 Agent 接入企业微信，再处理七天授权到期：两个开源项目的实践

Short introduction for a relevant discussion, after checking its context:

> 我们维护了两个互补的开源项目：[wecom-agent-gateway](https://github.com/fyaic/wecom-agent-gateway) 把已有 Agent 接入企业微信，Codex、Kimi、Pi、OpenClaw 有真实接入记录，自研 Agent 可通过 Adapter 扩展；[wecom-auth-keeper](https://github.com/fyaic/wecom-auth-keeper) 则实验性地通过 macOS 授权界面维护指定业务权限，已实测文档读写和通讯录的界面有效期更新。基础聊天不需要 Auth Keeper；续期仍需已登录 Mac 和预开的正确权限页，业务 API 复探、消息权限和跨周期运行尚未验收。两个项目还没有完成组合后的端到端续期验证。[完整实践与边界](agent-to-wecom-story.md)。

The article is available in this repository. No Linux.do, V2EX, Zhihu, Juejin or X publication is recorded by this entry; preparing copy is not a confirmed external publication.


## Juejin submission — 2026-09-23

Submitted [把 Codex、Pi 接入企业微信，顺手试了七天权限续期](https://juejin.cn/spost/7688401277181345842) through the signed-in author UI. The platform displayed publication success; the author article page then displayed **审核中 (under review)**. This is a confirmed submission, not confirmation of public approval or discoverability.

The [submitted body](juejin-community-article.md) uses short paragraphs, three comparison/results tables, the existing real Gateway/Pi GIF, a high-resolution demo link and a text flow diagram. Category: 人工智能; tag: Agent. It includes both project links, explicit verification limits and an AI-assisted preparation disclosure. The author page was read back to confirm the title, tables and outbound links. No new live renewal test was performed for this article.

Linux.do was excluded after reading its current guidelines: open-source promotional posts prohibit AI-generated or AI-polished text. No post was submitted there.
