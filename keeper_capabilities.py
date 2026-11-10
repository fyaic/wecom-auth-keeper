"""UI label catalog for configuration/discovery; target_rows remains the explicit allowlist."""
CAPABILITY_GROUPS = {
    "messages": ["发送消息"],
    "documents": ["搜索与获取文档内容", "新建与编辑文档"],
    "disk": ["搜索与获取微盘文件内容", "上传与更新微盘文件"],
    "mail": ["搜索与获取邮件内容", "发送邮件"],
    "todos": ["新建与跟进待办"],
    "calendar": ["新建与管理日程"],
    "meetings": ["搜索与获取会议信息", "预约与更新会议"],
    "contacts": ["搜索企业成员", "获取对话用户信息"],
}
CAPABILITY_LABELS = {label for group in CAPABILITY_GROUPS.values() for label in group}
