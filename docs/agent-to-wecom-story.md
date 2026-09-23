# 把已有 Agent 接入企业微信，再处理七天授权到期：两个开源项目的实践

> 作者维护本文中的两个社区项目。Gateway 处于 Public Preview；权限续期是有条件的 macOS 桌面实验。功能与验证范围核对于 2026-09-23。

在电脑上跑 Agent 很方便，但离开电脑后，我更希望在企业微信里继续提问、发一张报错截图，或收到任务完成通知。等到 Agent 开始调用文档、通讯录等办公能力，又出现另一个问题：接入成功并不意味着业务授权会一直有效。

我们把这两件事分别做成了开源项目：

- [wecom-agent-gateway](https://github.com/fyaic/wecom-agent-gateway)：连接企业微信与已有 Agent 的独立中间层。
- [wecom-auth-keeper](https://github.com/fyaic/wecom-auth-keeper)：通过 macOS 企业微信正常授权界面，尝试恢复或提前更新指定业务能力授权。

两个项目可以独立使用。基础聊天不需要先安装 Auth Keeper，Gateway 的首次私聊也不依赖 wecom-cli。

## 先让已有的 Agent 在企微里可用

Gateway 负责企业微信消息收发、会话映射、流式输出、去重与持久投递；模型选择、登录、推理和工具执行仍由你已有的 Agent 管理。

```text
企业微信私聊 / 群聊
        ↕
WeCom Agent Gateway
        ↕ Adapter
Codex / Kimi Code / Pi / OpenClaw / 自研 Agent
        ↓ 可选办公工具
wecom-cli → 文档、通讯录等业务能力

Auth Keeper → 在 macOS 权限页维护选定能力的授权
```

目前 Codex、Kimi Code、Pi、OpenClaw 都有真实企微接入记录。自研 Agent 可以实现公共 SDK 的 Adapter；已有 ACP 接口的 harness 可以评估 ACP 接入。因此，“连接不同 Agent”是扩展能力，并不意味着输入任何 Agent 名称就能即插即用。图片、文件、交互卡片等能力也需要按 Adapter 和模型确认。

仓库提供了[真实企业微信与 Pi 的演示](https://github.com/fyaic/wecom-agent-gateway/blob/main/docs/assets/demo/wecom-agent-gateway-demo.mp4)和[逐 Agent 验证记录](https://github.com/fyaic/wecom-agent-gateway/blob/main/docs/verified-kernel-cases.md)。连接会创建或恢复 Gateway 管理的会话，不会自动接管桌面 App 或终端中已打开的任务；切换 Agent 也不会自动迁移聊天记忆。

想先了解运行方式，可以从本地演示开始：

```bash
git clone https://github.com/fyaic/wecom-agent-gateway.git
cd wecom-agent-gateway
pnpm install --frozen-lockfile
pnpm demo
```

需要 Node.js 22.x（≥22.19）、24.x 或 ≥26，以及 pnpm 11.8.0；当前部署路径面向 macOS / Linux。演示使用 Echo 和真实 Core、SQLite、Adapter 加载器，不连接企业微信、不调用模型。它能帮助理解链路，但不能当作实际 Bot 接入验收。

随后按[快速开始](https://github.com/fyaic/wecom-agent-gateway#快速开始)选择已有 Agent、填写 Bot 配置并认领私聊。每个进程选择一个 Agent，一个 Bot 只运行一个 Gateway。主动消息面向已授权会话，不代表可以联系任意外部用户。项目仍处于 Public Preview，投递为 at-least-once，不能承诺绝不重复；长期 Linux 运行和跨主机部署等边界见[当前状态](https://github.com/fyaic/wecom-agent-gateway/blob/main/docs/status.md)。

## 办公工具的授权需要单独维护

当工作流进一步调用 wecom-cli 的文档、通讯录等能力时，需要区分三个状态：

| 状态 | 它能说明什么 |
| --- | --- |
| Bot 连接正常 | 消息连接可用 |
| 访问 token 可刷新 | 请求凭证可以更新 |
| 具体业务能力已授权且未到期 | 该能力的授权目前有效，实际操作仍受数据权限等条件限制 |

前两项正常，不能保证第三项正常。我们遇到的就是七天能力授权到期问题。官方社区也有[授权有效期可观测性](https://github.com/WecomTeam/wecom-cli/issues/87)和[文档能力过期](https://github.com/WecomTeam/wecom-cli/issues/134)讨论。

截至 2026-09-23，在已核查的官方公开文档、版本与源码中，未发现七天业务能力授权的无人值守续期路径。这是有范围和日期的核查结果；详见[官方支持核查](official-status.md)，使用前应再次确认上游是否已有更新。

## 取消再授权，能否变成脚本操作？

Auth Keeper 尝试把用户在正常授权界面上的操作脚本化：找到明确配置的权限行，取消后重新授权，核对新的有效期。它不提供私有续期 API，也不改变平台规定的授权期限。

2026-09-22，我们在 macOS 企业微信 5.0.11.99998 上，使用 Python 3.14 和 PyObjC 12.2.2 做了单账号实测。三项此前已授权的能力，界面有效期从当日 18:39 更新到 9 月 29 日 16:18；关闭并重开权限页后显示一致：

- 新建与编辑文档；
- 搜索与获取文档内容；
- 搜索企业成员。

这次页面由桌面代理预先打开，后续逐项续期由独立脚本完成。未纳入白名单的消息权限保持原日期。完整过程和证据边界见[实测记录](validation.md)。

可以选择只维护所需权限。例如只读文档和通讯录，可在完整配置中设置：

```json
{
  "target_rows": [
    "搜索与获取文档内容",
    "搜索企业成员"
  ]
}
```

需要文档写入时再加入 `新建与编辑文档`。白名单应只包含你明确愿意授予该机器人的能力，因为页面上的“授权”也可能代表该能力从未授权。

依照[复现指南](workaround.md)安装、配置身份并打开正确权限页后，可以先检查，再处理 24 小时内到期的目标：

```bash
.venv/bin/python renew.py --config config.json --check --existing-window
.venv/bin/python renew.py --config config.json \
  --pre-renew --existing-window --within-hours 24
```

有效期还很远的授权会跳过；不能只看 `ok=true` 判断发生了续期。需要比较操作前后的有效期，重开页面复核，并检查待恢复状态。

## 实验已经证明什么，还有什么没证明

这次验证证明了指定条件下，三项能力可以由独立桌面脚本取消、重授并更新界面有效期。没有在这次实测中运行业务 API 复探，因此还不能据此宣称实际业务恢复通过。

目前仍需要已登录、可操作的 Mac 和预先打开的正确权限页。取消与重授之间有短暂权限缺口；页面导航、锁屏运行、跨七天周期稳定性和消息权限续期尚未完成验证。仓库的每小时 keepalive 示例用于到期后的文档探针恢复，不会定时调用上述预续期命令。

也没有完成两个项目组合后的端到端续期验收。它们在职责上互补，但当前并非一键安装、自动联动的套件。

## 欢迎怎样的反馈

Gateway 欢迎新的 Agent Adapter、上手卡点和实际企微接入报告；Auth Keeper 更需要不同客户端版本的复现、续期后的业务 API 验证，以及完整跨周期运行记录。

如果你的目标是在企业微信里使用已有 Agent，可以先试 [wecom-agent-gateway](https://github.com/fyaic/wecom-agent-gateway)。如果已经遇到业务能力七天到期，且有可操作的 Mac，再评估 [wecom-auth-keeper](https://github.com/fyaic/wecom-auth-keeper) 的实验是否适合你的部署条件。
