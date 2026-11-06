---
name: lecture-notes-pdf
description: 把课程平台（ECNU 资源管理网页、网课站点等）上的课程视频，经「Windows-MCP 操作浏览器取直链 → 直链粘贴进 Motrix 下载 → 本地抽音频 → Tabbit 打开通义听悟转写 → 术语清洗 → Tabbit 任务模式双线分析 → 按 LaTeX / 彩色 HTML / 黑白 HTML 三种排版之一输出 A4 PDF → 质检交付」端到端变成一份复习讲义 PDF。当用户要求把某次课或一批课整理成讲义/复习资料 PDF 时使用。
---

# 课程讲义 PDF 生成流水线

把一节（或一批）课程视频，变成一份**可直接阅读、公式完整、带课堂例题与考点标注的 A4 讲义 PDF**。

核心思路：**画面与语音双线还原**。语音稿负责「老师说了什么」，视频关键帧负责「黑板上写了什么」，PPT 负责「课件呈现了什么」，三者交叉校验；语音稿里的同音错字一律以板书为准。

## 三条硬约束（不满足就是做错了）

1. **视频必须用 Motrix 下载**：拿到直链后，把链接**粘贴进 Motrix 软件**新建任务下载。Motrix 多连接能把源站速度从 0.5 MB/s 拉到 3–5 MB/s；不要用单线程或自写下载器当主路径。
2. **转写必须用 Tabbit 打开通义听悟**：在 Tabbit 浏览器里打开 `https://tingwu.aliyun.com`，用 Tabbit CLI 驱动上传、开始转写、取回全文；不要用 Windows-MCP 的手动点击路径，也不要用本地 whisper。
3. **最终只交付一个 PDF**：HTML / LaTeX 都是中间产物，必须在沙箱里编译或打印成 PDF，只把 PDF 作为「生成的文件」附件交出来。

## 流水线总览

```
[0] 盘点素材
      ↓
[1] 资源发现（Windows-MCP 操作浏览器）→ 拿到视频直链
      ↓
[2] 下载 + 合并（直链粘贴进 Motrix；多段用 ffmpeg -c copy 合并）
      ↓
[3] 抽音频 → Tabbit 打开通义听悟 → 上传 / 开始转写 / 取回全文
      ↓
[4] 术语清洗（同音错字修正表）
      ↓
[5] 选排版 → Tabbit 任务模式三步提交
      ├─ LaTeX          scripts/prompt_latex.txt
      ├─ 彩色 HTML      scripts/prompt_html_color.txt  → A4 彩色 PDF
      └─ 黑白 HTML      scripts/prompt_html_bw.txt     → A4 黑白 PDF
      ↓
[6] 取回 PDF + 按排版分别质检
      ↓
[7] 归档、更新交付说明、清理中间文件与进程
```

单节课走完约 1.5–3 小时（视频时长 + 转写排队 + 生成），大部分是等待时间。批量处理见 [references/batch-mode.md](references/batch-mode.md)。

---

## 阶段 0：盘点素材（5 分钟）

| 素材 | 检查方式 | 缺失怎么办 |
|---|---|---|
| 课程视频 | 本地文件？平台直链？ | 走阶段 1 从资源管理网页取 |
| 语音稿 | 平台自带字幕？已转写？ | 平台有字幕直接下载；没有走阶段 3 |
| 课程名/课次命名 | 如「第8周周二」 | 与学生确认或按平台课表命名 |
| 已有讲义 | 看交付目录是否已有同课前版本 | 有则增量补，不重复生成 |
| 目标排版 | LaTeX / 彩色 HTML / 黑白 HTML | 用户没说就默认 LaTeX；要打印优先黑白 |

**命名约定（贯穿全程）**：

- 课次标识：`第8周周二`（周次 + 星期），全流程唯一
- 交付文件名：`数据科学与工程数学基础-第十一次课.pdf`（中文序数）
- 中间文件：`数据科学与工程数学基础-第8周周二.mp4`、`语音文字稿/第8周周二.txt`

