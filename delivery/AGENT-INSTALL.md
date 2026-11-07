# 安装 Agent 执行协议

适用 Codex、WorkBuddy 或其他具备本机终端/文件访问能力的 Agent。此文件描述软件安装流程，不授权替用户发送消息、上传诊断、创建业务数据或扩大 Bot 权限。用户明确要求优先。不要仅凭依赖安装、AX 可读或 exit 0 宣称续期成功。

## 0. 先核对包与设备，不操作 UI

- 检查维护者提供的 ZIP SHA-256；解压后运行 `python3 delivery/verify_bundle.py`（Windows 可用 `py -3`）。包内散列只检测损坏，不证明发布者身份。
- 运行 `python3 delivery/onboard.py`。它只用标准库，Windows 不会导入 macOS 专用模块。没有 Python 时先说明需安装 Python 3.11+；在用户允许安装软件后用可信官方来源安装，不能远程下载后不检查就执行未知脚本。
- macOS 读取企业微信安装路径、版本、CPU 架构；未识别版本写 unknown，不能猜。Windows 返回 unsupported_automation_backend：停止自动化安装，不安装 pyobjc，不生成 launchd 或伪造 Windows 计划任务成功。按 DESIGN.md 的 Windows 验收方案交维护者处理。
- 只读检查现有 launchd 任务/配置，识别同一 Bot 是否已经在维护。不要启动重复作业或覆盖原配置。不要修改本机其他 Bot 的凭据、业务目录或常驻服务。

## 1. 获取这台机器自己的身份和范围

从业务请求取得目标企业、机器人及需要的能力；已经说明“本机现有 CLI Bot”时直接发现身份，不重复询问。利用本机已有 wecom-cli 的帮助、状态和身份查询确认当前 profile 的 Bot；CLI 命令随版本变化，先看本机 `--help`，不要猜参数，不自动 auth init 切换已在用的 Bot。

身份仅使用 `wecom-cli auth show --status`、`wecom-cli identity whoami` 和 `auth show` 的 Bot ID 字段。原始结果写私有文件，向上下文仅输出所需名字/一致性布尔值。禁止读取、打印或解密 `.encryption_key`、`credentials.enc`、Secret/token；它们不能解决组织定位，且不属于续期安装输入。名称过时或组织未知时，下一步是桌面组织发现，不能研究凭据加密格式。

如果用户明确要求维护“本机已经配置的 wecom-cli Bot”，指定 profile 的现有身份就是排查起点，不要求业务人员重新提供可以在本机查出的信息。当前打开的会话、当前选中企业、新建测试 Bot 都不能代替 CLI 目标。多组织设备应先读取企业切换菜单，核对 CLI 身份所属组织及该组织的机器人管理页面；必要时逐个核对本机已登录组织，再用权限页双 Bot ID 确认。不同组织出现不同 Bot 是正常情况，不能据此擅自换绑 CLI，也不能只在错误组织反复搜索后要求业务人员手工定位。名称不一致先检查组织、身份和页面，再判断是否改名。只有本机证据无法消除的歧义才问用户，并说明已核对了哪些组织及缺少什么。

CLI 授权人与企业微信当前组织显示的人名不同也不能直接认定是不同账号：先检查组织内身份和目标官方页面。若遍历已登录组织仍找不到匹配 Bot，输出具体已查范围和身份未核实结果；不得把另一 Bot 的页面填入 CLI 配置，不得自动重新初始化现有 CLI。首次初始化一个新 Bot 与续期旧 Bot 是不同步骤，需要业务人员确认目标和权限范围。

先运行包内只读盘点工具；它仅调用官方版本、授权状态和身份命令，不扫描凭据、不初始化 Bot。`--profile` 只填本机已知业务配置目录，可重复；默认 profile 始终单独核对。报告含本机身份，仅保存在包外私有目录，不能转发：

```bash
python3 delivery/profiles.py --profile /absolute/known/cli-profile --output /absolute/private/profiles.json
```

只使用默认 profile 时省略 `--profile`。工具的 `ok=true` 只说明盘点完成，`target_selected=false` 和 `desktop_identity_verified=false` 必须由现场核对补齐。多个组织 / 多个 Bot 是正常情况：从业务使用的 CLI profile 出发，核对该 Bot 的组织和页面；默认 profile 不拥有优先权。如果另一个组织的 Bot 才是部署对象，使用它的既有独立 profile；尚未绑定则明确作为首次安装流程，不把它当作改名或要求覆盖默认 Bot。

