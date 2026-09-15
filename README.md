# wecom-auth-keeper —— 企业微信 wecom-cli 能力授权自动续期（授权保活）

> 解决 wecom-cli（@wecom/cli）「文档」能力授权 **7 天到期必须人工续** 的平台限制。
> 适用于一切用 wecom-cli 读写在线文档/表格的无人值守项目（询盘登记、报表、同步任务……）。
> 实战验证：2026-09-14 起在生产环境全自动续期运行（读写双线各真实续期成功，含全程无人值守案例）。

## 一、问题是什么（为什么需要这个方案）

wecom-cli 操作文档/表格要过三层门，前两层是自动的，**第三层是本方案要解决的**：

| 层 | 是什么 | 有效期 | 自动吗 |
|---|---|---|---|
| ① Bot ID + Secret | bot 的身份密码（本地 credentials.enc） | 长期 | — |
| ② 访问 token | 每次调用的通行卡 | **24 小时** | ✅ 到期自动静默刷新（errcode 853004，无感） |
| ③ **能力授权** | 一个人（成员）点头同意"允许这个 bot 用文档能力" | **7 天，读/写两条独立线** | ❌ **到期报 850003，调用再多也不续期，官方无自动续期机制**（上游 [#87](https://github.com/WecomTeam/wecom-cli/issues/87) 悬置两月"待产品评估"） |

关键实证结论（两周实机观测 + 服务端授权页 UI 直接确认）：

- 读（搜索与获取文档内容）与写（新建与编辑文档）是**两条独立计时的 7 天线**，锚定各自的授予时刻，到期时刻精确到分（授权页直接显示"有效期至 M/D HH:MM"）；
- **持续调用不续期**——每天探针 + 真实业务调用，仍按授予时刻整点死亡；
- 官方 FAQ 称"到期后机器人主动推送续期链接"——**实测从未发生**（创建者收件箱零消息）；
- 续期 = 在授权页对到期项点一下「授权」，即开新 7 天时钟；已授权项可"取消授权→再授权"预续期（该按钮仅工作台路径页面渲染，自动到达不稳定，见 docs/auth-model.md）。

## 二、方案架构（三层防线，全无人值守）

```
每小时 launchd → keepalive-run.sh
    ├─ 双探针（纯 CLI，零 GUI）：读业务表 + 写 bot 自有测试表各一次
    ├─ 任一 850003 → renew.py --renew：
    │     链接消息在/发进机器人聊天 → 点击气泡 AXLink（聊天区 AX 最稳定）
    │     → 企微内置浏览器打开「可使用权限」页（登录会话现成，零扫码）
    │     → 页面为规整 AXWebArea：能力名/已授权/有效期至/授权按钮全可读
    │     → 点击到期行的「授权」按钮（轮询确认 ≤30s×3 补点，处理确认弹窗）
    │     → 复读验证新有效期（+7 天）
    ├─ 复探双绿确认 → 企微通知创建者（✅成功 / ⚠️需人工）
    └─ 业务侧自愈（可选，集成到调用方）：调用撞 850003 → 当场触发 renew → 重试一次
```

死窗分析：到期 → 下一整点探针最长 1 小时；期间业务任务由"调用侧自愈"吸收（自动续期 + 重试，约多等 1 分钟）；最坏情况（自动续期自身失败）每小时自动重试 + ⚠️通知人工兜底。

## 三、部署（10 分钟）

### 前置

1. macOS 企微桌面端**常驻登录**（会话属于能授权该 bot 的成员；机器不休眠——`caffeinate` 常驻或设置永不睡眠）；
2. 已装 wecom-cli（`npm i -g @wecom/cli`）并完成 `auth init`（绑定目标 bot）；
3. 一个 pyobjc 环境（本仓库只借用其 AX 库；任何含 `pyobjc-framework-Quartz` 的 venv 均可）；
4. （可选）wecom-bridge HTTP 服务——用于自动把链接发进聊天 + 收通知；不配则复用聊天中已有的授权链接（静态地址、历史消息永久可点）。

### 步骤

```bash
git clone <本仓库> && cd wecom-auth-renew
cp config.example.json config.json   # 已 gitignore，填入：
#   bot_chat_name   机器人会话名（在企微里跟 bot 的聊天标题）
#   aibotid / str_aibotid  从任意一次 850003 报错的 help_message 续期链接里取参数
#   read_docid      业务侧任一 bot 可读的表格 docid（读探针用）
#   write_docid/write_sheet  bot 自建一张测试表（写探针用，别用业务表）
#   venv_python / wecom_bridge_src  指向 pyobjc venv 与其 src 目录
#   notify_to / bridge_url  通知接收人 + bridge 地址（不配则不发通知）
# 先验证只读模式：
<venv_python> renew.py --config config.json --check
# 应输出两条权限线的 authorized + 有效期，与授权页一致
# 装 launchd（每小时）：
cp scripts/com.fyaic.wecomacl-renew.plist.example ~/Library/LaunchAgents/<改路径>.plist
launchctl load ~/Library/LaunchAgents/<...>.plist
```

### 业务侧自愈（推荐给调用方集成）

调用 wecom-cli 的代码在收到 `errcode=850003` 时：调 `renew.py --renew`（有并发锁，可与保活并行）→ 原调用重试一次。参考实现见 [wecom-lead-register 的 cli() 钩子](../wecom-lead-register/skill/register.py)。

## 四、已知边界与注意事项

- **取消授权按钮**：仅工作台路径页面渲染（悬停/点击可唤出），内置浏览器版页面不渲染——故本方案采用"到期后点授权"；预续期（取消→重授权）自动化路线的踩坑记录见 docs/auth-model.md §5；
- 授权页控件读取的三个坑（都已在本仓库代码内处理）：零宽字符清洗（`\u200b`）、AXTitle-or-AXValue 双取、相对坐标关联（抗窗口位移）；
- **launchd 无工作目录**：bridge 类依赖从 cwd 找 .env——本仓库 renew.py 已在 import 前 chdir，集成时勿删；
- 探针写目标必须是 **bot 自有的测试表**（写时间戳无害化）；不要探针写业务表；
- 企微桌面端离线/重启中：探针照常报错、续期跳过，下一整点自动重试；连续失败会持续 ⚠️ 通知；
- CEF 输入合成（CGEvent 打字/粘贴）对企微网页面板**无效**——本方案全程不需要打字（点击 + 链接复用），如需输入请用 System Events AppleScript 定向按键（见 docs/auth-model.md §4）。

## 五、文件清单

| 文件 | 作用 |
|---|---|
| `renew.py` | 核心：开授权页、读权限线状态、点授权续期（--check/--renew） |
| `scripts/probe.sh` | 双探针（读+写，纯 CLI） |
| `scripts/keepalive-run.sh` | 每小时联动主循环（探针→850003→renew→复探→通知） |
| `scripts/com.fyaic.wecomacl-renew.plist.example` | launchd 模板 |
| `config.example.json` | 配置模板（复制为 config.json，已 gitignore） |
| `docs/auth-model.md` | 授权模型全档：发现过程、实证时间线、机制定论、踩坑实录 |

## 六、来源与致谢

本方案诞生于一个外贸团队的无人值守询盘登记项目两周生产实战，上游反馈沉淀于 [WecomTeam/wecom-cli#134](https://github.com/WecomTeam/wecom-cli/issues/134)（读 850003 写绿首例 + 双 7 天线实证 + 续期链接通道发现）。授权模型的完整取证记录见 `docs/auth-model.md`。