课次标识 ↔ 中文序数的映射记在状态文件里，批量时尤其重要：

```json
{"第1周周四": "第一次课", "第1周周日": "第二次课", "第2周周四": "第三次课"}
```

---

## 阶段 1：资源发现（用 Windows-MCP 操作浏览器）

**这一阶段必须用 Windows-MCP，不要用无头脚本猜接口**。课程平台的播放地址通常带签名 `auth_key`、有效期短，且依赖登录态；用浏览器 UI 走一遍最稳。

### 1.1 打开并定位课程

```
App            → 启动/切换浏览器（Chrome / Edge / Tabbit）
Snapshot       → 看页面结构，拿到元素 id
Click          → 点「资源管理」/「课程列表」/「播放」
WaitFor        → 等播放页加载（元素出现或标题变化）
```

要点：

- 先 `Snapshot` 再 `Click`，不要凭截图坐标盲点；页面滚动后坐标会变
- 列表页元素多时用 `Snapshot` 的文本检索定位，或 `Screenshot` 看视觉布局
- 播放页打开后，视频一般在 `<video>` 标签或播放器 iframe 里
- **播放页常有两个 `<video>`**：第一个是主视频（有声音），第二个是备用流（`muted: true`、往往只有底噪）。取直链前先在页面里确认 `muted` 与 `duration`，别下错流

### 1.2 取视频直链

推荐顺序（命中即止）：

1. **F12 网络面板人工看**：点播放 → 筛选 `media` / `mp4` → 复制请求 URL
2. **Windows-MCP 的 `PowerShell` 工具配合**：取浏览器调试端口，读网络日志
3. **页面内监听**（有 Tabbit/Playwright 时）：`performance.getEntriesByType("resource")` 过滤 `.mp4`

直链长这样：

```
https://dudaomedia.ecnu.edu.cn:40443/vod2/....mp4?auth_key=1759...-0-0-....
```

**关键校验**：拿到 URL 后立刻发一个 Range 请求确认支持断点续传：

```powershell
curl.exe -sI -H "Range: bytes=0-1" "<URL>"
# 期望看到 206 Partial Content 和 Content-Range: bytes 0-1/<总大小>
```

同时记下总大小，下载完成后逐字节比对。

### 1.3 记录到状态文件

```json
{
  "lesson": "第8周周二",
  "course": "数据科学与工程数学基础",
  "style": "latex",
  "video_url": "https://...mp4?auth_key=...",
  "video_size": 885483291,
  "auth_expire": "2026-11-04T10:00:00"
}
```

签名有效期通常几小时到一天，**当天拿到当天就下**。

---

## 阶段 2：下载与合并（Motrix 强制）

### 2.1 主路径：把直链粘贴进 Motrix

用户机器上装有 Motrix（aria2 内核，多连接下载）。标准动作：

1. 复制阶段 1 拿到的直链；
2. 打开 Motrix（任务栏 / 开始菜单）；
3. 点工具栏「+」或按 `Ctrl+N` 打开「新建任务」；
4. 把链接**粘贴**到地址栏（Motrix 会自动识别剪贴板，通常弹出「检测到剪切板中的链接」提示，直接点「确定」）；
5. 在「保存到」里选课程视频目录（如 `C:\Users\<你>\Videos\课程合并`）；
6. 文件名按命名约定改成 `<课程名>-<课次>.mp4`；
7. 点「提交」，在「正在下载」里确认连接数为 8、速度正常爬升。

> 实测：同一门课，浏览器单线程约 0.5 MB/s，Motrix 8 连接可到 3–5 MB/s。**不要为了「自动化」绕开 Motrix 去写下载器**，慢一个数量级。

### 2.2 自动化：Motrix 的 aria2 JSON-RPC

需要脚本化时，走 Motrix 暴露的 RPC（默认 `127.0.0.1:16800`），不要另起下载器：

