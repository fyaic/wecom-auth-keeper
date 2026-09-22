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
