# PDF 文档构建与归档

两份已交付 PDF、Agent ZIP 和校验清单保存在[2026-11-11 交付目录](../releases/2026-11-11/README.md)。维护这些文件时，一并提交排版脚本、可读说明和选用截图；无需把本机验收目录整个加入 Git。

## 构建

在仓库根目录执行，依赖仅用于生成文档，与自动续期运行环境分开：

```bash
python3 -m venv build/docs-venv
build/docs-venv/bin/python -m pip install -r delivery/docs/requirements.txt
build/docs-venv/bin/python delivery/docs/build_user_guide.py
build/docs-venv/bin/python delivery/docs/build_manual_guide.py
```

输出位于被 Git 忽略的 `build/handouts/`。脚本不连接企业微信、不修改授权、不复制 ZIP、不更新交付目录；禁止直接把输出指向 `delivery/releases/`。

默认使用 macOS 系统的简体黑体 TTC（子字体索引 1）；字体文件不随仓库分发。其他系统可提供具备中文字符的 TrueType 字体，例如：

```bash
python3 delivery/docs/build_manual_guide.py \
  --font-regular /path/to/Chinese-Regular.ttf \
  --font-bold /path/to/Chinese-Bold.ttf --font-index 0 \
  --output-dir build/handouts
```

使用者 PDF 从 [USER-GUIDE.txt](../USER-GUIDE.txt) 读取可复制的 Agent 指令；其他段落及版式保存在生成脚本中。手动 PDF 使用 [7 张原图](../../docs/assets/manual-renewal/README.md)，只在 PDF 中做局部显示和矢量框标注，不修改截图像素。

脚本保留这版文案日期和 ZIP 版本号。更新版本时需要同时更新文案、截图说明和新的交付目录，不自动用当前日期伪装成重新验收。

## 验证与发布

1. 脚本自检页数、可提取中文及关键步骤；使用者 PDF 还核对安装指令与文本源一致。
2. 用 Poppler 渲染，逐页检查中文、按钮、标注和分页；只检查文字提取不足以证明版式正确。
3. 核对截图中没有凭据、私聊内容或不应公开的个人资料，再归档输出。
4. 更新交付目录中的 `release.json`，执行 `delivery/verify_release.py`，提交并打新标签。

```bash
pdftoppm -scale-to 1450 -png 'build/handouts/给使用者-企业微信Bot自动续期.pdf' build/user-guide
pdftoppm -scale-to 1450 -png 'build/handouts/纯人工手动续期-企业微信Bot图文指南.pdf' build/manual-guide
```

本次归档保留最初交付的 PDF 字节。生成器使用确定性 PDF 元数据；相同内容、字体和依赖下可稳定重建，但新生成文件的元数据与原交付件可能不同，不宣称哈希相同。归档时已检查两份重建 PDF 的 7 页渲染与原件像素一致。
