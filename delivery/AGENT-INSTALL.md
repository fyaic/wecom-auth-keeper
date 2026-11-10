# 安装 Agent 执行协议

适用 Codex、WorkBuddy、Kimi Code 等具备本机文件、终端与界面操作能力的 Agent。**先按 [AGENT-RUNBOOK.md](AGENT-RUNBOOK.md) 执行清单与 [FIRST-RUN.md](FIRST-RUN.md) 完成首次接入，再运行日常续期。** 不假设业务设备已经有 Bot、已经知道正确组织、已经有私聊消息或授权入口。本文件不额外授权发送消息、扩大权限或修改其他服务；用户本次明确授权优先。

**适用前提：自动续期设备的企业微信登录 Bot 创建者主账号，只维护该主账号自己创建的 Bot。** 先读取现有CLI与官方页面核验，不能以持有CLI凭据、authorized状态或同组织成员身份替代。前提不成立时保留配置、说明需要创建者桌面，不开启定时任务、不换绑来绕过。把安装Agent实际核验依据记入验收表的 `bootstrap.desktop_creator_account_verified` / `creator_identity_evidence`；这是安装身份核验，与脚本入口回执及真实续期证据分别记录。

## 0. 校验包与本机环境

校验维护者提供的 ZIP SHA-256，解压到固定版本目录，运行：

```bash
python3 delivery/verify_bundle.py
python3 delivery/onboard.py
```

manifest 只检查包内容完整性，不证明发布者身份。需要 Python 3.11+；缺少时按用户授权从可信官方来源安装；本包不含解释器和依赖，首次安装需要联网下载。macOS 检查实际客户端版本、CPU 架构、已有维护任务及实际运行 Python；Windows 当前返回 unsupported_automation_backend，没有 UIA 后端，不安装 pyobjc 或伪造计划任务成功。支持范围见 [DESIGN.md](DESIGN.md)，实际证据见 [VALIDATION.md](VALIDATION.md)。