```powershell
$body = @{
  jsonrpc = "2.0"; id = "1"; method = "aria2.addUri"
  params  = @(
    @("$URL"),
    @{ dir = "C:\Users\<你>\Videos\课程合并"; out = "数据科学与工程数学基础-第8周周二.mp4";
       split = "8"; "max-connection-per-server" = "8"; "min-split-size" = "8M" }
  )
} | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "http://127.0.0.1:16800/jsonrpc" -Method Post -Body $body -ContentType "application/json"

# 查进度
Invoke-RestMethod -Uri "http://127.0.0.1:16800/jsonrpc" -Method Post -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","id":"2","method":"aria2.tellStatus","params":["<gid>"]}'
```

有 secret 时在 `params` 数组第一个位置加 `"token:<secret>"`。

### 2.3 完整性校验（必做）

```powershell
ffprobe -v error -show_entries format=duration,size,bit_rate -of default=nw=1 "<输出.mp4>"
```

期望：`duration` 与课程时长吻合（如 `3300.042`），无 `moov atom not found`；`size` 与阶段 1 记下的 `video_size` 一致。

再抽样验证不是全零：

```powershell
python -c "f=open(r'<输出.mp4>','rb');f.seek(<size>//2);d=f.read(1048576);print('非零字节占比', round(sum(b!=0 for b in d)/len(d),3))"
```

占比应 > 0.9。若大小对但内容空洞，删掉用 Motrix 重下，不要试图修补。

### 2.4 合并（多节视频合成一节）

平台常把一节课拆成 2–3 段。用 ffmpeg 无损拼接：

```powershell
# filelist.txt 每行 file '片段路径'
ffmpeg -f concat -safe 0 -i filelist.txt -c copy "<合并后.mp4>"
```

必须 `-c copy`，不要重编码（省时且无损）。合并后再跑一次 2.3 的 ffprobe，确认总时长等于各段之和。

> **应急**：只有 Motrix 确实不可用、且用户明确同意时，才退回 `scripts/download_chunked.py`（8 MB 分块并发）。不要默认走它。

---

## 阶段 3：语音转写（Tabbit + 通义听悟，强制）

平台没有现成字幕时走这条路。**必须在 Tabbit 浏览器里打开通义听悟网站来操作**，不要用 Windows-MCP 手动点击，也不要用本地 whisper。

### 3.1 抽音频

```powershell
ffmpeg -i "<视频.mp4>" -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k "<课次>.mp3"
```

16 kHz 单声道 64 kbps 对语音识别足够，文件小、上传快。视频超过 100 分钟时按 50–60 分钟切段，分别转写后按时间偏移合并，避免单次转写排队过久或失败。

### 3.2 在 Tabbit 里打开听悟并上传

```powershell
# 1) 建任务并打开听悟
tabbit-cli create --task "听悟"
tabbit-cli nodejs --task "听悟" --request-id "tw-open-<时间>" --timeout-ms 60000 < scripts\js\tingwu_upload.js
```

`tingwu_upload.js` 做三件事（听悟的 UI 有三层，直接点最外层不会触发文件选择器）：

```
1. 点「上传音视频」            → 弹出面板
2. 点「上传本地音视频文件」     → 切到拖拽面板
3. 点「点击 / 拖拽」           → 才真正触发 <input type=file>
   然后 setFiles(音频路径)
```

上传成功后文件进入待转写列表，**还要再点「开始转写」**，否则一直排队：

```powershell
tabbit-cli nodejs --task "听悟" --request-id "tw-start-<时间>" --timeout-ms 60000 < scripts\js\tingwu_start.js
```

页面会显示「转写中，预计剩余 19:11」。转写完成后记录 URL 里的 `transId`（`/doc/transcripts/<transId>`）。

### 3.3 取回全文（关键技巧）

听悟的转写页是**虚拟列表**，`document.body.innerText` 只能拿到几千字，导出按钮也常点不出菜单。在 Tabbit 里直接调它的接口：

```js
POST /api/trans/getTransResult?c=web
Content-Type: application/json
Body: {"transId": "<转写记录ID>"}
```

- 用 `GET` → 405
- 传 `{"transIds":[...]}` → `TRS.InvalidTrans`
- 必须传单个 `transId`

