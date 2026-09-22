# 部署指南

[返回首页](../README.md) · [命令与退出码](#命令与退出码)

## 安装

需要 macOS、Python 3.11+、已登录的企业微信桌面端，以及有权管理目标机器人的成员身份。GUI 必须可操作；休眠、锁屏和其他自动化会影响执行。

```bash
git clone https://github.com/fyaic/wecom-auth-keeper.git
cd wecom-auth-keeper
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-macos.txt
cp config.example.json config.json
```

原生 AX 适配层已内置，不再需要 `wecom-bridge` 源码或它的 `.env`。依赖固定在 `requirements-macos.txt`。Python 进程仍需 macOS 辅助功能访问权限；程序不会自动弹框申请。

使用探针前需自行完成 `wecom-cli` 安装及 bot 授权。程序不读取或输出本地凭据，也不会自动 `auth init` 切换 bot。

## 配置

| 字段 | 说明 |
|---|---|
| `bot_chat_name` | 目标机器人会话名；供可选的链接投递使用 |
| `aibotid` / `str_aibotid` | 同一目标授权链接中的两项身份参数；均须字符串，仅保存在本地 |
| `target_rows` | 需要检查/恢复的能力行名；默认文档读、写两项 |
| `read_docid` | CLI 读探针表格 |
| `write_docid` / `write_sheet` | **专用测试表**及子表；写探针覆盖其 A1 单元格 |
| `wecom_cli` | 默认从 PATH 找 `wecom-cli`，也可设绝对路径 |
| `venv_python` | 运行 GUI 恢复子进程的 Python，填写本仓库 `.venv/bin/python3` 的绝对路径 |
| `state_file` / `log_file` | 状态快照与保活 JSONL 日志；相对路径基于配置文件目录 |
| `probe_timeout` | 每次 CLI 探针超时秒数 |
| `renew_timeout` | 保活启动的 GUI 子进程总超时秒数 |
| `lock_wait` | 等待进程锁的秒数；超时退出 4 |
| `bridge_send_link` | 可选：通过 bridge 发授权链接；默认 false |
| `bridge_monitor` | 可选：操作前切 observe、完成后恢复原模式；默认 false，与发送开关独立 |
| `bridge_url` / `notify_to` | 可选 bridge HTTP 地址与通知接收人；默认不通知 |

从已有的 850003 报错帮助链接或正确机器人的管理权限页取得身份参数；不要为了取链接让业务故意过期。CLI 当前凭据必须对应同一 bot——配置页身份校验不自动验证 CLI 凭据归属，部署者应核对。

旧 `wecom_bridge_src` 配置不再需要。旧配置未指定 `bridge_monitor` 时，保持与 `bridge_send_link` 一致的兼容行为；建议显式设定。

## 本地检查

填写真实配置后运行：

```bash
.venv/bin/python renew.py --config config.json --doctor
```

该命令只检查配置、平台、可导入模块与 CLI 可执行路径；不发消息、不打开 GUI、不探测业务权限，也不证明辅助功能权限已就绪。它检查的是当前 Python 进程，`venv_python` 应指向同一个环境。

## 检查与到期恢复

先在企业微信中打开目标 bot 的“可使用权限”页：

```bash
.venv/bin/python renew.py --config config.json --check --existing-window
```

`--check` 不改授权、不发消息、不改 monitor；它会写本地状态。省略 `--existing-window` 时可点击当前可见的目标授权链接，但不会主动切换到指定聊天。页面必须暴露匹配两项 bot 参数的 AXWebArea URL，否则拒绝操作。

恢复已经到期的配置项，然后验证业务读写：

```bash
.venv/bin/python renew.py --config config.json --renew
.venv/bin/python probe.py --config config.json
```

第二条会写专用测试表。GUI 成功只说明页面状态健康；保活流程还要求读写探针都通过。

## 实验性预续期：现有窗口模式

在目标 bot 详情打开“可使用权限”，保持页面可操作；脚本会滚动目标控件：

```bash
.venv/bin/python renew.py --config config.json \
  --pre-renew --existing-window --within-hours 24
```

仅处理指定能力中 24 小时内到期的行；已到期的行直接重授，健康且远于阈值的行跳过。每次只取消并恢复一条，再进入下一条。此命令会滚动目标控件并复查页面边界，但不会自动导航管理列表。

取消前持久化 `<state_file>.pending.json`。中断后，程序优先重授；仍失败则保留记录并停止。下一次 `--renew` 或保活会优先尝试该记录。不要为了消除报错直接删记录，应先确认目标权限已经恢复。存在无法确认取消是否发生的情况时，可能需要人工复核。

2026-09-22 已用独立脚本完成文档读写、通讯录三项真实预续期，重开页面复核一致。详见[实测记录](validation.md)及[临时方案](workaround.md)。本次没有运行业务 API 探针，完整导航、干净 Mac 部署和跨周期运行仍待验收。

### 选择能力范围

`target_rows` 使用页面上的能力行名，不是“文档”等分类名。例如：

```json
{
  "target_rows": ["新建与编辑文档", "搜索与获取文档内容", "搜索企业成员"]
}
```

这是现有配置的片段。文档只读可仅保留 `搜索与获取文档内容`；通讯录是 `搜索企业成员`。未列出的行不会被操作。“授权”按钮不能区分从未授权与已经过期，因此白名单也代表允许授予的能力。默认文档读写探针不会随白名单自动变成通讯录探针；只做通讯录续期时应直接调用 `renew.py`，并单独验证相应业务调用。

## 每小时保活

```bash
.venv/bin/python keepalive.py --config config.json
```

**此调度用于文档权限到期后恢复，不运行 `--pre-renew`，也不按 GUI 有效期提前触发续期。** 预续期需单独调用上节命令，并满足目标页面已经打开的条件。

行为：双探针 → 850003 或 pending 恢复记录 → 有界 GUI 恢复 → 双探针复核。非授权错误只报告，不盲目点击 UI。通知需显式配置收件人与 bridge；相同状态六小时内抑制重复通知，状态恢复时通知。

兼容入口仍可使用 `bash scripts/probe.sh` / `bash scripts/keepalive-run.sh`，都接受 `--config`。**其输出已改为单个 JSON，失败非零退出**，旧版解析 `read_errcode=...` 的调用方需迁移。

编辑 `scripts/com.fyaic.wecomacl-renew.plist.example` 中的仓库路径，确认配置内 `venv_python` 正确，再安装：

```bash
mkdir -p "$HOME/Library/LaunchAgents"
cp scripts/com.fyaic.wecomacl-renew.plist.example \
  "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
plutil -lint "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
```

停止调度：

```bash
launchctl bootout "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
```

日志目录由程序创建。状态使用原子替换与 0600 文件权限；同一 macOS 用户的 GUI 恢复共用生命周期锁，不按超时删除另一个进程的锁。异常直接终止时，操作系统释放锁，未完成预续期记录保留。

## 命令与退出码

| 退出码 | 含义 |
|---|---|
| 0 | 当前命令检查通过；不代表所有业务流程通过 |
| 2 | 权限不健康、操作失败或无法可靠判断；无效命令行参数也使用 argparse 的标准退出码 2 |
| 3 | 配置、平台或依赖问题 |
| 4 | 另一个进程持有锁，等待超时 |

正常执行与运行错误在 stdout 返回单个 JSON。`--help` 和命令行解析错误使用标准 argparse 输出。保活通知发送失败也返回非零，即使探针本身已经恢复。
