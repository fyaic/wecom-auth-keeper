# 安装 Agent 执行协议

适用 Codex、WorkBuddy、Kimi Code 等具备本机文件、终端与界面操作能力的 Agent。**先按 [FIRST-RUN.md](FIRST-RUN.md) 完成首次接入，再运行日常续期。** 不假设业务设备已经有 Bot、已经知道正确组织、已经有私聊消息或授权入口。本文件不额外授权发送消息、扩大权限或修改其他服务；用户本次明确授权优先。

## 0. 校验包与本机环境

校验维护者提供的 ZIP SHA-256，解压到固定版本目录，运行：

```bash
python3 delivery/verify_bundle.py
python3 delivery/onboard.py
```

manifest 只检查包内容完整性，不证明发布者身份。需要 Python 3.11+；缺少时按用户授权从可信官方来源安装。macOS 检查实际客户端版本、CPU 架构、已有维护任务及实际运行 Python；Windows 当前返回 unsupported_automation_backend，没有 UIA 后端，不安装 pyobjc 或伪造计划任务成功。支持范围见 [DESIGN.md](DESIGN.md)，实际证据见 [VALIDATION.md](VALIDATION.md)。

在 macOS 为本版本准备独立执行环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-macos.txt
```

检查 `wecom-cli --version`（至少1.1.0）；没有 CLI 时先检查 Node/npm，并按官方 `@wecom/cli` 包完成安装，再复查版本与 `auth show --status`。已有可用 CLI 不默认升级，不重复初始化已授权 profile。自定义 profile 的隔离行为目前验过1.3.0，其他版本先验证，不把一套凭据误当多个 profile。

不复用其他业务服务的依赖环境。若本机已有经系统授权的专用执行 Python，可在私有配置中明确填写其绝对路径，并如实记录复用；验收与正式任务必须使用同一个执行主体，不能把这种复测说成从空设备全新安装。

配置、输入、聊天入口文本、诊断和验收记录全部放包外本机私有目录，建议 `~/.local/state/wecom-auth-keeper/<本机Bot配置名>/`（目录700、私有文件600）。本机实测相同 Python/脚本在 Documents 下的新日志目录启动返回78，改用 `~/.config` 下私有目录后成功；原因应按实际系统日志核查，不把它当成 AX 页面失败。若 runner 返回 gui_job_failed/78，先检查解释器与日志目录访问，使用常规私有运行目录重试，不改系统权限数据库。不要修改本机其他 Bot 的凭据、业务目录或常驻服务；先识别同 Bot 已有任务，避免重复安装。

## 1. 完成首次接入，不直接搜索不存在的历史

顺序固定：**目标企业与业务能力 → 选定/接入 Bot 与 CLI profile → 原生组织核验 → Bot 官方身份核验（必要时先进入候选空私聊只读定位）→ 确认本机 Bot 私聊 → 发送或复用一次入口 → 离开会话后的后台找回。** 详细动作及失败回退见 FIRST-RUN.md。

本机已有 CLI profile 只用官方命令盘点：

```bash
python3 delivery/profiles.py --output /absolute/private/profiles.json
# 有已知的其他 profile 时，增加 --profile /absolute/private/another-cli-profile
```

正确身份命令是 `wecom-cli identity whoami`。只读 `auth show --status`、`auth show` 的 Bot ID 及身份结果；原始结果留在私有文件，不向公共报告输出 ID/URL。禁止读取、解密 `.encryption_key`、`credentials.enc`、Secret/token；这不能帮助定位组织。默认 profile 不自动等于业务目标；不同组织 Bot 名称相似或不同都正常，不能擅自换绑已有 CLI。

若未绑定 Bot，按本机官方帮助完成独立 profile 的接入或创建。首次扫码、系统授权及首次业务权限授予可能需要一次用户操作；这是安装，不是每次续期都需要人工。用户已经说明目标时不重复问；本机无法消除的歧义只呈现具体候选，不让业务人员提供技术标识。

`onboard.py --input <私有输入.json> --output <新私有配置.json>` 在取得正确官方入口后生成草稿。必填字段：bot_chat_name、organization_name、cli_bot_id、authorization_url、target_rows；可选 cli_config_dir、organization_selector_name、wecom_cli 与 wecom_node（后两者为绝对路径）。生成器会记录当前检测到的 CLI 和 Node 路径；npm 安装的 CLI 即使使用绝对路径，也可能通过 `/usr/bin/env node` 启动，因此后台调用会加入已记录的运行目录。未检测到时补充实际路径，并在 GUI launchd 中复验身份，不能以终端成功代替。target_rows 是用户需要维护的明确权限白名单，消息、文档、微盘、邮件等可多选，不因验收方便自动加权。organization_name 是业务企业名，organization_selector_name 是本机原生菜单实际名称，不能猜或用头像推断。

草稿返回 `entry_preparation_required`，包含 entry_receipt 路径。`prepare_entry.py` 只生成准备发送的文本，sent=false 不代表已经发消息。安装 Agent 必须从已核验 Bot 详情进入正确私聊；首次没有会话不能仅重跑全局/历史搜索。收到发送授权后只发一次，然后本机读回核验。不默认使用群聊、他人私聊、文件传输助手或另一设备的历史。

## 2. 后台入口验收与诊断

安装 Agent 核对私聊类型并记录来源，关闭权限页、切到其他普通聊天或企业，然后运行：

```bash
.venv/bin/python delivery/gui.py --config /absolute/private/config.json --action entry-verify --evidence-dir /absolute/private/entry-check-1
```

这是实际 GUI launchd 一次性任务，使用配置中的 Python，完成后卸载；不是每小时服务。成功表示所选 CLI、原生组织、目标聊天标题、链接双 ID、官方页面、全部配置权限可读与关页均通过。它不会发送、授权或改变 Bridge。私聊类型由安装 Agent 从已核验详情的进入路径确认，脚本不会把同名聊天当作类型证据。entry_receipt 是设备与配置绑定的本地安装记录，不是防篡改安全证明，也不是续期成功证明。

入口未准备好时维护/定时任务生成返回 bootstrap_incomplete；修好本步骤再继续。换目标、profile、组织、权限范围或 Python/CLI/Node 路径后重新验证；不要删掉 entry_receipt 配置来绕过。已有旧配置保持原行为，不在正在运行的服务上强制迁移。

`bootstrap_authorization_baseline_required` 表示入口和页面已读到，但所选权限没有有效期证据。仅一个“授权”按钮不能区分从未授权与过期；先核对既有授权或完成用户确认的一次首次授权，再重验建立基线，不重复发送链接或搜索历史。此时不生成成功回执，不开启维护。

| 工具 | 用途及限制 |
| --- | --- |
| `gui.py --action inspect-expanded --python <绝对Python路径>`（无config） | 首次接入时读取原生组织菜单与可见Bot名称候选，不需要虚构Bot配置；只读、不导航、不授予权限。 |
| `gui.py --action inspect` | 只读当前原生控件、通讯录 Bot 分组与官方权限页；不导航、不调用 Bridge、不输出聊天/原始URL。通讯录只报告可见候选数量/位置，不声明列表完整或身份已验证。 |
| `gui.py --action inspect-expanded` | 临时请求 AXEnhancedUserInterface，读回生效并恢复原值；不是系统辅助功能授权。 |
| `gui.py --action discover` | 仅适用于入口已经准备好后的跨组织查找；缺少私聊或入口时回首次接入，不反复执行。 |
| `gui.py --action check-existing` | 只读已经打开且双ID匹配的页，不激活、不导航、不调用 Bridge；不能算自动找回。 |
| `gui.py --action check` | 检查完整已有入口导航和权限；可能切换界面。检查后执行 close。 |
| `gui.py --action close` | 只关闭当前双ID绑定权限页；不退出主窗口，不调用 Bridge，不用键盘/鼠标回退。 |
| `gui.py --action maintain` | 正式维护入口，包含监督器、逐项续期与 finally 关页；不能绕过监督器使用内部 --worker。 |

每次 evidence-dir 使用新私有目录，保留实际进程输出与退出码。任务登记成功、HTTP200、空日志或 Agent 自述不能算验收。

5.0.13 原生管理页可能肉眼可见而 AX 标签为空；原生卡片还可能将标签合并进 AXTitle/AXDescription。inspect-expanded 只输出固定标签与精确/包含匹配，不把包含匹配直接当成可点击控件。切页后可能需要重新展开树，重复设置 true 不等于树刷新。必须区分门户/列表/详情/权限弹窗；管理列表只显示可管理的 Bot，不代表可使用的全部 Bot。“查看更多机器人”会进入通讯录的“智能机器人”分组，用实际列表行识别，不套管理卡片布局；页面未知或列表未完整读取，不能报告“没有 Bot”。

组织导航目前仅已知 5.0.13 中文适配器：准确企业菜单名、企业图标行、唯一 checkmark、切换后重新定位和验证。企业入口采用版本约束的相对窗口位置，不能外推其他版本/语言/布局。未知页面先诊断，不能硬套坐标。

所有授权/取消授权/确认动作只来自双ID匹配 AXWebArea 的当前子树；窗口消失或控件脱离就停止，AXPress失败不退回坐标。内嵌权限页清理还要求原生AXSheet、唯一页面、可使用权限标题及已核验关闭布局；未知布局拒绝关闭主窗口。

## 3. 系统权限与共用桌面

辅助功能必须属于正式执行的那个 Python。终端可操作不证明 launchd 子进程可操作；SSH 检查失败也不证明 GUI launchd 失败。使用同用户的 gui.py 临时任务验证。必要时通过正常系统设置授权真实执行主体，不修改 TCC、不借用其他应用绕过，也不要求给 sshd 额外授权。

普通没有其他 UI 服务的 Mac 不需要安装 Bridge。已运行 Bridge 的设备先识别真实服务，不能为了续期自行停止、升级或改其模式。支持共同桌面锁时按 [BRIDGE-COORDINATION.md](BRIDGE-COORDINATION.md) 配置并验证协议、uid、锁文件 inode 及交接刷新；旧 Bridge 的 observe 模式不能停止组织轮巡。用户拒绝更新/停止的约束持续有效，不重复索取同一权限或用 SIGSTOP 绕过。

旧 Bridge 的组织API success与缓存 current_org 不证明当前页面组织，普通切换API还可能触发自动回到主组织。首次接入可做有界的导航核验，但不代表正式授权修改获得桌面独占；完整维护路径仍按协调要求执行。不要把入口准备缺失和并发协调失败混为一个问题。

## 4. 真实续期与定时触发分开验收

入口完成后运行 `gui.py --action maintain` 验证所选已有权限。默认每小时检查、提前24小时逐项续期，完成自动关页。记录每项前后到期日、pending=false、关页结果，再用同 Bot 的必要只读业务调用核验。未授权新权限要先按用户确认范围完成首次授权，单独记录。

健康但未到阈值只算检查通过。用户已明确同意提前做一次取消/重授时，可以隔离验收配置临时设 within_hours=168，验收后恢复24小时；不要为得到绿色结果扩大白名单或写业务数据。正式定时安装前至少通过：

1. 本设备从其他聊天/组织找回私聊入口，并关闭页面。
2. 纯脚本实际续期、全部目标项有效期确实延长；运行期间无人/Agent代点。
3. 同一正式执行 Python、GUI launchd 启动链通过，清理与异常恢复可复核。
4. 临时定时任务真正触发一次；登记成功或手工 kickstart 不代替自然触发。

使用 acceptance.example.json 的私有副本（schema_version=3）分别记录首次接入、入口、续期、定时结果，release_commit 从 manifest 读取。bootstrap.private_chat_opened_from_verified_bot 必须由安装 Agent 实际观察；entry-verify 的标题/链接结果不能替代。任一 Bot/设备通过不代表其他设备或 Windows 通过。

## 5. 安装、升级和卸载

完整验收通过、无重复任务且用户要求启用后：

```bash
.venv/bin/python maintain.py --config /absolute/private/config.json --write-launchagent /absolute/private/job.plist
plutil -lint /absolute/private/job.plist
launchctl bootstrap "gui/$(id -u)" /absolute/private/job.plist
```

RunAtLoad 会立即执行真实维护，加载后读取运行结果。记录实际 Label、日志和停止方法：

```bash
launchctl bootout "gui/$(id -u)" /absolute/private/job.plist
```

升级用新版本目录，保留旧配置、状态、pending与回滚路径，不覆盖执行中的文件或同时启动两套服务。失败时停止新任务恢复旧版本，不删除 pending 清错。设备休眠、锁屏、退出账号、重启未登录会影响定时执行；客户端升级后重新验收。

给业务人员简短报告：维护哪个组织/Bot/哪些权限，入口准备、真实续期、定时运行各是否通过，以及怎么停止。默认不联系别人、不上传聊天/AX/凭据或原始日志。当前包仍是内部候选，未通过远端真实续期前不能发布为“Mac通用可用版”。
