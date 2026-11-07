# 企业微信群机器人 @人的正确姿势（白色卡片/蓝色@版）

> 面向 agent/开发者。2026-11-07 双端（macOS 桌面端 + 手机端）实测定论。
> 适用场景：通过群机器人 webhook 发消息并希望 **@ 到具体的人且对方收到提醒**。

## TL;DR（一眼版）

**用 `markdown` 消息 + 把 `<@userid>` 直接写进正文。** 不要用 `text + mentioned_list`（手机端不渲染）。

```json
{
  "msgtype": "markdown",
  "markdown": {
    "content": "**【任务提醒】** <@wobO-XXXXXXXX> 这单今天 17:00 前需要确认"
  }
}
```

## 两种机制实测对比

| 机制 | 桌面端 | 手机端 | 提醒推送 | 结论 |
| --- | --- | --- | --- | --- |
| `text` + `mentioned_list: [userid...]` | 蓝色 ✓ | **黑色或不显示** ✗ | 桌面✓ 手机不稳定 | 弃用 |
| `markdown` + 正文内嵌 `<@userid>` | **蓝色 ✓** | **蓝色 ✓（白色卡片样式）** | **双端 ✓** | **采用** |

## 正确实现（Python，零依赖）

```python
import json, urllib.request

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"

def send_markdown_mention(webhook_url, text, userids):
    """text 里 @ 标签由本函数拼在开头；userids 为企微 userid 列表（wobO- 开头）。"""
    mentions = ''.join(f' <@{uid}>' for uid in userids)
    payload = {
        'msgtype': 'markdown',
        'markdown': {'content': f'{text}{mentions}'},
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    assert result.get('errcode') == 0, result
    return result

send_markdown_mention(
    WEBHOOK_URL,
    '**【数据确认提醒】** 以下单据需要今天处理：',
    ['wobO-mCAAAxxxxxxxxxxxxxxx'],  # 被@人的企微 userid
)
```

## 硬性前提（@不生效的真正原因排序）

1. **被 @ 的人必须是该群的成员**。群机器人无法 @ 群外成员——API 照样返回成功（errcode=0），
   但客户端不渲染提醒、收不到推送。**这是最常见的坑：发送成功 ≠ @ 成功**。
   → 排查：让被 @ 的人在该群里随便发一句话；或导出群成员名单核对。
2. **userid 必须正确**：企微 userid（`wobO-` 开头），不是手机号、邮箱、也不是机器人自己的 id。
3. `markdown` 消息**不支持** `mentioned_list` 字段——@ 标签必须在正文里，写了字段也没用。
4. 正文 ≤ 4096 字节（markdown 上限），超长会被拒。

## 获取 userid 的三种方式

| 方式 | 适用 |
| --- | --- |
| `wecom-cli contact users search --json '{"keywords":["姓名中文字"]}'` → 返回 `userid` | 已部署 wecom-cli 且有"搜索企业成员"权限的机器人 |
| 企业微信管理后台 → 通讯录 → 成员详情 | 人工查单个 |
| 项目已有的权限名单（如 access-plan.json 的 `principal_userid`） | warecheck 系项目 |

## 一次性验收（新群/新机制必做）

向测试群发两条对照消息，被 @ 的人用**手机和电脑各看一遍**：

- ① @ 是否显示、什么颜色（蓝色=有效；黑色/不显示=无效）
- ② 企微是否**弹出提醒通知**（这是功能的本质；颜色只是渲染）
- ③ 点 @ 名字能否打开名片

三条全过才算接通。**不要用 API 返回码验收**——errcode=0 与 @ 是否生效完全无关。

## 常见故障速查

| 症状 | 原因 | 解法 |
| --- | --- | --- |
| 电脑蓝、手机黑 | 用了 text+mentioned_list | 换 markdown 内嵌 |
| 双端都不显示 @ | 人不在群 / userid 错 | 拉人进群 / 核对 userid |
| 正文出现原始 `<@wobO-...>` 字样 | markdown 语法没生效或版本过旧 | 确认 msgtype=markdown；升级客户端 |
| @ 显示但没人收到推送 | 客户端通知设置关了 | 让成员检查企微消息通知设置 |
| errcode=0 但一切没发生 | 见上——API 不校验 @ 有效性 | 按验收流程真人验证 |
