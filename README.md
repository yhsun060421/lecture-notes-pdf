# lecture-notes-pdf

课程视频 → 复习讲义 PDF 的端到端流水线 skill。

支持三种排版，最终都输出 A4 PDF：

| 排版 | 提示词 | 产物 |
|---|---|---|
| LaTeX | `scripts/prompt_latex.txt` | `xelatex` 编译的 A4 PDF |
| 彩色 HTML | `scripts/prompt_html_color.txt` | Chromium 打印的 A4 彩色 PDF |
| 黑白 HTML | `scripts/prompt_html_bw.txt` | Chromium 打印的 A4 黑白 PDF |

**HTML 两条路线共用唯一的版式基准 `assets/reference_lecture_style.html`**：
深海军蓝封面 + 金色点缀 + 五色盒子 + 衬线正文。提交任务时它会作为「样式参考」自动随语音稿上传，
提示词第一条就是「先读它的 `<style>` 并原样复用」。成品与样板不是同一套视觉语言，一律返工。
公式全部由 **MathJax 3 渲染 TeX（CHTML 输出）**，PDF 里不允许出现任何 `\frac` / `$` 残留。

## 三条硬约束

1. **视频用 Motrix 下载**：把直链粘贴进 Motrix 新建任务，多连接能把源站速度从 0.5 MB/s 拉到 3–5 MB/s。
2. **转写用 Tabbit 打开通义听悟**：在 Tabbit 浏览器里完成上传、开始转写、取回全文。
3. **只交付一个 PDF**：HTML / LaTeX 都是中间产物，必须在沙箱里转成 PDF 再交付。

## 目录结构

```
lecture-notes-pdf/
├── SKILL.md                      # 主流程（单节课，7 个阶段）
├── README.md                     # 本文件
├── assets/
│   └── reference_lecture_style.html  # HTML 讲义的唯一版式样板（可打印，4 页）
├── references/
│   ├── html-layout.md            # 彩色 / 黑白 HTML 的 A4 打印规范（设计令牌、组件、两遍法目录）
│   ├── batch-mode.md             # 批量处理多节课的状态机与并发控制
│   ├── toolchain.md              # Windows-MCP / Tabbit CLI / 听悟 / Motrix / ffmpeg 速查
│   └── troubleshooting.md        # 按症状查的踩坑记录
└── scripts/
    ├── download_chunked.py       # 应急分块下载（Motrix 不可用且用户同意时才用）
    ├── fetch_pdf.py              # 从 Tabbit 会话取回 PDF 附件
    ├── render_html_pdf.py        # HTML -> A4 PDF（Playwright/Chromium 打印 + 自检）
    ├── check_pdf.py              # 交付前体检（空白页/LaTeX 泄漏/错字/位图/描边/灰度）
    ├── clean_transcript.py       # 语音稿清洗（繁转简 + 碎段合并 + 术语纠错）
    ├── submit_to_tabbit.py       # 三步提交 Tabbit 任务（--style 选排版，自动附带样式样板）
    ├── close_tab_uia.ps1         # UIA 关闭 Playwright 接管不了的标签
    ├── prompt_latex.txt          # LaTeX 排版提示词
    ├── prompt_html_color.txt     # 彩色 HTML 排版提示词
    ├── prompt_html_bw.txt        # 黑白 HTML 排版提示词
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
#    ffmpeg / ffprobe、Motrix、Tabbit 浏览器
```

## 快速开始（单节课）

```powershell
# 1) 取直链后，粘贴进 Motrix 下载（推荐 8 连接）
# 2) 校验并合并
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "课程合并\第8周周二.mp4"
ffmpeg -f concat -safe 0 -i filelist.txt -c copy "课程合并\第8周周二.mp4"

# 3) 抽音频 -> Tabbit 打开听悟上传/开始转写/取全文（见 SKILL.md 阶段 3）
ffmpeg -i "第8周周二.mp4" -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k "第8周周二.mp3"

# 4) 术语清洗
python -I scripts\clean_transcript.py "语音文字稿" "语音文字稿_清洗"

# 5) 提交生成（--style 三选一；html-* 会自动附带样式样板）
python -I scripts\submit_to_tabbit.py `
  --course "数据科学与工程数学基础" `
  --lesson "第8周周二" `
  --sections 2 `
  --txt "语音文字稿_清洗\第8周周二.txt" `
  --video "C:\Videos\课程合并\数据科学与工程数学基础-第8周周二.mp4" `
  --style html-color

# 6) 轮询 -> 取回 -> 质检（按排版选 --style）
python -I scripts\check_pdf.py "讲义.pdf" "体检报告.txt" --style html-color

# 7) 自建/返工 HTML 时，本地打印成 A4 PDF
python -I scripts\render_html_pdf.py "讲义.html" "讲义.pdf" --header "课程名 · 第8周周二"
```

### 版式样板自查

```powershell
# 样板本身就是可打印的，先打一份确认环境正常（4 页，深蓝封面 + 五色盒子）
python -I scripts\render_html_pdf.py assets\reference_lecture_style.html "样板.pdf"
```

## 让 skill 全局可用

在 `~/.claude/skills/` 下建一个目录联接（不需要管理员权限）：

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\lecture-notes-pdf" `
         -Target "<本仓库所在路径>\skills\lecture-notes-pdf"
```

之后在任意项目里说「把这次课做成讲义」即可触发。

## 维护

- 发现新的语音同音错字 → 补进 `scripts/clean_transcript.py` 的 `FIX`
- 平台 UI 改版 → 改对应的 `scripts/js/*.js`
- 交付标准变化 → 改对应 `scripts/prompt_*.txt` 与 `SKILL.md` 的检查表
- HTML 打印参数 / 分页 / 目录页码问题 → 先查 `references/html-layout.md`
