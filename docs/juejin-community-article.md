离开电脑后，我想在企业微信里给 Agent 发一张报错截图，接着问项目问题，或者收到任务完成通知。

为此，我们做了两个开源项目：一个负责接入，一个研究办公权限到期后的恢复。先看区别：

| 项目 | 做什么 | 什么时候需要 |
| --- | --- | --- |
| [wecom-agent-gateway](https://github.com/fyaic/wecom-agent-gateway) | 连接已有 Agent 与企业微信 | 想在私聊、群聊里使用 Agent |
| [wecom-auth-keeper](https://github.com/fyaic/wecom-auth-keeper) | 用 Mac 桌面脚本维护指定业务授权 | 调用文档、通讯录等能力，遇到七天到期 |

**两者可以独立使用。普通 Bot 聊天不需要先装续期工具。**

## 先看企微里的效果

下面是 Gateway 接入 Pi 的真实演示，包括流式回复、显式确认、任务恢复和主动通知。

![真实企业微信与 Pi Agent 演示](https://raw.githubusercontent.com/fyaic/wecom-agent-gateway/main/docs/assets/demo/wecom-agent-gateway-demo.gif)

[查看高清 MP4](https://github.com/fyaic/wecom-agent-gateway/blob/main/docs/assets/demo/wecom-agent-gateway-demo.mp4)。普通聊天默认不附卡片，演示中的确认来自显式交互。

Gateway 负责消息收发、会话、去重和持久投递。用哪个模型、怎么登录、执行哪些工具，仍由已有 Agent 管理。

```text
企业微信私聊 / 群聊
        ↕
WeCom Agent Gateway
        ↕ Adapter
你已有的 Agent
        ↓ 可选
wecom-cli → 文档、通讯录等办公能力

Auth Keeper → Mac 上的业务权限授权页
```

## 哪些 Agent 已经接过？

| Agent | 接入方式 | 当前证据 |
| --- | --- | --- |
| Codex | Codex Adapter | 有真实企微接入记录 |
| Kimi Code | ACP | 有真实企微接入记录 |
| Pi | Pi Adapter | 有真实企微接入记录 |
| OpenClaw | 连接已有 Gateway | 有真实企微接入记录 |
| 自研 Agent | 实现公共 SDK 的 Adapter | 提供模板，需要自行验收 |

[各 Adapter 的详细验证记录](https://github.com/fyaic/wecom-agent-gateway/blob/main/docs/verified-kernel-cases.md)。图片、文件、交互卡片等能力因 Adapter 和模型而异。

这里的“可扩展接入”不等于任意 Agent 都能即插即用。它会创建或恢复 Gateway 管理的会话，不会直接接管你桌面 App 中打开的任务；更换 Agent 也不会自动迁移聊天记忆。

想先看看链路怎么跑，可以执行本地演示：

```bash
git clone https://github.com/fyaic/wecom-agent-gateway.git
cd wecom-agent-gateway
pnpm install --frozen-lockfile
pnpm demo
```

环境需要 Node.js 22.x（≥22.19）、24.x 或 ≥26，以及 pnpm 11.8.0。当前部署面向 macOS / Linux。

`demo` 使用本地 Echo，不调用模型、不连接企微。真正接入时，再按 [快速开始](https://github.com/fyaic/wecom-agent-gateway#快速开始) 配置已有 Agent、Bot 和私聊认领。

项目仍是 Public Preview。一个 Bot 只运行一个 Gateway，投递为 at-least-once，不能承诺绝不重复；主动消息也只面向已授权会话。

## 接通之后，还有一个七天问题

如果 Agent 进一步调用 wecom-cli 的文档、通讯录等业务能力，就需要单独关注能力授权。

Bot 在线、token 能刷新，都不能证明某项办公能力仍有权限。官方社区里也有人反馈：[文档写操作返回 850003，读操作却正常](https://github.com/WecomTeam/wecom-cli/issues/134)。

我们的尝试很直接：在 Mac 的正常授权界面上，把指定权限取消后重新授权，再检查有效期是否更新。Auth Keeper 做的就是这段桌面操作，不提供私有续期 API。

### 一次实测的结果

2026 年 9 月 22 日，macOS 企业微信 `5.0.11.99998`，Python 3.14、PyObjC 12.2.2：

| 已有授权 | 操作前有效期 | 操作后及重开页面复查 |
| --- | --- | --- |
| 新建与编辑文档 | 9/22 18:39 | 9/29 16:18 |
| 搜索与获取文档内容 | 9/22 18:39 | 9/29 16:18 |
| 搜索企业成员 | 9/22 18:39 | 9/29 16:18 |

以上时间均为北京时间。页面预先由桌面代理打开，逐项取消、重授和检查由独立脚本完成。未选中的消息权限保持原日期。

**这次确认的是界面有效期更新，没有运行续期后的业务 API 复探。** [完整实测记录](https://github.com/fyaic/wecom-auth-keeper/blob/main/docs/validation.md)。

### 可以只选文档和通讯录吗？

可以，用 `target_rows` 白名单。例如只读文档和通讯录：

```json
{
  "target_rows": [
    "搜索与获取文档内容",
    "搜索企业成员"
  ]
}
```

需要写文档时，再加入 `新建与编辑文档`。未列出的行不会操作；白名单只应包含你明确愿意授予的能力，因为“授权”按钮也可能对应从未授权的权限。

完整配置和命令见 [复现指南](https://github.com/fyaic/wecom-auth-keeper/blob/main/docs/workaround.md)。预续期默认处理 24 小时内到期项，更远的有效授权会跳过。

## 现在适合谁试？

- 已经有能独立运行的 Agent，想增加企微入口：先试 Gateway。
- 已经遇到业务权限到期，又有可操作的 Mac：再评估 Auth Keeper。
- 只有 Linux 服务器，希望全程无人值守续期：当前桌面实验还不能满足。

续期仍需登录状态和预先打开的正确权限页，取消期间存在短暂权限缺口。消息权限、锁屏运行、跨七天周期稳定性尚未验收；每小时 keepalive 示例做的是到期后文档探针恢复，并非定时预续期。

两个项目还没有完成组合后的端到端续期验收，也不是一键联动套件。

仓库都已开放，欢迎提交接入问题、Adapter 或复现记录：

- [wecom-agent-gateway](https://github.com/fyaic/wecom-agent-gateway)
- [wecom-auth-keeper](https://github.com/fyaic/wecom-auth-keeper)

> 本文由两个项目的维护者借助 AI 整理，功能及实测范围核对于 2026-09-23。演示与数据来自仓库已有记录；未验证的部分已单独说明。
