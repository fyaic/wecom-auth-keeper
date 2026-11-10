# 装柜提醒bot 授权自动续期：部署手册

目标：让 warecheck 依赖的 `wecom-cli` 权限（智能表格读写、通讯录搜索）在 7 天有效期到期前自动续期，消除 850003 停更事故的人肉续期环节。复用本仓库 `maintain.py` 多权限预续期引擎（每小时检查、提前 24 小时逐项续期、逐项进度与冷却、断点恢复），本分支只补齐 didadi 部署资产。

## 为什么是这些权限

| target_rows | 依据 |
| --- | --- |
| 搜索与获取文档内容 / 新建与编辑文档 | v2 装柜表（smartsheet）读写、客服操作手册在线页 |
| 搜索企业成员 | v1 验货 flow2 每次 @身份解析（`contact users search`），v2 通知客服解析 |
| （不加）发送消息 | 本企业 853006 不可用；群通知走 webhook 机器人，与 bot 授权无关 |

## 1. 取两项身份参数（通常零人工）

`aibotid`（数字）与 `str_aibotid`（aib 开头）来自机器人授权页链接。**本机已有现成来源**：wecom-cli 的 850003 错误日志（`~/.config/warecheck-v2/wecom-directory-didadi/log/ww.log.*`）中的帮助链接即含两参数，且 `str_aibotid` 应等于 `wecom-cli auth show` 的 Bot ID（`aibNIF3gzZPv1vFefOO9BgLY1u4TzaL0W5Y`），用作交叉核对。仅在日志已轮转清空时才需从「企业微信 → 工作台 → 智能机器人 → 装柜提醒bot」管理页链接现取。不要为了取链接让业务授权故意过期。

## 1b. 一次性播种聊天（必做，约 1 分钟）

引擎靠「与目标机器人的聊天记录」导航到授权页。若该 Mac 上没人跟 bot 聊过天，首轮会报 `navigation_target_not_found`。播种一次永久有效：

1. 打开桌面企业微信 → 顶部搜索「装柜提醒bot」→ 打开与它的聊天（首次会自动创建会话）
2. 把下面的链接整条粘贴发送到该聊天（谁发的都行，引擎只搜记录）：

```
https://work.weixin.qq.com/ai/aiHelper/authorizationList?from=chat&forceInnerBrowser=1&aibotid=33777000565280640&str_aibotid=aibNIF3gzZPv1vFefOO9BgLY1u4TzaL0W5Y&type=1
```

3. 保持 `chat_history_navigation: true`（模板默认已开）

播种后触发一轮（kickstart 或手动 `maintain.py --config ...`），成功标志：状态里 `permissions` 出现各项有效期、`rows` 非空。

**企业微信 5.0.13 实测补充（2026-11-03）**：消息列表有懒加载——播种后需让该聊天在桌面端打开过一次（消息渲染后链接才以 AXLink 暴露），引擎即可正常导航；首个成功样本：三项权限读出有效期、未到期不操作、页面自动关闭。首次完整自动续期预计出现在有效期前 24 小时的整点巡逻。

## 2. 私有配置（不入库）

```bash
mkdir -p ~/.config/warecheck-v2/wecom-auth-keeper
cp config.didadi.example.json ~/.config/warecheck-v2/wecom-auth-keeper/maintain-didadi.json
# 编辑：替换两项占位符；venv_python/state_file/log_file 按模板默认即可
```

预检（不碰 GUI；含 CLI 绑定 bot 与配置一致性校验）：

```bash
.venv/bin/python scripts/preflight_didadi.py --config ~/.config/warecheck-v2/wecom-auth-keeper/maintain-didadi.json
```

## 3. 生成并安装定时任务

**一次性系统授权（仅首次）**：系统设置 → 隐私与安全性 → 辅助功能 → 「+」→ 按 `Cmd+Shift+G` 粘贴 `/Users/veil/projects/wecom-auth-keeper/.venv/bin/python3` → 添加并保持开启。launchd 拉起的 Python 没有该权限时，首轮即报 `accessibility_permission_unavailable` 并进入冷却重试，授权后下一轮自动恢复（无需重启任务）。

```bash
CFG=~/.config/warecheck-v2/wecom-auth-keeper/maintain-didadi.json
.venv/bin/python maintain.py --config "$CFG" --write-launchagent ~/Library/LaunchAgents/com.fyaic.wecom-auth-keeper.didadi.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fyaic.wecom-auth-keeper.didadi.plist
```

标签含身份哈希，与 kaopu 等其他 bot 的任务互不冲突。回滚：`launchctl bootout + disable` 后删除 plist。

## 4. 验证与观察

- `maintain.py --config "$CFG" --status`：看每项权限的页面有效期、下次续期时间、失败冷却（不访问企业微信）
- 首个周期内人工看一眼续期动作（需要桌面锁内操作企业微信窗口，期间勿动键鼠）
- 业务侧最终验证：`wecom-cli smartsheet fields ...` 与 `contact users search` 正常；warecheck 管线照常 `ok`
- 状态/日志：`~/.wecom-auth-renew/didadi/state.json.maintenance.json`、`run.log.maintenance.log`

## 5. 已知边界（与引擎一致）

- 需要常驻、已登录、未锁屏的 macOS 桌面会话；跨设备/锁屏行为未验收
- 页面续期成功不等于业务验证（引擎显式 `business_verified: false`），业务侧由调用方（warecheck 管线）验证
- 若企业微信改版导致控件结构变化，续期会失败进冷却重试——warecheck 侧 850003 停更告警（管理员群）仍是最终兜底
