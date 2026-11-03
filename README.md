# lecture-notes-pdf

课程视频 → 复习讲义 PDF 的端到端流水线 skill。

## 目录结构

```
lecture-notes-pdf/
├── SKILL.md                      # 主流程（单节课，7 个阶段）
├── README.md                     # 本文件
├── references/
│   ├── batch-mode.md             # 批量处理多节课的状态机与并发控制
│   ├── toolchain.md              # Windows-MCP / Tabbit CLI / 听悟 / Motrix / ffmpeg 速查
│   └── troubleshooting.md        # 按症状查的踩坑记录
└── scripts/
    ├── download_chunked.py       # 8MB 分块并发下载 + 断点续传
    ├── fetch_pdf.py              # 从 Tabbit 会话取回 PDF 附件
    ├── check_pdf.py              # 交付前体检（空白页/LaTeX 泄漏/错字/引号）
    ├── clean_transcript.py       # 语音稿清洗（繁转简 + 碎段合并 + 术语纠错）
    ├── submit_to_tabbit.py       # 三步提交 Tabbit 任务
    ├── close_tab_uia.ps1         # UIA 关闭 Playwright 接管不了的标签
    ├── prompt_template.txt       # 提交给 Tabbit 的提示词（含全部硬性交付要求）
    └── js/
        ├── tingwu_upload.js          # 听悟：三层点击上传
        ├── tingwu_start.js           # 听悟：点「开始转写」
        ├── tingwu_fetch_transcript.js# 听悟：走接口取带时间戳全文
        ├── dl_session_pdf.js         # Tabbit：抓 PDF 预签名 URL
        └── poll_files.js             # Tabbit：轮询文件库新产物
```

## 环境准备

```powershell
# 1. Windows-MCP（全局）
uv tool install windows-mcp
claude mcp add --scope user windows-mcp -- "C:\Users\<你>\.local\bin\windows-mcp.exe" serve

# 2. Python 依赖
D:\Anaconda\python.exe -m pip install pymupdf opencc-python-reimplemented

# 3. 外部工具
#    ffmpeg / ffprobe、Motrix（aria2 RPC 16800）、Tabbit 浏览器
```

## 快速开始（单节课）

```powershell
python -I scripts\download_chunked.py "<视频直链>" "C:\Videos\第8周周二.mp4" 8
ffmpeg -i "C:\Videos\第8周周二.mp4" -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k "第8周周二.mp3"
# —— 听悟上传 + 开始转写 + 取全文（见 SKILL.md 阶段 3）
python -I scripts\clean_transcript.py "语音文字稿" "语音文字稿_清洗"
python -I scripts\submit_to_tabbit.py --lesson "第8周周二" --txt "语音文字稿_清洗\第8周周二.txt" --video "C:\Videos\第8周周二.mp4"
# —— 等待生成，用 poll_files.js 轮询，再 fetch_pdf.py 取回
python -I scripts\check_pdf.py "讲义.pdf" "体检报告.txt"
```

## 让 skill 全局可用

在 `~/.claude/skills/` 下建一个目录联接（不需要管理员权限）：

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\lecture-notes-pdf" `
         -Target "<本仓库所在路径>\skills\lecture-notes-pdf"
```

之后在任意项目里说"把这次课做成讲义"即可触发。

## 维护

- 发现新的语音同音错字 → 补进 `scripts/clean_transcript.py` 的 `FIX`
- 平台 UI 改版 → 改对应的 `scripts/js/*.js`
- 交付标准变化 → 改 `scripts/prompt_template.txt` 与 `SKILL.md` 的检查表
