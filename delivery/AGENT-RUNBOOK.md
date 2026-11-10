# 给安装 Agent 的执行清单

先读根 [AGENTS.md](../AGENTS.md) 与 [安装协议](AGENT-INSTALL.md)。本清单负责执行顺序，[首次接入](FIRST-RUN.md)负责具体页面和身份判断。人只需说明企业、Bot和业务能力；设备可查的信息由你查，不让人抄ID或Secret。沿用本次会话已有授权，常规检查和可逆修复不要反复问“是否继续”。

## 0. 固定目录、执行主体与前提

- 从解压目录工作；记录MANIFEST中的提交和外部ZIP校验值，运行`python3 delivery/verify_bundle.py`和`python3 delivery/onboard.py`。本包当前新设备入口要求企业微信5.0.13中文版；其他版本先报告适配缺口，不能改版本判断凑绿。Windows停止自动化安装。
- 包是源码安装包，依赖需联网。确认Python 3.11+，按安装协议建专用venv；记录实际解释器绝对路径。**同一Python用于系统辅助功能确认、GUI验收、正式任务。** 不复用业务Bridge的venv。
- 私有配置、状态和证据放包外；目录700、文件600。记录已有目标任务、正在操作企业微信的其他服务和当前CLI配置路径。需要共用桌面时按[协调说明](BRIDGE-COORDINATION.md)处理，不能关闭冲突检查绕过。
- 下面的`keeper_python`、`keeper_config`、`keeper_private`均由你设置为已核验的本机绝对路径；不要让业务用户填写，不要把尖括号占位符写进实际配置。例子使用新输出路径，已有记录不覆盖。

## 1. 固定用户目标，再匹配既有 CLI

1. 记录用户指定组织/Bot及所需权限；只有目标不明确时呈现查到的具体候选。主账号必须是该Bot创建者，不能用其他业务Bot替代测试对象。
2. 读取当前`WECOM_CLI_CONFIG_DIR`及已知业务启动配置中的profile路径（只取路径，不读取凭据内容）。`profiles.py`会清空继承的环境覆盖并额外检查真正default，**不会扫描整机**；对每个已知非默认目录传`--profile`。
3. 按FIRST-RUN打开指定Bot的原生详情/官方权限页，确认创建者与原生组织。查看通讯录Bot目录，不把“管理机器人”当成全部Bot。
4. 把实际观察保存为私有`target.json`，按ID匹配profile：

```json
{
  "selection_source": "user_request",
  "identity_source": "native_selected_bot_permission_page",
  "bot_chat_name": "<实际AX聊天标题>",
  "organization_selector_name": "<原生菜单准确企业名>",
  "authorization_url": "<从该Bot官方页面取得的完整原始链接>"
}
```

```bash
python3 delivery/profiles.py --cli /absolute/path/wecom-cli --profile /absolute/known/profile --output /absolute/private/profiles.json
python3 delivery/select_target.py --target /absolute/private/target.json --profiles /absolute/private/profiles.json --output /absolute/private/selection.json
```

同Bot匹配多份profile时，根据已知业务使用配置或用户明确选择，在select_target命令增加`--profile /absolute/known/profile`或`--default-profile`；只在匹配候选中选，不删除/重绑另一份配置。没有匹配不代表没Bot，按FIRST-RUN完成该目标接入准备；过期、缺历史或另一个Bot的拒绝都不是扫码理由。

## 2. 建立本机私聊和配置

- 从已核验Bot详情进入本机私聊。5.0.13可能是“去使用→通讯录资料→发消息”；资料页不算聊天。用inspect-expanded读取真实AX标题和消息视图，不能从截图猜空格。若与前一步target/selection标题不同，保留已核验Bot身份与组织，更新target并重新运行select_target，不能只改onboard输入。
- `existing_entry.py --selection ... --cli ... --node ... --output ...`从正确profile取官方原链接；健康时未返回链接可用已核验官方UI原链接，不能故意制造业务写入错误。
- 由selection和实际观察准备私有onboard输入：`bot_chat_name`、`organization_name`、`organization_selector_name`、`authorization_url`、`cli_bot_id`、`target_rows`，非默认时加`cli_config_dir`，并填绝对`wecom_cli`/`wecom_node`路径。选择记录的profile为null表示默认，onboard输入中省略该字段。
- `target_rows`只取用户需要的精确权限标签，目录可用`maintain.py --list-capabilities`查看；例子中的多项权限不是默认授权要求。

```bash
python3 delivery/onboard.py --input /absolute/private/input.json --selection /absolute/private/selection.json --output /absolute/private/config.json
python3 delivery/prepare_entry.py --config /absolute/private/config.json --message-output /absolute/private/renewal-entry.txt
```