多 Bot 的 CLI 配置必须明确选择，不能只核对默认目录后声称覆盖了整台设备。CLI 1.3.0 实测支持 `WECOM_CLI_CONFIG_DIR=/absolute/private/profile`；先用 `auth show --status` 只读验证所选目录及默认配置没有混用，再在同一环境下执行身份查询和业务复查。此项在其他 CLI 版本上需要重新验证，不猜 profile 参数、不改 HOME、不复制 Secret。用户同意新增测试 Bot 时使用新建的独立目录；官方扫码绑定和首次业务权限确认仍是必要的一次性步骤，禁止覆盖旧配置或把它们算成自动续期已经完成。

从用户指定 Bot 的官方权限页或本地已有 850003 帮助链接取得 authorization_url。只在指定 profile/业务日志内查找，不扫描整台电脑的凭据。不回显完整链接、Bot ID、聊天内容或认证数据。链接必须为官方 HTTPS 路径且同时包含两个 Bot 标识；其中 str_aibotid 必须和现场 CLI Bot ID 相同。机器人名字和企业文字仅作导航线索。

在仓库/安装包目录外建立权限为 0700 的私有目录，在其中保存以下输入 JSON（0600）。下面是字段示意，必须替换成本机值：

```json
{
  "bot_chat_name": "<本机目标机器人完整会话名>",
  "organization_name": "<本机目标企业>",
  "cli_config_dir": "/absolute/private/selected-cli-profile",
  "authorization_url": "<本机官方权限链接>",
  "cli_bot_id": "<刚刚从指定CLI profile核验的Bot ID>",
  "target_rows": ["搜索与获取文档内容", "新建与编辑文档"]
}
```

`cli_config_dir` 为可选字段：默认 profile 应省略，独立 profile 必须填写绝对路径；安装后所有身份/业务复查必须使用该值。不要依赖 Agent 进程继承的环境变量。

权限目录在 `keeper_capabilities.py`。只选择用户业务需要的项；模板不是允许给所有权限授权。页面不能总是区分未授权与已过期，用户确认白名单也代表允许授予这些能力。无需索取 Secret。

## 2. 配置 macOS（尚未安装服务）