在 macOS 为本版本准备独立执行环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-macos.txt
```

检查 `wecom-cli --version`（至少1.1.0）；没有 CLI 时先检查 Node/npm，并按官方 `@wecom/cli` 包完成安装，再复查版本与 `auth show --status`。已有可用 CLI 不默认升级，不重复初始化已授权 profile。自定义 profile 的隔离行为目前验过1.3.0，其他版本先验证，不把一套凭据误当多个 profile。

**用户指定的Bot优先于业务服务profile和终端默认值。** 先用profiles盘点已知配置，再从指定Bot的原生详情取得官方身份，以select_target生成匹配记录；仅成功选择后才用`existing_entry.py --selection ...`读取该profile的原始链接。默认CLI即使authorized也不能改变目标。`850003`是权限过期；其他Bot的创建者拒绝也不能用于判断指定Bot或整台设备。详见FIRST-RUN.md。

不复用其他业务服务的依赖环境。若本机已有经系统授权的专用执行 Python，可在私有配置中明确填写其绝对路径，并如实记录复用；验收与正式任务必须使用同一个执行主体，不能把这种复测说成从空设备全新安装。

配置、输入、聊天入口文本、诊断和验收记录全部放包外本机私有目录，建议 `~/.local/state/wecom-auth-keeper/<本机Bot配置名>/`（目录700、私有文件600）。本机实测相同 Python/脚本在 Documents 下的新日志目录启动返回78，改用 `~/.config` 下私有目录后成功；原因应按实际系统日志核查，不把它当成 AX 页面失败。若 runner 返回 gui_job_failed/78，先检查解释器与日志目录访问，使用常规私有运行目录重试，不改系统权限数据库。不要修改本机其他 Bot 的凭据、业务目录或常驻服务；先识别同 Bot 已有任务，避免重复安装。

## 1. 完成首次接入，不直接搜索不存在的历史

顺序固定：**用户指定目标/组织/能力 → 盘点既有profile候选 → 指定Bot的原生组织与官方身份 → 按ID匹配profile → 该目标的创建者核验 → 本机Bot私聊 → 一次入口 → 后台找回。** 无匹配profile时保留指定目标，明确区分“Bot已创建但CLI接入未匹配”；不换成别的已授权Bot，不要求重建目标。详细动作见FIRST-RUN.md。

先从当前`WECOM_CLI_CONFIG_DIR`和已知业务启动配置收集非默认profile路径，不读取凭据内容。profiles工具会清空继承覆盖并检查真正default，不自动扫描整机；显式传入其他已知目录。只用官方命令盘点：

```bash
python3 delivery/profiles.py --output /absolute/private/profiles.json
# 有已知的其他 profile 时，增加 --profile /absolute/private/another-cli-profile
```

正确身份命令是 `wecom-cli identity whoami`。只读 `auth show --status`、`auth show` 的 Bot ID 及身份结果；原始结果留在私有文件，不向公共报告输出 ID/URL。禁止读取、解密 `.encryption_key`、`credentials.enc`、Secret/token；这不能帮助定位组织。默认 profile 不自动等于业务目标；不同组织 Bot 名称相似或不同都正常，不能擅自换绑已有 CLI。

若目标已创建但未找到对应绑定，按FIRST-RUN的专门分支复用该Bot现有API接入信息、准备独立profile；本机CLI支持`--manual`时不先要求扫码。目标凭据只在本机受控传给官方CLI，不进入模型/日志，不解密其他profile。首次扫码（确需时）、系统授权及首次业务权限授予可能需要一次用户操作；这是安装，不是每次续期都需要人工。用户已经说明目标时不重复问；本机无法消除的歧义只呈现具体候选，不让业务人员提供技术标识。

同一Bot匹配多份profile时，select_target可用`--profile /absolute/known/profile`或`--default-profile`显式消歧，只允许选择已盘点且ID匹配的候选；不删除其他绑定。

`onboard.py --input <私有输入.json> --selection <成功选择记录.json> --output <新私有配置.json>`生成草稿。必填输入：bot_chat_name、organization_name、organization_selector_name、cli_bot_id、authorization_url、target_rows；可选cli_config_dir、wecom_cli、wecom_node。Bot身份、名称、原生组织、profile必须与选择记录一致，否则不写配置；旧部署配置不自动迁移。CLI/Node绝对路径用于后台精简PATH，在GUI launchd中复验。target_rows是用户明确需要的权限白名单，不因验收加权；organization_name保留业务企业名，organization_selector_name必须是本机实际菜单名。

草稿返回 `entry_preparation_required`，包含 entry_receipt 路径。`prepare_entry.py` 只生成准备发送的文本，sent=false 不代表已经发消息。安装 Agent 必须从已核验 Bot 详情进入正确私聊；首次没有会话不能仅重跑全局/历史搜索。收到发送授权后只发一次，然后本机读回核验。不默认使用群聊、他人私聊、文件传输助手或另一设备的历史。

新版的“去使用”可能先进入通讯录Bot资料页，再点资料页“发消息”才是私聊。看到“由我创建/个人使用机器人/去管理/添加到群聊”时仍是资料页；不能将通讯录选中行当聊天标题，将全局搜索或任意AXTextArea当发送框。按FIRST-RUN核验实际消息视图、标题、消息区域和底部composer后才发送。

## 2. 后台入口验收与诊断

安装 Agent 核对私聊类型并记录来源，关闭权限页、切到其他普通聊天或企业，然后运行：

```bash
.venv/bin/python delivery/gui.py --config /absolute/private/config.json --action entry-verify --evidence-dir /absolute/private/entry-check-1
```

这是实际 GUI launchd 一次性任务，使用配置中的 Python，完成后卸载；不是每小时服务。成功表示所选 CLI、原生组织、目标聊天标题、链接双 ID、官方页面、全部配置权限可读与关页均通过。它不会发送、授权或改变 Bridge。私聊类型由安装 Agent 从已核验详情的进入路径确认，脚本不会把同名聊天当作类型证据。entry_receipt 是设备与配置绑定的本地安装记录，不是防篡改安全证明，也不是续期成功证明。

入口未准备好时维护/定时任务生成返回 bootstrap_incomplete；修好本步骤再继续。换目标、profile、组织、权限范围或 Python/CLI/Node 路径后重新验证；不要删掉 entry_receipt 配置来绕过。已有旧配置保持原行为，不在正在运行的服务上强制迁移。

`bootstrap_authorization_baseline_required` 表示入口和页面已读到，但所选权限没有有效期证据。仅一个“授权”按钮不能区分从未授权与过期；先核对既有授权或完成用户确认的一次首次授权，再重验建立基线，不重复发送链接或搜索历史。此时不生成成功回执，不开启维护。

`authorization_creator_required` 表示双ID匹配的官方页面明确要求机器人创建者；它不是辅助功能不足、按钮失效或未绑定。`authorization_organization_mismatch` 与 `authorization_bot_deleted` 分别表示官方企业身份限制和Bot已删除。保留原profile，按 FIRST-RUN.md 核对桌面/组织上下文；不要让业务人员重新扫码绑定。只读页面加载要等权限行或明确错误，标题和HTTP/打开返回码不足以通过。缺少Bot私聊时，FIRST-RUN.md允许在已授权范围内用本人会话临时诊断，但它不能代替正式Bot私聊验收。

| 工具 | 用途及限制 |
| --- | --- |
| `select_target.py --target ... --profiles ... --output ...` | 根据用户指定Bot的原生官方身份匹配profile；无匹配或多匹配不自动选择默认项，不改变目标。 |
| `existing_entry.py --selection ... --cli ... --output ...` | 只读取选择记录指定的profile，调用前重验Bot ID；识别850002未授权与850003过期并保留原URL，不初始化、不授予权限、不读凭据、不发送。 |
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

所有授权、最终取消确认和授权确认动作只来自双ID匹配 AXWebArea 的当前子树；窗口消失或控件脱离就停止，AXPress失败不退回坐标。5.0.13的非最终“取消授权”文本菜单没有AXPress：仅这一打开确认框的导航步骤，允许在已持桌面锁、版本匹配、原生窗口聚焦、目标行仍有效且期限未变、系统级命中测试恰为同一菜单控件时，按当次控件中心点击。不能将此例外用于授权按钮、最终取消按钮、未知版本、遮挡或猜坐标。内嵌权限页清理还要求原生AXSheet、唯一页面、可使用权限标题及已核验关闭布局；未知布局拒绝关闭主窗口。

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

自然触发验收可使用包内 `maintain.py --write-launchagent` 生成临时60秒任务：保留生成的 plist，将其副本的 RunAtLoad 改为 false，再 bootstrap；记录加载时间和自然输出。验收策略可暂用 within_hours=168、interval_seconds=60、min_renew_interval_seconds=60、retry_seconds=60，实际配置字段以配置示例与策略解析为准。至少捕获一轮 `pre_renewed`、有效期严格增加、pending=false、cleanup.closed=true，随后卸载临时任务。分钟精度使同一分钟重授不构成延期证据；not_due/cooldown 也不算真实续期。恢复正式24小时/3600秒策略，再生成正式任务；严禁遗留短周期重复撤销授权。保留实际输出和 plist，不能修改结果文件把检查变成续期。

使用 acceptance.example.json 的私有副本（schema_version=3）分别记录首次接入、入口、续期、定时结果，release_commit 从 manifest 读取。bootstrap.private_chat_opened_from_verified_bot 必须由安装 Agent 实际观察；entry-verify 的标题/链接结果不能替代。任一 Bot/设备通过不代表其他设备或 Windows 通过。

## 5. 安装、升级和卸载

完整验收通过、用户已要求启用时，将正式策略恢复为每小时/提前24小时。先检查同目标旧任务，等待其周期结束后卸载，避免两套任务。下面变量均由Agent设为本机已核验的绝对路径，当前目录为固定解压目录：

```bash
"$keeper_python" maintain.py --config "$keeper_config" --write-launchagent "$keeper_private/hourly.plist"
plutil -lint "$keeper_private/hourly.plist"
keeper_label=$(/usr/libexec/PlistBuddy -c 'Print :Label' "$keeper_private/hourly.plist")
keeper_plist="$HOME/Library/LaunchAgents/$keeper_label.plist"
```

生成命令仅写文件，`installed=false`不是错误，也不代表已经安装。读取Label后检查`launchctl print "gui/$(id -u)/$keeper_label"`和`$keeper_plist`；有旧任务或文件先核对来源，不能直接覆盖。

正式文件必须放入`~/Library/LaunchAgents`才能在后续用户登录时加载。临时验收文件保留在私有证据目录，不能顺手也装成常驻任务。确定无同目标冲突后，用独占创建避免覆盖旧文件：

```bash
python3 - "$keeper_private/hourly.plist" "$keeper_plist" <<'PYINSTALL'
import os, pathlib, sys
source, destination = map(pathlib.Path, sys.argv[1:])
destination.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'wb') as stream:
    stream.write(source.read_bytes())