onboard生成草稿后检查实际`venv_python`、CLI/Node及Bridge协调设置；正确设置后再验入口。入口已存在且身份匹配就复用；没有时在本次安装授权范围内运行`gui.py --action seed-current-chat`，只发一次并读回。保留草稿和未知发送日志，不通过删除日志重发。

## 3. 首次授权和冷启动入口

所有GUI动作使用同一公开启动器；每次运行及重试都换一个新evidence-dir，不复用示例中的entry-check-1：

```bash
"$keeper_python" delivery/gui.py --config "$keeper_config" --action entry-verify --evidence-dir "$keeper_private/entry-check-1"
```

执行前先关闭本轮权限页、离开目标私聊到其他会话/组织。若所需权限缺有效期，明确区分首次授权与过期；首次授予已有用户批准后，用`--action initial-grant`建立基线，随后再次离开会话、entry-verify。回执必须由脚本成功产生，不能复制旧回执或删配置中的entry_receipt。

通过标准：目标CLI/组织/聊天/链接与官方页面身份一致、全部配置权限可读、关页成功。私聊类型由你从已核验Bot详情的进入路径确认。首次授权与入口成功均不能写成续期成功。

## 4. 真实续期，再验自然定时

- 使用同一私有配置，备份maintenance策略；停止该目标旧任务并确认没有活跃周期后再试验，避免同Bot两套任务。其他Bot与服务保留。
- 已获准提前取消/重授时，临时策略为`within_hours=168, interval_seconds=60, min_renew_interval_seconds=60, retry_seconds=60, close_window=true`。
- 先`gui.py --action maintain`，保存每项`expiry_before/expiry`，必须严格延长、pending=false、cleanup.closed=true。若刚授予，等跨过页面的分钟精度再做实际预续期；not_due/cooldown不算。
- 用`maintain.py --write-launchagent`在新私有证据目录生成临时plist，保留原件，将执行副本**仅RunAtLoad改false**，bootstrap并记录加载时间；不得kickstart。
- 等自然输出，只有整体`ok=true`、全部`target_rows`在该次逐项实际`pre_renewed`且期限增加、无pending、关页成功才通过。把原始日志结果逐字存成独立证据，不能拿上次state当本次成功。设有界观察时间并在finally卸载临时任务，失败也卸载；不能留下60秒任务继续反复撤销。
- 复核同Bot必要的只读业务调用和共用服务恢复。禁止为测试发送业务消息或写业务表。

## 5. 正式持久任务与结果卡

恢复`within_hours=24, interval_seconds=3600, min_renew_interval_seconds=3600, retry_seconds=300, close_window=true`。retry_seconds是失败后的最短退避门槛，实际重试仍由下一次调度触发，不承诺每5分钟执行。

按[安装协议第5节](AGENT-INSTALL.md#5-安装升级和卸载)将正式plist放入**本用户`~/Library/LaunchAgents/<实际Label>.plist`**。任意私有目录里的plist被bootstrap只是当前登录会话加载，不算持久安装。生成工具不安装、不去重；你必须检查同目标已有job并保持唯一。

bootstrap后读取真实输出、exit code、权限与关页结果，记录首跑是not_due还是实际续期。无需为了验登录加载而擅自重启/退出业务设备；如未实测重登，应准确写“已安装登录加载文件，未重启设备验证”。

在私有目录填[验收记录](acceptance.example.json)，并给人一张简短结果卡：

```text
状态：安装完成 / 尚未完成（具体阶段与错误）
维护对象：组织、Bot、所需权限（可读名称）
实测：真实续期前后期限；自然定时完成时间；自动关页结果
运行：每小时检查／到期前24小时；正式首跑结果与时间
位置：固定项目目录、私有配置、最近结果和日志、正式plist
停用／恢复：本机实际命令或可直接交给Agent的指令
限制：本机系统与客户端版本、是否重登验证、仍未验场景
```

## 6. 后续排障、持久停用、升级

- 状态查看先读最近定时日志、`state_file`及其`checked_at`、`maintain.py --status`和launchctl状态；历史healthy不代表新周期通过，`--status`的ok只表示读记录成功。锁冲突可能仅写日志，不覆盖另一个周期的状态。
- 持久停用：先确认本目标没有活跃周期，bootout该Label，再把**该目标唯一plist**移出`~/Library/LaunchAgents`到私有备份目录。只bootout会在下次登录重新加载。不删配置/pending，不退出企业微信、不停其他服务。
- 恢复：确认配置、代码路径、执行Python和入口仍有效、无重复job，再把该plist放回并bootstrap。RunAtLoad会立即检查；读取真实结果。
- 升级：新固定版本目录、保留私有状态与回滚；先停旧目标任务再验新版本，不能同时运行两个版本。恢复旧代码前也停止新任务，不能删除未决记录来消除错误。
- 本地不可修复的身份/系统授权/客户端适配问题，给出具体证据和最少必要操作；不扩大授权、不重新建Bot掩盖问题，不把失败安装写成完成。