在包根目录建立专用虚拟环境并安装固定依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-macos.txt
.venv/bin/python delivery/onboard.py --input /absolute/private/input.json --output /absolute/private/config.json
.venv/bin/python renew.py --config /absolute/private/config.json --doctor
```

输入及配置不得放进发布包或提交 Git。onboard 会拒绝重复文件、非官方 URL、CLI 身份不符及未知权限项；它核对的是输入数据的一致性，**不能代替 Agent 的现场身份查询**。输入文件用完按用户本地留存规则处理，不上传。

生成配置默认每小时检查、提前24小时续期、最大600秒运行、最后关页。不会自动开启组织切换。先让用户/Agent在正确企业下验证目标 Bot；后台需跨组织时，才按下面一节启用。安装路径要固定，移动路径或换 Python 后需重新验收系统权限与任务。

多组织安装先使用包内后台发现工具，不手写 launchd 探针或只相信 Bridge 的缓存企业名。先让企业微信处于“消息”视图；以下命令在实际 GUI launchd 中使用配置指定的 Python，完成后卸载临时任务，证据目录每次必须为新目录：

```bash
.venv/bin/python delivery/gui.py --config /absolute/private/config.json --action discover --evidence-dir /absolute/private/discovery-1
```

它逐个核对原生企业菜单和目标聊天，尝试读回已有官方入口，然后恢复原企业；不发送消息、不改授权。`chat_name_matched` 仅是名字候选，`link_identity_verified` 才表示发现双 Bot ID 匹配链接；即使 `ok=true`，`identity_review_required` 也不代表找到正确 Bot，更不代表续期通过。仅当唯一候选完成双身份核对，才填写 organization_selector_name 并启用 sidebar-5.0.13。未发现入口时按下一节核对机器人权限页、准备首次入口。必须保留每个组织的发现结果，不能只查当前企业就放弃。

发现失败时，`discovery` 中保留 `enumerated_organizations`、已尝试组织、`stage` 和 `cleanup`；主错误不会被恢复企业的错误覆盖。枚举到了五个企业不等于已经逐一核对五个企业的 Bot。连续遇到相同失败且现场条件未变时，应检查具体步骤、原生页面或管理入口，不能反复重跑后用次数代替覆盖证据。

## 3. 企业与页面导航验收

- 先检查当前企业、目标 Bot 及权限页双身份。不要凭同名会话、头像坐标或页面标题直接授权。
- 没有 Bridge 的设备保持 `bridge_monitor=false`，不为续期安装 Bridge。存在 Bridge 时，先核对同一登录用户的服务地址。支持共同桌面锁的 Bridge 配置为 `bridge_monitor=true`、`bridge_url` 和 `bridge_coordination="shared-lock-v1"`。该协议需要 Bridge 同时升级（见 `delivery/BRIDGE-COORDINATION.md`），不是只改 Keeper 的配置即可工作。Keeper 验证协议、用户、锁文件 inode 和组织重新核验能力后才开始；Bridge 轮巡、监控和 UI 请求在此期间自动让出桌面，关页后恢复。已有私聊入口必须先准备好；该模式不支持调用 Bridge 发入口链接。旧 Bridge 不支持时明确停止，禁止关闭检测、SIGSTOP 或手动暂停服务冒充无人值守通过。旧 observe 兼容路径仍保留，但不能证明独占桌面；启用组织轮巡时明确拒绝。`--worker` 只供监督器内部使用，正式任务使用不带该参数的 `maintain.py`。
- 默认将续期入口保存在**当前部署设备上、当前企业账号与目标 Bot 的私聊消息**中。先核对当前 CLI profile、官方授权链接的双 Bot ID 和目标机器人；不要复制其他设备/机器人的链接，不用群聊、他人的私聊或文件传输助手作为默认入口。
- 首次没有链接时，说明需要一次“入口准备”。用户授权后只向已核对的目标 Bot 私聊发送一次官方链接；用户也可自行发送。发送后必须在这台设备的私聊历史中读回、匹配双 Bot ID，再关闭权限页，从其他会话重新运行完整后台导航。其他设备上能看到消息、或当前权限页已打开，都不能代替此设备的后台验收。日常续期只查找已有入口，不反复发消息。
- Bot 显示名可能被改名，CLI 本地缓存名称不能代替最新现场身份。名称不符时先核对官方页面/链接的双 Bot ID，再更新本机导航名称；不能凭“看起来像测试 Bot”就更换目标。
- 5.0.13 曾出现聊天消息懒加载，首次需打开聊天让链接渲染。对新布局应观察 AX 结构并与预期比对；未知结构停止。5.0.13 的企业入口 AX 坐标失真，专用适配器只在已核对版本和主窗口后使用相对侧栏位置打开菜单，再用原生企业行及选中标记核验；其他版本不能沿用此入口。
- 先运行 `renew.py --check` 获取完整权限和日期；该命令可能导航/切换前台但不改授权。用 finally 调用 `renew.py --close-window`。
- 5.0.13 中文版跨企业时，在私有配置加入 `"organization_navigation": "sidebar-5.0.13"` 和 `"organization_selector_name": "<企业切换菜单中的准确名称>"`。菜单简称可能和企业全称不同。必须先现场读菜单核对，不猜名称。旧 organization_name/organization_markers 不再触发头像启发式切换。
- 此适配器用企业图标识别菜单行，精确唯一名称选择，重新打开菜单验证当前选中项。切换会重建主窗口，脚本重新定位；聊天提及企业名不算当前企业证据。版本不匹配、重名、没有选中标记则停止。该功能须用真正后台启动链测试“别的企业 → 目标企业 → 权限页 → 关页”，再启用定时任务。


## 4. 实际后台链路与续期分层验收

1. **配置层**：doctor/字段校验，只说明依赖和配置可用。
2. **桌面检查层**：相同登录用户、Python 和启动链读取目标权限及日期、干净关页。终端的权限不能证明 launchd 子进程有辅助功能权限。让用户在系统设置对真实执行主体授权；不修改 TCC、不重置全局授权、不借用其他程序绕过检查。
   远程终端/SSH 仅负责安装和读取结果。SSH 链的 AX 检查失败不能证明用户桌面的 launchd Python 也失败；应使用该登录用户的 GUI launchd 临时任务运行同一个 Python，核对实际 AX 信任及读页结果，完成后卸载临时任务。不要为了方便 SSH 调试要求额外授予 sshd 辅助功能。系统权限设置完成后，重新从普通聊天/其他组织开始验收，不能由安装 Agent 预先打开权限页替代完整导航。
3. **真实续期层**：对已确认白名单中的临近到期项运行 `maintain.py --config ...`。记录每项前后日期、pending 为 false、关页成功，并用同 Bot 的只读业务调用复查。业务写验证或发消息需用户另行授权。健康但未到阈值的检查只算检查通过。
4. **提前验收（可选）**：如用户明确同意现在取消/重授一次，可用隔离配置/状态临时设 within_hours=168，只针对同意的权限。验收后恢复生产24小时，不让168小时进入生产任务。没有到期项、也没有该授权时，标记 renewal_pending；到自然窗口后观察真实续期，不能虚报完成。

以上后台命令统一用 `delivery/gui.py --config ... --action check|close|maintain --evidence-dir <新的私有目录>`，每次只选一个 action。`maintain` 调用完整生产入口，不绕过监督器。`check` 后必须执行 `close`；`maintain` 自带 finally 关页。工具返回实际进程退出码与原始脚本结果，临时任务不会设置每小时调度。不要把任务登记成功、空日志、轮询 `launchctl print` 仍存在或模型文字结论当成完成。

记录 `delivery/acceptance.example.json` 的副本到私有目录。只填实际证据。schema_version=2 将身份拆为四项：cli_profile_verified 只代表选定了正确 CLI 配置，cli_url_identity_verified 只代表 CLI 与官方链接一致；desktop_organization_verified 和 desktop_bot_identity_verified 必须来自这台设备的桌面核验。前两项不能代替后两项。release_commit 从当前 MANIFEST.json 读取，不留空；scheduled_run_verified 必须有实际定时入口执行证据；runtime_human_or_agent_clicks 记录运行期间是否代点，人工/模型代点成功不能算无人值守续期。`entry_location` 记录实际入口位置；`entry_identity_verified` 记录私聊链接双身份核对；`entry_reopened_from_other_chat` 必须来自关页、切到其他会话后的后台重新导航结果，不能用当前打开的页面替代。多权限至少检查所有白名单项；某项成功不等于所有项成功。已有一个 Bot 的验收不能代表其他 Bot 或其他系统版本。

## 5. 安装、观察、升级、卸载

确认用户要启用定时任务且无同 Bot 的重复任务，再运行：

```bash
.venv/bin/python maintain.py --config /absolute/private/config.json --write-launchagent /absolute/private/job.plist
plutil -lint /absolute/private/job.plist
launchctl bootstrap "gui/$(id -u)" /absolute/private/job.plist
```

生成器默认 RunAtLoad，会立即执行真实维护，所以在加载前完成范围和后台授权检查。保留 job.plist 的固定路径；写出实际 Label（从 plist 读取，不猜）、日志位置、卸载命令。加载成功只代表任务已登记，必须读它的运行输出确认没有权限/导航错误。`--status` 是历史状态，不是存活或实时授权证明。

```bash
launchctl bootout "gui/$(id -u)" /absolute/private/job.plist
```

升级使用新版本目录，不覆盖正在执行的文件；先停止该 Bot 的旧任务、保留原配置/状态/版本，再验证新版本并启用。保留 pending 与 maintenance 状态；配置身份不匹配时停止，不直接删除状态清错。失败则停新任务，恢复旧路径和配置，不能同时启用两套维护。

至少观察一个正常检查周期和一次真正续期。设备休眠、锁屏、退出账号、系统重启未登录均可能错过窗口。输出一份简短中文结论：已配置范围、系统/客户端版本、任务是否运行、哪些验收通过、尚缺什么、出现问题怎么停止。默认不自动联系维护者、不上传原始 AX/聊天/日志。原 scripts/inspect_compat.py 会输出原始文本和 URL，本分发包有意不包含它。
