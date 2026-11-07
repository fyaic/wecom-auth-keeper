# 与 WeCom Bridge 共用桌面

此版本为内部验收候选；单元测试不等于远端续期通过。没有 Bridge 的普通 Mac 不需要此集成。

## 协议

- 同一 macOS 登录用户共用 `~/.wecom-auth-renew/desktop.lock`，不可删除或替换这个文件。
- Keeper 在完整导航、逐项授权、关页及超时清理期间持有独占锁。监督器子进程继承文件描述符，父进程异常退出也不能提前把仍在工作的子进程桌面释放出去。
- Bridge 为完整 UI 工作持共享锁。既有内部线程锁继续生效；组织轮巡和监控新周期在忙时跳过本次，不消费侧栏快照。HTTP UI 请求返回 503 desktop_busy，尚未开始发送，也不消费幂等键。健康检查、协调能力接口与数据 WebSocket 保留。语音通话在完整生命周期持锁，续期等待而不打断通话。
- Keeper 写入交接代次。Bridge 恢复操作前重新核验原生当前组织并更新监控与轮巡；无法核验则拒绝继续，避免续期切换组织后使用旧缓存。
- 不修改 Bridge 的 active/observe 模式，不暂停进程，不改变服务的启动设置。系统锁会在全部持有者关闭描述符后释放；原生 AX 卡死的存活子进程仍会占锁，必须如实报告，不能强行删除锁。

## 配置与验收

先按 Bridge 仓库的生产部署规则更新支持协议的版本，再在包外私有配置设置：

```json
{"bridge_monitor": true, "bridge_url": "http://127.0.0.1:23392", "bridge_coordination": "shared-lock-v1", "bridge_send_link": false}
```

能力接口为 `GET /wecom/desktop/coordination`。Keeper 在已持锁时验证 protocol、uid、设备号、inode 和 handoff_refresh；接口不可用或任何项不符即失败。

必须在 Bridge 正常 active 且组织轮巡启用时，通过真实 GUI launchd 检查与续期；再验证关页、Bridge 恢复、下一周期正常。记录两边提交、版本、每项前后有效期和定时任务输出。不能将本地测试、HTTP 200、Agent 退出码或一次手动操作当作该验收通过。

生产 Bridge 的升级是另一服务的部署动作，应先提供具体提交和回滚方案，遵守该设备仓库的部署授权。安装 Agent 不得就地修改生产源码、拉起第二个 Bridge 或复制 Secret。

Bridge 的测试与部署使用其自身依赖锁和生产 Python 版本，不照搬 Keeper 的 venv。远端现有 Bridge 使用 Python 3.14.5；Keeper 验收 Python 3.15.2 是另一运行主体。复测需使用隔离源码、隔离数据库与告警配置，禁止在生产树直接运行测试。