返回的 `data.result` 是一个**字符串**，要再 `JSON.parse` 一次：

```
{ "pg": [ { "sc": [ { "bt": 起始毫秒, "et": 结束毫秒, "tc": "文本" } ] } ] }
```

`bt` → `mm:ss` 就是每句的时间戳。`data.wordCount` 给字数，`data.duration` 给音频秒数。

脚本：`scripts/js/tingwu_fetch_transcript.js`，用法见 [references/toolchain.md](references/toolchain.md#通义听悟)。

### 3.4 结果过大时

全文可能 6 万字、60 KB，Tabbit CLI 会转成 `resourceId`。必须分片读：

```powershell
tabbit-cli resource --task "听悟" --resource "<resourceId>" --offset 0 --max-bytes 20000
# 按返回的 nextOffset 继续，直到 eof=true
# offsetUnit=4 表示 UTF-16 code units，不是字节，不能用字符长度推算
```

把各片 `data` 字段拼起来再 `json.loads`。

### 3.5 落盘格式

```
[00:00] 好，我们开始上课。然后下一节课主要讲的是这个 LU 分解。
[00:12] 每一种分解，其实学习的时候本身要注意的几个事情……
```

存成 `语音文字稿/<课次>.txt`，UTF-8。

---

## 阶段 4：术语清洗（必做）

听悟的稿子句子完整，但数学术语错字密集。直接喂给模型会得到满篇「举证矩阵」。

```powershell
python -I scripts\clean_transcript.py "<语音文字稿目录>" "<输出目录>"
```

脚本内置术语表（`举证→矩阵`、`转制→转置`、`内机→内积`、`对焦化→对角化`、`现金代数→线性代数`……），并做三件事：

1. 繁转简（OpenCC `t2s`）
2. 碎段合并（间隔 ≤6 秒且合起来 ≤110 字）
3. 同音错字替换

输出 `语音文字稿_清洗/<课次>.txt`，**提交给 Tabbit 的是这一份**。

> 术语表是本项目的核心资产。每发现一个新错字就补进去，见 `scripts/clean_transcript.py` 顶部的 `FIX`。清洗后仍可疑的地方由模型在生成时按板书校正，但不要指望它兜底。

---

## 阶段 5：提交 Tabbit 生成讲义

### 5.1 选排版

| 排版 | 提示词 | 产物 | 技术路线 |
|---|---|---|---|
| LaTeX | `scripts/prompt_latex.txt` | A4 PDF | `xelatex` + `ctex` + `tcolorbox` + `TikZ` |
| 彩色 HTML | `scripts/prompt_html_color.txt` | A4 彩色 PDF | HTML+CSS + MathJax3 CHTML + Chromium `page.pdf` |
| 黑白 HTML | `scripts/prompt_html_bw.txt` | A4 黑白 PDF | 同上，全灰度 + 符号标签 |

**HTML 两条路线必须带样式样板**：`assets/reference_lecture_style.html` 是唯一的版式基准
（深海军蓝封面 + 金色点缀 + 五色盒子 + 衬线正文）。提交时它会作为「样式参考」随语音稿一起上传，
提示词第一条就要求模型先读它的 `<style>` 并原样复用；不传样板、或成品与样板不是同一套视觉语言，一律返工。

完整技术规范（设计令牌、组件清单、A4 参数、页眉页脚、目录两遍法、打印质检、黑白映射）见
[references/html-layout.md](references/html-layout.md)。

### 5.2 为什么要分三步

单次程序有 **180 秒硬超时**。上传 txt、引用视频、输入长 prompt 三件事加起来会超；分开后每步都在时限内。

```powershell
python -I scripts\submit_to_tabbit.py `
  --course "数据科学与工程数学基础" `
  --lesson "第8周周二" `
  --sections 2 `
  --txt "语音文字稿_清洗\第8周周二.txt" `
  --video "C:\Users\<你>\Videos\课程合并\数据科学与工程数学基础-第8周周二.mp4" `
  --style html-color `
  --task "课程讲义"
```

`--style` 三选一：`latex`（默认）/ `html-color` / `html-bw`；也可用 `--prompt` 指定自定义提示词。

`html-color` / `html-bw` **强制自带样式样板**：脚本会在 step 1 把 `assets/reference_lecture_style.html`
与语音稿放进同一次 filechooser 上传，并逐张卡片核对文件名是否出现在 composer 里，缺哪张补传哪张。
需要额外参考文件（往年讲义、教材扫描等）时用 `--ref <路径>` 追加，可重复。

内部流程：

| 步骤 | 动作 | 关键点 |
|---|---|---|
| 1 | 新开 `web.tabbit.com/newtab` → 选「任务」模式 → 添加引用 → 上传 txt + 参考文件 | 先关引导弹窗；模式菜单点「任务」，备选文案「生成文件、操作网页和长程任务。」；上传后核对文件名 |
| 2 | 新开视频的 `file://` 页 → 回到 composer 输入 `@` + 视频关键词 → 点候选 | 必须先在 `[role=textbox]` 里打 `@`，再输关键词；候选里点 `.mp4` |
| 3 | 用 `execCommand("insertText")` 灌入 prompt → 点 `Run` | 长文本不能用 `fill`，会被截断或触发校验 |

### 5.3 提示词里的硬性约束（改课时只换占位符，不改这些）

三条路线共用：

- **TXT 必须全量读取，不得遗漏**
- 标注课堂例题（写「课堂讲授」+ 时间戳）与考点/可能考的暗示
- 语音稿术语必须规范化，不得原样抄错字
- 精度：每块板书标 `[画面 mm:ss]`，每段引用标 `[录音 mm:ss]`，全篇录音引用 ≥15 处
- 推导完整，不换页、不留白
- 交付：只要一个编译好的 PDF，作为「生成的文件」附件给出

LaTeX 路线追加：

- 公式全部 `\displaystyle`
- 内容用盒子（tcolorbox）封装
- 多次编译保证目录、页码正确
- PDF 里不得出现 `#` 开头的 LaTeX 乱码

HTML 路线追加：

- 纯 HTML+CSS，**严禁** `xelatex` / `pdflatex` / `lualatex` / `tectonic` / `xdvipdfmx`
- 公式用 MathJax 3 **CHTML**，禁止 `tex-svg.js`
- 插图全部内联 SVG，禁止位图
- 打印前等 `MathJax.startup.promise`
- 目录页码用两遍法
- 黑白版不得出现任何彩色，四类标签用 ●▲■◆ 区分

### 5.4 提示词占位符

三份提示词都用同一套占位符，`submit_to_tabbit.py` 会自动替换：

| 占位符 | 来源 | 示例 |
|---|---|---|
| `{{课程名}}` | `--course` | 复变函数与积分变换 |
| `{{讲次}}` | `--lesson` | 第8次课 |
| `{{节数}}` | `--sections` | 2 |
| `{{视频文件}}` | `--video` 的文件名 | 复分析8.mp4 |
| `{{输出文件名}}` | `--out-name`，默认 `<课程名>_<讲次>.pdf` | 复分析_第8次课.pdf |
| `{{语音稿}}` | `--txt` 的文件名 | 复分析8.txt |

手工提交时也要先把这些占位符替换掉，再灌进 Tabbit。

### 5.5 并发上限

**同时最多 3 个生成任务**。更多会互相拖慢，且容易触发平台限流或任务相互干扰。

### 5.6 等待与轮询

任务跑起来后，用文件库接口轮询产物，不要盯着页面：

```js
GET /api/v0/tabbit-space/files?type=all&limit=36
// item: { id, filename, content_type, source.chat_session_id, created_at }
```

判据：`filename` 命中课次关键字 **且** 以 `.pdf` 结尾 **且** `created_at` 晚于提交时间。

轮询间隔 3–4 分钟，单节课通常 20–50 分钟生成完。

---

## 阶段 6：取回 PDF 与质检

### 6.1 取回

会话页里 PDF 是附件卡片，卡片上有「下载」按钮。点击后浏览器会向 COS 发预签名请求，CDP 监听 `Network.requestWillBeSent` 抓 `myqcloud.com` 的 URL：

```powershell
python -I scripts\fetch_pdf.py <sessionId> "<匹配关键词>" "<输出.pdf>"
```

> 直接拿文件库的 `file_id` 调 `/api/v0/cos/presigned-download-url` 会返回 `file.notFound`。必须从会话页走。

### 6.2 质检（不过不许交付）

```powershell
python -I scripts\check_pdf.py "<pdf>" "<报告.txt>" --style latex|html-color|html-bw
```

共用判据：

| 项 | 合格标准 |
|---|---|
| 页数 / 字数 | 有值，字数与课长匹配（一般 2 万–5 万） |
| 空白页 | `blank=[]` |
| 目录 | `toc=True` |
| 例题 / 考点 | `example=True`、`exam=True` |
| 语音错字 | 命中的必须**全部**落在勘误对照表页内 |
| LaTeX 泄漏 | `hash_line=0`、`displaystyle=0`、`begin_cmd=0`、`frac=0`、`dollar=0` |
| 引号配对 | `“` 与 `”` 数量接近（跨页引用允许少量差值） |

HTML 路线追加：

| 项 | 合格标准 |
|---|---|
| 位图 | `images=0`（插图必须全部是内联 SVG） |
| 文字描边 | `text_strokes=0` |
| 越界 | `text_outside_page=0` |
| 黑白纯度（`html-bw`） | `color_pages=[]`、`color_ratio_max≈0` |

再手工抽查：

- `pdffonts` 确认中文字体与公式字体全部内嵌、无 Type3；
- 抽 3 页以 400 dpi 渲染，公式是干净实心笔画；
- 目录前 5 条与页脚页码一致。

错字命中要人工回看上下文——在附录「转写原样 → 应为」对照表里属正常，出现在正文就返工重生成。

### 6.3 重生成

不合格时不要手工改 PDF。回到 Tabbit，新开一个 request，把失败点写进 prompt 追加段（例如「上一版第 25 页出现 `\frac` 残留，请检查所有公式环境」），重新生成。

---

## 阶段 7：归档与清理

```
交付目录/
├── <课程名>_<讲次>.pdf
└── 交付说明.md          ← 明细表：文件 / 对应课堂 / 排版 / 页数 / 字数 / 状态
```

更新交付说明时：加一行明细、更新总数、记录本课特殊说明（旧版缺陷、转写工具变更等）。

清理（用户通常明确要求「全部做完清理中间文件」）：

1. 关闭 Tabbit 相关标签页 / `tabbit-cli finish --task "<任务名>"`；需要连标签一起关时用 `--discard`（会关掉收购来的用户标签，先确认）
2. Motrix 里确认没有进行中的任务（`aria2.tellActive` 为空）再退出
3. 停掉后台轮询脚本
4. 删除中间文件：分段视频、抽出的音频、`*_清洗` 临时稿、HTML/tex/py/日志、旧版静音视频
5. 确认没有残留的 python / ffmpeg 进程

> 关浏览器进程会丢掉用户其他标签，**先问一句**；用户说「直接关」再关。

---

## 交付前的最后一道检查

```
[ ] PDF 在交付目录，文件名符合「<课程名>_第X次课.pdf」
[ ] 无压缩包、无 tex/html/中间图片一起交付
[ ] check_pdf.py 对应 --style 全绿
[ ] HTML 版 images=0、text_strokes=0；黑白版 color_pages=[]
[ ] 目录页码与页脚一致
[ ] 交付说明.md 已更新
[ ] 中间文件与临时进程已清理
```

---

## 相关文档

- [HTML 排版规范（彩色 / 黑白）](references/html-layout.md)
- [批量处理多节课](references/batch-mode.md)
- [工具与 API 速查](references/toolchain.md)
- [故障排查](references/troubleshooting.md)