PYINSTALL
launchctl bootstrap "gui/$(id -u)" "$keeper_plist"
```

RunAtLoad会立即执行真实维护。加载后核对唯一Label、实际配置/解释器/代码路径、真实输出与退出码、关页结果。文件处于Library/LaunchAgents仅证明已配置登录加载；未重登实测就如实记录，不为验收擅自重启或退出业务桌面。`retry_seconds=300`是最短退避门槛，仍需下一调度周期触发，不是每5分钟运行一次。

停用须区分：

- **本次登录会话临时卸载**：确认当前周期结束后，执行`launchctl bootout "gui/$(id -u)/$keeper_label"`；plist保留时下次登录会再次加载。
- **持久停用**：同样先卸载，再将这个目标的plist移出`~/Library/LaunchAgents`至私有备份目录（新路径，不覆盖已有备份），核对原路径已不存在。保留配置、状态、pending、日志和固定代码目录。
- **恢复**：确认无重复任务和有效执行路径，将该plist放回Library/LaunchAgents，再bootstrap并检查首跑。不得因此停止其他Bot或退出企业微信。

若周期卡住或有pending，先按保留记录的恢复流程处理，不删除锁或未决状态凑绿。升级使用新固定目录，保留旧配置、状态与回滚路径；验收与正式任务使用同一Python。停止旧目标任务后再验证新版本，避免两个版本并行；回滚也先停新任务，保留恢复记录。

给业务人员交付[执行清单](AGENT-RUNBOOK.md)中的本机结果卡：维护对象与权限、入口/真实续期/自然定时/关页结果、正式首跑与策略、项目/配置/日志/plist路径、持久停用与恢复方法。不要只回复“安装成功”。不上传私人证据或联系他人。每个新设备仍需自己的验收，不能将本分发包的远端记录当作当前设备通过。
