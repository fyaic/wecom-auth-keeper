# 企业微信 @人终极指南（给 Agent 看）

> 2026-11-09 定稿 | 三天调研 + 七轮双端实测 + 官方文档核验
> 如果你的 Agent 发企微消息 @ 不到人，这份文档直接告诉你为什么以及怎么做。

---

## 你为什么卡住了（90% 的人卡在这两个坑）

**坑 1：用了 wecom-cli 发消息，想 @ 人**

wecom-cli 的两条发送路径**都不能 @ 人**：

| 你可能在用的命令 | 为什么不行 |
|---|---|
| `wecom-cli message send` | 底层 API 只支持纯文本（text），**没有 markdown、没有 mentioned_list 字段**。写 `@名字` 只是普通文字。 |
| `wecom-cli message aibot send` | 支持 markdown 排版，但 **`<@userid>` 标签渲染为黑色普通文字**，不是真正的 @ 提醒（群内实测 + 官方文档确认）。企微网关服务端会拒绝未知字段。 |

**坑 2：用了 webhook 但方式不对**

| 你可能在用的方式 | 结果 |
|---|---|
| text 消息 + `mentioned_list` 参数 | 电脑端蓝色 ✓，**手机端黑色或不显示** ✗ |
| markdown_v2 消息 | **完全不支持 @**（官方文档明确说明） |

---

## 唯一正确的做法（生产验证，直接复制）

### 第一步：在目标群添加群机器人，拿到 webhook 地址

群设置 → 群机器人 → 添加 → 复制 Webhook URL（`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...`）

### 第二步：用这段代码发消息（零依赖，Python 3 直接跑）

```python
import json, urllib.request

def send_with_mention(webhook_url, text, userids):
    """
    唯一能在手机+电脑都显示蓝色 @ 卡片的 API 方式。
    webhook_url: 群机器人的 Webhook 地址
    text: 消息正文（支持 markdown 语法）
    userids: 企微 userid 列表（wobO- 开头）
    """
    mentions = ''.join(f' <@{uid}>' for uid in userids)
    payload = {
        'msgtype': 'markdown',   # 必须是 markdown（v1），不能是 markdown_v2
        'markdown': {
            'content': f'{text}{mentions}'
        }
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# ── 使用示例 ──
result = send_with_mention(
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key",
    "**【任务提醒】** 以下单据需要处理：",
    ["wobO-mCAAAxxxxxxxxxxxxxxx"],  # 被@人的企微 userid
)
print(result)  # {'errcode': 0, 'errmsg': 'ok'}
```

### 第三步：获取被 @ 人的 userid

| 方式 | 命令/操作 |
|---|---|
| wecom-cli 通讯录搜索 | `wecom-cli contact users search --json '{"keywords":["姓名中文字"]}'` → 返回 `userid` |
| 企微管理后台 | 通讯录 → 成员详情 → userid |
| 已有系统 | 项目权限名单中的 `principal_userid` 字段 |

---

## 两个硬性前提（不满足则 @ 无效）

1. **被 @ 的人必须是该群的成员**。群机器人无法 @ 群外成员——API 返回 errcode=0（成功），但对方收不到任何提醒。这是最常见的"看起来发了但没人收到"的原因。
   - 排查：让被 @ 的人在该群里发一句话，或导出群成员名单核对。

2. **userid 必须正确**。企微 userid（`wobO-` 开头），不是手机号、不是邮箱、不是机器人自己的 ID。

---

## 验收标准（新群/新机制必做，一次性）

发一条测试消息后，被 @ 的人用**手机和电脑各看一遍**：

| 检查项 | 通过标准 |
|---|---|
| @ 颜色 | 蓝色（手机+电脑都是蓝色） |
| 提醒推送 | 企微弹出通知 |
| 点击 @ | 能打开对方名片 |

**⚠️ 不要用 API 返回码验收**——errcode=0 与 @ 是否生效完全无关，API 不校验 @ 有效性。

---

## 完整决策树

```
需要 @ 人？
├── 是 → 必须走 webhook 群机器人
│   ├── 消息类型: markdown（v1）
│   ├── @ 语法: <@userid> 写在 content 里
│   ├── 前提: 被@人在群里 + userid 正确
│   └── ⚠️ 不要用 markdown_v2（不支持@）
│       不要用 text + mentioned_list（手机端不渲染）
│
├── 不需要 @，只需发消息
│   ├── 富消息（文件/图片/语音/视频）→ wecom-cli message aibot send
│   └── 纯文本 → webhook text 或 CLI 均可
│
└── 两者都需要（通知带@ + 发文件）
    └── 组合使用：webhook 发带@的通知 + CLI 发文件
```

---

## 故障速查表

| 症状 | 根因 | 解法 |
|---|---|---|
| 手机上 @ 是黑色 | 用了 text+mentioned_list | 换 markdown 内嵌 |
| 双端都不显示 @ | 人不在群 / userid 错 | 拉人进群 / 核对 userid |
| 正文出现 `<@wobO-...>` 原始字样 | markdown 没生效 | 确认 msgtype=markdown |
| @ 显示但没弹提醒 | 客户端通知关了 | 检查企微消息通知设置 |
| errcode=0 但什么都没发生 | API 不校验 @ 有效性 | 按验收流程真人验证 |
| wecom-cli 里怎么写都不行 | CLI 两条路径都不支持 @ | 改走 webhook |
| 消息内容含代码块导致 @ 失效 | markdown 复杂结构干扰解析 | 保持 @ 标签附近格式简单 |

---

## 官方依据

- [消息推送配置说明（企业微信开发者中心）](https://developer.work.weixin.qq.com/document/path/91770)：`<@userid>` 为消息推送 text/markdown **专属**；markdown_v2 不支持
- [WecomTeam/wecom-cli](https://github.com/WecomTeam/wecom-cli) 官方技能文档：CLI 两条路径均无 @ 能力
- 实测环境：macOS 桌面端 5.0.13 + iOS 手机端，2026-11-07 双端验证

---

## 底层原理（可选阅读）

企微的消息通道有两套：

1. **群机器人 webhook**：直连底层应用消息 API，完整支持 `<@userid>` 扩展语法 → 真提醒
2. **智能机器人（aibot）通道**：走独立的 bot 平台 API，平台层面未实现 mention 渲染 → 黑色文字

wecom-cli 连的是 aibot 通道（`message aibot send`）和用户消息通道（`message send`），都不经过底层应用消息 API 的 markdown 渲染管线，所以 `<@userid>` 到了客户端就只是普通文本。

**这不是写法问题，是通道能力差异**。想要蓝色 @ 卡片，必须走 webhook。
