# Public launch preparation

This is a publication checklist and draft copy, not a claim that a release or promotion has happened.

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

- [ ] Merge reviewed repository documentation and check CI on the default branch.
- [x] Fix the known false-success and bot/window selection issues with regression coverage.
- [x] Implement an experimental standalone existing-window pre-expiry state machine.
- [ ] Complete live acceptance of that implementation and clean-Mac end-to-end deployment.
- [ ] Capture a new, explicitly recorded demo; remove account names, bot IDs, links and enterprise content. Do not label a reenactment as the original live run.
- [ ] Publish a versioned release with exact supported conditions and validation scope.
- [ ] Add useful reproduction evidence to relevant upstream/community discussions when a maintainer chooses to share it. Avoid repetitive promotional posts.

## Draft announcement (中文)

我们在用 wecom-cli 做后台文档自动化时遇到一个问题：访问 token 能刷新，但业务能力授权会在七天后到期，任务因此中断。

wecom-auth-keeper 尝试用 macOS 企业微信桌面自动化处理授权恢复。最近实机验证了未到期预续期：在“已授权”下拉中取消后重新授权，文档读写有效期都延长到七天后，重开页面复核一致。

当前仓库支持到期恢复脚本；预续期已有实验性现有窗口状态机，管理列表导航和新版真实账号验收仍待完成。欢迎有同类场景的开发者参与导航、状态验证和跨周期测试。

https://github.com/fyaic/wecom-auth-keeper

## Draft announcement (English)

We built wecom-auth-keeper after seven-day business permission expiry interrupted our WeCom CLI document workflows. It uses macOS desktop automation to interact with the authorization UI.

A live desktop-agent session has now demonstrated pre-expiry renewal: revoke an existing document permission, re-grant it, and verify a new seven-day expiry after reopening the page. The repository currently implements renewal after expiry; an experimental existing-window pre-expiry implementation is now available, with live acceptance and automatic management-page navigation still pending.

We welcome reproducibility reports and contributions to navigation, state validation and multi-cycle testing.

https://github.com/fyaic/wecom-auth-keeper
