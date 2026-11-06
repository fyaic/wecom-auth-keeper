# 安装 Agent 执行协议

适用 Codex、WorkBuddy 或其他具备本机终端/文件访问能力的 Agent。此文件描述软件安装流程，不授权替用户发送消息、上传诊断、创建业务数据或扩大 Bot 权限。用户明确要求优先。不要仅凭依赖安装、AX 可读或 exit 0 宣称续期成功。

## 0. 先核对包与设备，不操作 UI

- 检查维护者提供的 ZIP SHA-256；解压后运行 `python3 delivery/verify_bundle.py`（Windows 可用 `py -3`）。包内散列只检测损坏，不证明发布者身份。
- 运行 `python3 delivery/onboard.py`。它只用标准库，Windows 不会导入 macOS 专用模块。没有 Python 时先说明需安装 Python 3.11+；在用户允许安装软件后用可信官方来源安装，不能远程下载后不检查就执行未知脚本。
- macOS 读取企业微信安装路径、版本、CPU 架构；未识别版本写 unknown，不能猜。Windows 返回 unsupported_automation_backend：停止自动化安装，不安装 pyobjc，不生成 launchd 或伪造 Windows 计划任务成功。按 DESIGN.md 的 Windows 验收方案交维护者处理。
- 只读检查现有 launchd 任务/配置，识别同一 Bot 是否已经在维护。不要启动重复作业或覆盖原配置。不要修改本机其他 Bot 的凭据、业务目录或常驻服务。

## 1. 获取这台机器自己的身份和范围

询问业务人员企业名、机器人名及需要哪些能力。利用本机已有 wecom-cli 的帮助、状态和身份查询确认当前 profile 的 Bot；CLI 命令随版本变化，先看本机 `--help`，不要猜参数，不自动 auth init 切换已在用的 Bot。

从用户指定 Bot 的官方权限页或本地已有 850003 帮助链接取得 authorization_url。只在指定 profile/业务日志内查找，不扫描整台电脑的凭据。不回显完整链接、Bot ID、聊天内容或认证数据。链接必须为官方 HTTPS 路径且同时包含两个 Bot 标识；其中 str_aibotid 必须和现场 CLI Bot ID 相同。机器人名字和企业文字仅作导航线索。

在仓库/安装包目录外建立权限为 0700 的私有目录，在其中保存以下输入 JSON（0600）。下面是字段示意，必须替换成本机值：

```json
{
  "bot_chat_name": "<本机目标机器人完整会话名>",
  "organization_name": "<本机目标企业>",
  "authorization_url": "<本机官方权限链接>",
  "cli_bot_id": "<刚刚从指定CLI profile核验的Bot ID>",
  "target_rows": ["搜索与获取文档内容", "新建与编辑文档"]
}
```

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

## 3. 企业与页面导航验收

- 先检查当前企业、目标 Bot 及权限页双身份。不要凭同名会话、头像坐标或页面标题直接授权。
- 聊天记录路径要求目标聊天已有对应官方授权链接；新机器不一定有历史消息。若没有，应先在管理界面核验身份。发送链接到聊天是消息发送，只有用户明确允许播种时才执行；不要把“能打开页面”当成后台以后也能自动找到。
- 5.0.13 曾出现聊天消息懒加载，首次需打开聊天让链接渲染。对新布局应观察 AX 结构并与预期比对；未知结构停止，不能根据旧截图固定坐标点击。
- 先运行 `renew.py --check` 获取完整权限和日期；该命令可能导航/切换前台但不改授权。用 finally 调用 `renew.py --close-window`。
- 当前组织自动切换仍是启发式候选导航。确需使用时，在私有配置增加 organization_name，可选 organization_markers；标记不得使用常见“机器人/授权”等词。记录从其他企业切回、选择正确会话、双 Bot 身份匹配的证据。若重名、面板歧义或无法证明组织已切换，停止并保持自动切换关闭。不要恢复或切到未知企业。

## 4. 实际后台链路与续期分层验收

1. **配置层**：doctor/字段校验，只说明依赖和配置可用。
2. **桌面检查层**：相同登录用户、Python 和启动链读取目标权限及日期、干净关页。终端的权限不能证明 launchd 子进程有辅助功能权限。让用户在系统设置对真实执行主体授权；不修改 TCC、不重置全局授权、不借用其他程序绕过检查。
3. **真实续期层**：对已确认白名单中的临近到期项运行 `maintain.py --config ...`。记录每项前后日期、pending 为 false、关页成功，并用同 Bot 的只读业务调用复查。业务写验证或发消息需用户另行授权。健康但未到阈值的检查只算检查通过。
4. **提前验收（可选）**：如用户明确同意现在取消/重授一次，可用隔离配置/状态临时设 within_hours=168，只针对同意的权限。验收后恢复生产24小时，不让168小时进入生产任务。没有到期项、也没有该授权时，标记 renewal_pending；到自然窗口后观察真实续期，不能虚报完成。

记录 `delivery/acceptance.example.json` 的副本到私有目录。只填实际证据。多权限至少检查所有白名单项；某项成功不等于所有项成功。已有一个 Bot 的验收不能代表其他 Bot 或其他系统版本。

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
