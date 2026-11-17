# 2026-11-17 AZW 每小时 GUI 残窗事故（根因与根治）

## 摘要

`com.fyaic.wecom-auth-keeper.821a7dd0403c`（`maintain.py`，azw 配置）自 2026-11-14 00:13 首轮成功后，**连续 83 次每小时运行全部失败**（`navigation_target_not_found`×63 / `navigation_unavailable`×9 / `navigation_focus_lost`×8），每次失败都在 WeCom 桌面遗留搜索下拉/全局搜索对话框，成为 wecom-bridge 侧多日每小时残窗（320×702 / 640×560）的**源头**：桥日志 2026-11-15..17 共 93 条残窗检测中 51 条与本任务 `checked_at` 精确配对（±12s，如 07:19:16.757→07:19:17、11:33:31.051→11:33:42）。残窗期间桥的 org 切换被堵，2026-11-17 08:59:37 一次真实发送被拒（见桥仓 `docs/incidents/2026-11-17-groupchat-dialog-wedge.md`）。

同主机的 `com.fyaic.wecomacl-renew`（keepalive）经其日志自证无罪：88/88 次运行全部死在配置校验（`read_docid` 占位符未填），从未触碰 GUI。

## 根因（代码级，全部实测）

| # | 缺陷 | 位置 |
| --- | --- | --- |
| 1 | **未到期也无条件全导航**：`run_cycle` 在任何 due 判定之前 `engine.open(activate=True)`；权限 2026-11-20 17:41 才到期（24h 维护窗 ⇒ 11-19 前不需要 GUI） | `keeper_maintenance.py`（修复前 :112） |
| 2 | **WeCom 搜索行为漂移**：搜索框粘贴+Return 的「Return 只导航」假设失效——Return 现在打开 **640×560 全局搜索对话框**（CG 残窗形态之一）并清空输入框，heading 永不匹配 → 每小时 8 秒超时失败 | `keeper_navigation.py`（修复前 `submit_search` 路径；取证 `tools/probe_navigation_failure.py`，/tmp/keeper_nav_probe/events*.jsonl） |
| 3 | **打字期下拉即残窗**：输入查询即弹出 **320×702 AXSystemDialog**（渲染初期更小），失败路径从不收起 | 同上（v2 探针实测形态） |
| 4 | **失败清理只关授权页**：`close_window` 仅关闭身份验证过的授权页；搜索下拉、聊天记录面板全部遗留（`docs/compatibility.md` 修复前自认） | `renew.py` close_window |
| 5 | 失败退避封顶 3600s ⇒ 永远每小时重试（与 #1 复合放大） | `keeper_maintenance.py`（修复前 :174） |

## 取证与修复对照

- **探针**：`tools/probe_navigation_failure.py`（worktree 分支）逐步复刻导航链——v1 证「粘贴落字 ✓、Return 被接收但打开对话框 ✗」；v2.x 证「下拉为 320×702 AXSystemDialog、行=AXStaticText(value)、主窗 below-fold 行报虚拟坐标 y≈2672、**界内精确同名行点击后 heading 匹配成功**」。
- **修复**（分支 `fix/2026-11-17-azw-hourly-residue-root-cure`）：
  1. **未到期先决门** `navigation_due`：全部目标行都无未决 `intent`、有 expiry 记录、均未临期（> now + within_hours）、数据新鲜（checked_at 距今 < `stale_after_hours`，新策略键默认 24h）、无未决撤销 journal ⇒ **零 GUI 返回 `not_due_skipped`（ok=true，exit 0）**，状态零副作用（failures/next_retry_at 原样）。缺记录/未决 intent/临期/陈旧/有 journal 任一 ⇒ 照常导航（保住首跑学习、到期续期与恢复优先语义——门审轮1 P1：`restored` 分支在 authorize 前持久化的 intent 无 journal 保护，必须同等强制导航）。
  2. **导航输入修复** `select_chat`：枚举打字期下拉中「**精确同名且完整落在其根窗口界内**」的会话行，唯一才点击；绝不 Return、绝不点未验名/界外（虚拟坐标）/歧义行；点击后仍以 heading 验证收尾。
  3. **清理军链** `restore_navigation`（挂在 run_cycle finally，**关页之后**——门审轮1 P2-3，天然消除授权页对主窗工具栏的遮挡）：置空全局搜索框（`set_value` 返回码校验，下拉随之收起）+ 唯一「关闭聊天记录」钮才点（收聊天记录面板）；逐步独立守卫（单窗枚举失败不吞其余）、绝不抛，结果入 `result["cleanup"]["navigation"]`。零坐标盲点。
  4. 失败退避逻辑保持不变（到期窗内 5min→1h 重试是有意设计；#1 的门已消除「未到期也在重试」的空转）。
- **纵深互补**：残余的搜索对话框类 CG 窗（如清理失败）由 wecom-bridge 弹窗守卫兜底（桥仓 2026-11-17 起按窗 pacing ≤tick+60s 自动点除）——本仓不重复实现坐标/键击清理，红线两侧都干净。

## 验证

- 单测 141 例全绿（新增：门六态含 intent + 策略校验 + 选择纪律三态 + 清理军链五态含返回码/多窗聚合 + skip 保 permissions + cleanup.navigation 接线；既有 submit 断言更新为验名行点击）；`scripts/check_repository.py` PASS。门审两轮：轮1 NOT LGTM（P1 intent 漏窗 + 5 P2）→ 整改 → 轮2 LGTM（0 P0/0 P1）→ P2 全收口。
- 现场验证（部署后）：首轮（状态陈旧 ⇒ 重验导航）走通修复后的选择路径并刷新 checked_at；此后每小时应见 `not_due_skipped` 且桥侧零新增残窗，直至 2026-11-19 17:41 进入到期窗。

## 遗留（人工事项）

- `com.fyaic.wecomacl-renew`（keepalive）配置占位符（`read_docid`/`write_docid`/`write_sheet`）未填，每小时空转报 `invalid_config`。需要真实 docid 数据或直接禁用该 launchd 任务——本次不动（无 GUI 影响，仅日志噪音）。
- 维护超时分支（`maintenance_timeout` + close_window 策略）由 maintain.py 单独拉起关页进程，**不经过** restore_navigation——该路径的遗留面板仍依赖桥侧守卫兜底（见桥仓特性）。
