# 独立定时维护多个权限

`maintain.py` 是无需 Gateway、Codex 或模型的定时维护入口。它复用原有 AX 导航和授权状态机，在一个桌面锁内完成导航、逐项续期、最终复查和关页。默认每小时检查，提前 24 小时续期。

本入口按页面有效期调度，**不要求文档测试表，也不会运行文档写探针**。页面验证和业务验证分开：结果始终明确 `business_verified: false`，实际文档、微盘、邮箱等业务应由对应调用方复查。旧 `keepalive.py` 的文档双探针恢复流程保留不变。

## 1. 每个 Bot 一份配置

复制 [config.maintenance.example.json](../config.maintenance.example.json) 到仓库外的私有目录，填写机器人会话名、授权链接的两个身份参数和 Python 绝对路径。各 Bot 使用不同的状态与日志目录。模板的权限仅作示例，应删改为该部署确实需要维护的能力。

`target_rows` 是唯一操作白名单，可以是一项，也可以同时包含多项：

```json
{
  "target_rows": [
    "发送消息",
    "搜索与获取文档内容",
    "新建与编辑文档",
    "搜索与获取微盘文件内容",
    "上传与更新微盘文件",
    "搜索与获取邮件内容",
    "发送邮件"
  ]
}
```

这是配置片段，不是向本机自动增加授权的指令。企业微信的“授权”按钮不能区分已过期与从未授予，白名单也代表允许授予这些能力。不要把所有示例项直接加入生产白名单。

| 场景 | 页面权限名称 |
| --- | --- |
| 消息 | 发送消息 |
| 文档读取 / 编辑 | 搜索与获取文档内容 / 新建与编辑文档 |
| 微盘读取 / 上传更新 | 搜索与获取微盘文件内容 / 上传与更新微盘文件 |
| 邮件读取 / 发送 | 搜索与获取邮件内容 / 发送邮件 |
| 待办 | 新建与跟进待办 |
| 日程 | 新建与管理日程 |
| 会议 | 搜索与获取会议信息 / 预约与更新会议 |
| 通讯录 | 搜索企业成员 / 获取对话用户信息 |

不接触企业微信即可列出当前目录：

```bash
.venv/bin/python maintain.py --list-capabilities
```

目录集中在 `keeper_capabilities.py`，供配置工具复用。新能力可使用页面的完整行名加入 `target_rows`，无需为每种权限写一套续期脚本；若新版客户端的控件结构变化，仍需更新解析并做实机验证。**目录里有某能力不等于本版已对其完成真实续期验收。**

## 2. 选择提前量与检查频率

```json
{
  "maintenance": {
    "within_hours": 24,
    "interval_seconds": 3600,
    "min_renew_interval_seconds": 3600,
    "retry_seconds": 300,
    "close_window": true
  }
}
```

- `within_hours`：只对剩余时间不超过该值的已授权项执行取消、重授。已过期项直接恢复。范围 1–168 小时；生产建议 24，168 主要用于受控验收。
- `interval_seconds`：生成的 launchd 作业检查间隔，默认 3600 秒，必须小于提前量。修改后需重新生成并重新加载作业。
- `min_renew_interval_seconds`：每项成功后至少等待的时间，默认 3600 秒。只约束同一权限同一有效期，不阻塞其他到期项。
- `retry_seconds`：失败后的退避起点，指数递增至最多一小时；实际重试仍由下一次定时检查触发，不会后台密集点击。
- `close_window`：完整周期结束后关闭核验过的权限窗口，默认 true；关闭失败单独报告。

例如消息权限剩 12 小时、文档权限剩 3 天、微盘权限已过期：本次仅预续消息、恢复微盘，文档跳过。每项都依据自己的页面有效期判断，不要求所有权限同一天到期。

## 3. 单次验收

先确认目标聊天已有官方授权链接、已登录解锁、后台 Python 有辅助功能权限。客户端实测范围见[兼容与升级](compatibility.md)。辅助功能授权必须验证实际后台启动链；终端或 Gateway 链路可用不代表直接 Python launchd 作业也有权限。2026-10-23 本机直接 Python 作业返回 `accessibility_permission_unavailable`，未执行授权操作，因此本机仍保留已验证的 Gateway 定时链路。独立作业在其他机器启用前需由该机器确认实际执行进程的系统辅助功能授权，程序不会代为获取或绕过。

```bash
.venv/bin/python maintain.py --config /absolute/private/keeper.json
```

运行逻辑：读取全部指定权限 → 优先恢复 pending → 按每项期限逐条处理 → 保存每项进度 → 最终复查 → 关闭目标权限窗口。一个权限失败会停止后续变更，已成功项的记录保留。父进程对完整 GUI 子进程设置 `renew_timeout` 总超时；超时后另行尝试关页，仍报告失败。

`<state_file>.maintenance.json` 保存 Bot 绑定、每项冷却与未完成动作、失败退避；`<state_file>.pending.json` 继续保存取消后的优先恢复记录。进程在授权成功后、调度状态保存前退出，下次会用新的页面有效期核销旧动作，不重复撤销。如果无法确认上次动作结果，返回 `action_outcome_unknown`，不再冒然取消；需要复核页面，不要直接删除状态文件。

只读查看历史调度证据：

```bash
.venv/bin/python maintain.py --config /absolute/private/keeper.json --status
```

这是历史状态，不代表新检查或服务当前正在运行。预续冷却不会阻止已经观察到的过期项或 pending 恢复。失败退避期间不操作 UI，下一次允许执行时优先恢复 pending。

## 4. 安装定时任务

确认单次验收后生成任务；生成步骤只写文件，不启动 UI 或安装服务：

```bash
.venv/bin/python maintain.py --config /absolute/private/keeper.json \
  --write-launchagent "$HOME/Library/LaunchAgents/com.example.wecom-maintenance.plist"
plutil -lint "$HOME/Library/LaunchAgents/com.example.wecom-maintenance.plist"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.example.wecom-maintenance.plist"
```

作业在加载时立即运行，之后按 `interval_seconds` 调度。生成器使用参数数组，路径带空格也可工作；文件已存在时拒绝覆盖。日志写到 `<log_file>.maintenance.log`，每次输出一条 JSON。相同 Bot 的作业 Label 相同，避免按不同文件名重复加载。

停止任务：

```bash
launchctl bootout "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.example.wecom-maintenance.plist"
```

同一个 Bot 在独立调度和 Gateway 调度中**选择一个**。迁移时先停止旧维护服务，保留旧配置、状态和代码用于回滚，再启用新任务；不影响 Gateway 的消息服务。多 Bot 可分别安装不同配置的作业，Keeper 的共享桌面锁会串行化实际 UI 操作。不同企业不会自动切换。

## 复用接口与边界

- `keeper_capabilities.CAPABILITY_GROUPS`：权限目录。
- `keeper_maintenance.policy(cfg)`：策略校验及默认值。
- `keeper_maintenance.run_cycle(cfg, ax)`：可注入 AX 实现和时钟的周期函数；调用方必须在整个调用期间持有 `gui_lock_path()` 的 `process_lock`。推荐外部项目调用 `maintain.py`，使用已有进程超时和 JSON 退出协议。
- `maintain.py --write-launchagent`：根据同一份配置生成定时启动文件。

共享锁只约束遵守同一协议的 Keeper 进程；其他 UI 服务仍需互斥或错峰。关闭权限页不会恢复原会话。机器休眠或锁屏期间无法保证及时续期，不以“已配置提前 24 小时”宣称永不中断。旧客户端兼容性未知，跨设备与多周期实测仍需补齐。
