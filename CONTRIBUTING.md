# Contributing / 参与贡献

中文和英文 Issue / PR 均欢迎。先阅读 [README](README.md)、[已知限制](docs/known-limitations.md)和[路线图](docs/roadmap.md)。

## 开始

1. 搜索已有 Issue，选择一个可独立验证的问题；较大架构改动先讨论。
2. Fork 仓库并建立工作分支。文档和结构检查不需要企业微信账号。
3. 运行 `python3 scripts/check_repository.py` 和 `git diff --check`。
4. 使用 PR 模板说明问题、变更和验证范围。修复行为时补充能覆盖真实失败的回归测试。

## 桌面与真实账号验证

使用自己有权操作的 bot 和专用测试表。记录系统/客户端/CLI/bridge 版本、前后有效期、是否重开页面复核、是否运行实际 API 探针。没有真实验证时直接写“未验证”。

不要提交 Bot Secret、token、credentials.enc、真实授权 URL、企业聊天/文档内容、config.json、原始 state 或日志。截图应移除账号和企业信息。

## 有帮助的贡献

- 复现并修复状态误判、错误退出码或超时。
- 不依赖固定屏幕坐标的导航与严格身份验证。
- 干净环境安装说明、客户端兼容性记录和英文文档。
- 失败后能够恢复原权限的预续期状态机。

行为规范见 [Code of Conduct](CODE_OF_CONDUCT.md)，漏洞报告见 [Security](SECURITY.md)。提交贡献即同意按仓库的 [MIT License](LICENSE) 提供该贡献。
