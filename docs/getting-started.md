# 部署指南

[返回首页](../README.md)

当前发行形态是源码脚本，不是可独立 `pip install` 的包。先阅读[已知限制](known-limitations.md)，再决定是否用于自己的环境。

## 前置条件

- macOS 企业微信桌面端已登录，登录成员能管理目标机器人；保持可操作的图形会话。休眠、锁屏和其他桌面自动化可能影响结果。
- 已安装并授权 `@wecom/cli`。当前探针硬编码 `/opt/homebrew/bin/wecom-cli`，其他安装位置需要先调整脚本。
- 有可用的 `wecom-bridge` 源码与 Python 环境，其中 `wecom.ax.helpers` 可导入。该依赖链包含 Cocoa、Quartz、ApplicationServices 以及 bridge 自身配置依赖，请遵循所用 bridge 版本的安装说明。当前仓库未锁定一个可复现的 bridge 版本。
- Python 进程具备 macOS 辅助功能访问权限。
- 专用测试表：读探针调用 `sheet get`；写探针在指定子表首个单元格写入时间戳。不要把写目标设成业务表。

## 配置

```bash
cp config.example.json config.json
```

编辑 `config.json`：

| 字段 | 说明 |
|---|---|
| `bot_chat_name` | 目标机器人聊天名 |
| `aibotid` / `str_aibotid` | 目标授权链接中的参数；仅保存在本地 |
| `target_rows` | 默认两条文档能力的页面名称 |
| `read_docid` | 读探针在线表格 |
| `write_docid` / `write_sheet` | 专用写探针表及子表 |
| `venv_python` | 可导入 bridge helpers 的 Python **绝对路径** |
| `wecom_bridge_src` | bridge 的 `src` **绝对路径** |
| `bridge_send_link` | 是否通过 bridge 给机器人聊天发送授权链接；示例为 true |
| `bridge_url` | 对应 bridge HTTP 服务地址 |
| `notify_to` | 可选通知收件人；空字符串表示不通知 |
| `state_file` / `log_file` | 本地状态与日志；示例使用 `~/.wecom-auth-renew/` |

可从已有的 `850003` 报错 `help_message` 中取授权链接参数，不需要故意让正常业务过期。请勿公开包含真实参数的完整链接、配置文件或日志。

`bridge_send_link=false` 只关闭消息投递，不移除核心对 bridge Python 模块的依赖。当前脚本不会主动定位目标聊天：请先打开正确会话，确保已有授权链接在可见区域。开启投递时也应核对 bridge 使用的是同一企业微信会话。

## 交互检查与到期恢复

先创建示例配置所需目录；自定义路径时改为对应目录：

```bash
mkdir -p "$HOME/.wecom-auth-renew"
```

以下 `PYTHON` 须替换为配置中的 `venv_python`。检查会操作桌面；开启链接投递时也会发送消息。

```bash
PYTHON="/absolute/path/to/bridge/.venv/bin/python3"
"$PYTHON" renew.py --config config.json --check
```

核对目标机器人、两行权限和实际有效期。不要只看 `ok=true`：当前脚本可能在读取不完整时返回成功。

需要恢复已经到期的权限时：

```bash
"$PYTHON" renew.py --config config.json --renew
bash scripts/probe.sh
```

最后一条命令会写入测试表。读写探针都返回 0，才算这两项操作恢复。仓库 `--renew` 不会撤销尚未到期的权限；预续期仍是[实机验证中的独立流程](validation.md)。

## 可选：每小时调度

完成手工验证后，编辑 `scripts/com.fyaic.wecomacl-renew.plist.example` 中的仓库绝对路径，再安装：

```bash
mkdir -p "$HOME/Library/LaunchAgents"
cp scripts/com.fyaic.wecomacl-renew.plist.example \
  "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
plutil -lint "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
```

查看 `/tmp/wecom-auth-renew-keepalive.log` 和配置中的日志。现有失败告警并不覆盖所有错误场景；小时调度不是可用性保证。

停止调度：

```bash
launchctl bootout "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.fyaic.wecomacl-renew.plist"
```

调用方自愈需要在业务项目中实现：遇到能力过期 → 有界恢复 → 验证 → 重试一次；追加/创建类写入还需业务去重。该钩子未包含在本仓库。
