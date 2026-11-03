# 装柜提醒bot 授权自动续期：部署手册

目标：让 warecheck 依赖的 `wecom-cli` 权限（智能表格读写、通讯录搜索）在 7 天有效期到期前自动续期，消除 850003 停更事故的人肉续期环节。复用本仓库 `maintain.py` 多权限预续期引擎（每小时检查、提前 24 小时逐项续期、逐项进度与冷却、断点恢复），本分支只补齐 didadi 部署资产。

## 为什么是这些权限

| target_rows | 依据 |
| --- | --- |
| 搜索与获取文档内容 / 新建与编辑文档 | v2 装柜表（smartsheet）读写、客服操作手册在线页 |
| 搜索企业成员 | v1 验货 flow2 每次 @身份解析（`contact users search`），v2 通知客服解析 |
| （不加）发送消息 | 本企业 853006 不可用；群通知走 webhook 机器人，与 bot 授权无关 |

## 1. 取两项身份参数（唯一人工步骤）

`aibotid`（数字）与 `str_aibotid`（aib 开头）来自**机器人管理权限页链接**：企业微信 → 工作台 → 智能机器人 → 装柜提醒bot → 授权文档使用权限，页面 URL 内含两参数。已知 str_aibotid 应等于 `wecom-cli auth show` 的 Bot ID（`aibNIF3gzZPv1vFefOO9BgLY1u4TzaL0W5Y`），可用作核对。不要为了取链接让业务授权故意过期。

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
