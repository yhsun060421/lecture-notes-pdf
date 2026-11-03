---
name: lecture-notes-pdf
description: 把课程平台（ECNU 资源管理网页、网课站点等）上的课程视频，经「Windows-MCP 操作浏览器取直链 → Motrix/分块下载 → 通义听悟转写 → 术语清洗 → Tabbit 任务模式双线分析 → PDF 质检交付」端到端变成一份 LaTeX 排版的复习讲义 PDF。当用户要求把某次课或一批课整理成讲义/复习资料 PDF 时使用。
---

# 课程讲义 PDF 生成流水线

把一节（或一批）课程视频，变成一份**可直接阅读、公式完整、带课堂例题与考点标注的 LaTeX-PDF 复习讲义**。

核心思路：**画面与语音双线还原**。语音稿负责"老师说了什么"，视频关键帧负责"黑板上写了什么"，两者交叉校验后写成讲义；语音稿里的同音错字一律以板书为准。

## 什么时候用

- "把第 X 次课整理成复习讲义 / 复习资料 PDF"
- "这批课程视频都做成讲义"
- 已经有一份课程视频（本地或直链）和一份语音转写稿，需要合成排版精美的 PDF

## 流水线总览

```
[0] 盘点素材
      ↓
[1] 资源发现（Windows-MCP 操作浏览器）→ 拿到视频直链
      ↓
[2] 下载 + 合并（Motrix/aria2 或分块下载器）
      ↓
[3] 抽音频 → 通义听悟转写 → 取回带时间戳全文
      ↓
[4] 术语清洗（同音错字修正表）
      ↓
[5] 提交 Tabbit 任务模式（分三步，避免超时）
      ↓
[6] 取回 PDF + 自动质检
      ↓
[7] 归档、更新交付说明、清理进程与标签页
```

单节课走完约 1.5–3 小时（视频时长 + 转写排队 + 生成），其中大部分是等待时间。批量处理见 [references/batch-mode.md](references/batch-mode.md)。

---

## 阶段 0：盘点素材（5 分钟）

先搞清楚手上有什么，缺什么：

| 素材 | 检查方式 | 缺失怎么办 |
|---|---|---|
| 课程视频 | 本地文件？平台直链？ | 走阶段 1 从资源管理网页取 |
| 语音稿 | 平台自带字幕？已转写？ | 平台有字幕直接下载；没有走阶段 2–3 |
| 课程名/课次命名 | 如"第8周周二" | 与学生确认或按平台课表命名 |
| 已有讲义 | 看交付目录是否已有同课前版本 | 有则增量补，不重复生成 |

**命名约定（重要，贯穿全程）**：

- 课次标识：`第8周周二`（周次 + 星期），全流程唯一
- 交付文件名：`数据科学与工程数学基础-第十一次课.pdf`（中文序数）
- 中间文件：`数据科学与工程数学基础-第8周周二.mp4`、`语音文字稿/第8周周二.txt`

课次标识 ↔ 中文序数的映射要记在状态文件里，批量时尤其重要：

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
Click          → 点"资源管理"/"课程列表"/"播放"
WaitFor        → 等播放页加载（元素出现或标题变化）
```

要点：
- 先 `Snapshot` 再 `Click`，不要凭截图坐标盲点；页面滚动后坐标会变
- 列表页元素多时用 `Snapshot` 的文本检索定位，或 `Screenshot` 看视觉布局
- 播放页打开后，视频一般在 `<video>` 标签或播放器 iframe 里

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

不支持 Range（返回 200 且无 Content-Range）就只能单线程下，见 [references/troubleshooting.md](references/troubleshooting.md#不支持-range)。

### 1.3 记录到状态文件

```json
{
  "lesson": "第8周周二",
  "video_url": "https://...mp4?auth_key=...",
  "video_size": 885483291,
  "auth_expire": "2026-11-04T10:00:00"
}
```

签名有效期通常几小时到一天，**当天拿到当天就下**。

---

## 阶段 2：下载与合并

### 2.1 首选：Motrix（aria2 JSON-RPC）

用户在任务栏开着 Motrix 时，直接走它的 RPC，8 连接能跑到源站上限（实测 0.56 MB/s → 4 MB/s）。

```powershell
# 无 secret 时直接调；有 secret 则加 "token:<secret>"
$body = @{
  jsonrpc = "2.0"; id = "1"; method = "aria2.addUri"
  params  = @(
    @("$URL"),
    @{ dir = "C:\Users\<你>\Videos\课程"; out = "数据科学与工程数学基础-第8周周二.mp4";
       split = "8"; "max-connection-per-server" = "8"; "min-split-size" = "8M" }
  )
} | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "http://127.0.0.1:16800/jsonrpc" -Method Post -Body $body -ContentType "application/json"

# 查进度
Invoke-RestMethod -Uri "http://127.0.0.1:16800/jsonrpc" -Method Post -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","id":"2","method":"aria2.tellStatus","params":["<gid>"]}'
```

### 2.2 备选：分块并发下载器

没有 Motrix 或 RPC 不通时用 `scripts/download_chunked.py`：

```powershell
python -I scripts\download_chunked.py "<URL>" "<输出.mp4>" 8
# 输出 ALL_OK 才算成功
```

它把文件切成 8 MB 块，每块独立 Range 请求，状态写 `<输出>.state`，中断可续传。

> **绝对不要用 `truncate` 预分配后单线程写**。那是"文件大小看着对、内容大片为 0"的根源，ffprobe 会报 `moov atom not found`。完整踩坑见 [references/troubleshooting.md](references/troubleshooting.md#视频文件大小正确但内容空洞)。

### 2.3 完整性校验（必做）

```powershell
ffprobe -v error -show_entries format=duration,size,bit_rate -of default=nw=1 "<输出.mp4>"
```

期望：`duration` 与课程时长吻合（如 `3300.042`），无 `moov atom not found`。

再抽样验证不是全零：

```powershell
# 读取文件中段 1MB，确认不是一堆 0x00
python -c "f=open(r'<输出.mp4>','rb');f.seek(<size>//2);d=f.read(1048576);print('非零字节占比', round(sum(b!=0 for b in d)/len(d),3))"
```

占比应 > 0.9。

### 2.4 合并（多节视频合成一节）

平台常把一节课拆成 2 段。用 ffmpeg 无损拼接：

```powershell
# 先写 filelist.txt，每行 file '片段路径'
ffmpeg -f concat -safe 0 -i filelist.txt -c copy "<合并后.mp4>"
```

必须 `-c copy`，不要重编码（省时且无损）。

---

## 阶段 3：语音转写（通义听悟）

平台没有现成字幕时走这条路。**用户明确要求用通义听悟，不要用本地 whisper**。

### 3.1 抽音频

```powershell
ffmpeg -i "<视频.mp4>" -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k "<课次>.mp3"
```

16 kHz 单声道 64 kbps 对语音识别足够，文件小、上传快。

### 3.2 上传

听悟的 UI 有三层，直接点最外层不会触发文件选择器：

```
1. 点「上传音视频」            → 弹出面板
2. 点「上传本地音视频文件」     → 切到拖拽面板
3. 点「点击 / 拖拽」           → 才真正触发 <input type=file>
   然后 setFiles(音频路径)
```

用 `scripts/js/tingwu_upload.js`（Playwright 版，交给 Tabbit CLI 执行），或直接用 Windows-MCP 走 UI：
`Click` → `Click` → `Click`，文件选择框出现后用 `Type` 输入完整路径再回车。

上传成功后文件进入待转写列表，**还要再点「开始转写」**，否则一直排队：

```powershell
tabbit-cli nodejs --task "听悟" --request-id "tw-start-<随机>" --timeout-ms 60000 < scripts\js\tingwu_start.js
```

页面会显示"转写中，预计剩余 19:11"。

### 3.3 取回全文（关键技巧）

听悟的转写页是**虚拟列表**，`document.body.innerText` 只能拿到几千字，导出按钮也常点不出菜单。正确做法是直接调它的接口：

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
tabbit-cli resource --task "<任务名>" --resource "<resourceId>" --offset 0 --max-bytes 20000
# 按返回的 nextOffset 继续，直到 eof=true
# offsetUnit=4 表示 UTF-16 code units，不是字节
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

听悟的稿子句子完整，但数学术语错字密集。直接喂给模型会得到满篇"举证矩阵"。

```powershell
python -I scripts\clean_transcript.py "<语音文字稿目录>" "<输出目录>"
```

脚本内置术语表（`举证→矩阵`、`转制→转置`、`内机→内积`、`对焦化→对角化`、`现金代数→线性代数`……），并做三件事：

1. 繁转简（OpenCC `t2s`）
2. 碎段合并（间隔 ≤6 秒且合起来 ≤110 字）
3. 同音错字替换

输出 `语音文字稿_清洗/<课次>.txt`，**提交给 Tabbit 的是这一份**。

> 术语表是本项目的核心资产。每发现一个新错字就补进去，见 `scripts/clean_transcript.py` 顶部的 `FIX`。清洗后仍可疑的地方会由模型在生成时按板书校正，但不要指望它兜底。

---

## 阶段 5：提交 Tabbit 生成讲义

### 5.1 为什么要分三步

单次程序有 **180 秒硬超时**。上传 txt、引用视频、输入长 prompt 三件事加起来会超；分开后每步都在时限内。

`scripts/submit_to_tabbit.py` 封装了三步：

```powershell
python -I scripts\submit_to_tabbit.py `
  --lesson "第8周周二" `
  --txt "语音文字稿_清洗\第8周周二.txt" `
  --video "C:\Users\<你>\Videos\课程合并\数据科学与工程数学基础-第8周周二.mp4" `
  --prompt scripts\prompt_template.txt `
  --task "课程视频整理"
```

内部流程：

| 步骤 | 动作 | 关键点 |
|---|---|---|
| 1 | 新开 `web.tabbit.com/newtab` → 选「任务模式」→ 添加引用 → 上传 txt | 先关引导弹窗；点「生成文件、操作网页和长程任务。」进入任务模式 |
| 2 | 新开视频的 `file://` 页 → 回到 composer 添加视频引用 | 用标题匹配 `数据科学与工程数学基础-<课次>.mp4`；失败重试一次 |
| 3 | 用 `execCommand("insertText")` 灌入 prompt → 点 `Run` | 长文本不能用 `fill`，会被截断或触发校验 |

`prompt_template.txt` 里已经写死了所有硬性要求（见下节），**不要临时改写削弱约束**。

### 5.2 提示词里的硬性约束（改课时只换课次，不改这些）

- 公式全部 `\displaystyle`
- 内容用盒子（tcolorbox/mdframed）封装
- 章节结束**不换页**，继续往下写
- 多次编译保证目录、页码正确
- 不要空白页
- PDF 里不得出现 `#` 开头的 LaTeX 乱码
- **TXT 必须全量读取，不得遗漏**
- 标注课堂例题（写"课堂讲授"+时间戳）与考点/可能考的暗示
- 语音稿术语必须规范化，不得原样抄错字
- 交付：只要一个编译好的 PDF，作为"生成的文件"附件给出；不要 tex/py/图片/压缩包
- 精度：每块板书标 `[画面 mm:ss]`，每段引用标 `[录音 mm:ss]`，全篇录音引用 ≥15 处

### 5.2.1 提示词全文

实际提交时读取 `scripts/prompt_template.txt`；下面是同一份内容的全文，改课时只替换课次相关信息，**不要删减约束段落**。

```text
这个视频是需要你看的数据科学与工程数学基础课程，一共分2节课，已经合并成一个视频，你需要一步一步分析老师的板书图片，也就是你要对视频的具体关键帧进行截屏分析（注意：如果需要视觉查看老师板书内容，放大然后截图仔细做视觉上的分析），然后结合老师的讲课语音信息(我下面给你这几节课程对应的语音原文，你要严格详细分析语音原文然后和视频关键帧的板书和电脑上呈现的ppt进行双线分析)，也就是你要成为一个学生代替我上课，然后这几节课都要进行分析，详细分析文字稿，你在pdf中需要标注哪些例题是老师上课讲过的，并且把老师重点讲的内容和老师提到可能会考试的内容做重点标注，把老师重点讲的课本上的例题，重点讲的例题，并且如果老师提到考试，重点，考试可能考，类似这种明示或暗示这个点可能要考的地方你需要重点在pdf里面标注

然后你需要把复习资料整理成latex-pdf排版并且排版美观（公式全部用latex美观渲染，公式采用/displaystyle格式，相应的内容要用相应的盒子美观地封装，并且每一章节结束之后不要换页，继续往下编写，并且需要多次编译保证目录等内容正常显示）并且完整编译，并且latex要求极致的细致，每一个都要有详细的推导过程，做到课堂上仔细思考，不要换页不要有空白要对知识详细描述讲解，直接交付干净的pdf，不要交付压缩包等东西

你在pdf中需要标注哪些例题是老师上课讲过的，并且把老师重点讲的内容和老师提到可能会考试的内容做重点标注

你需要保证pdf在latex公式渲染的时候不会在pdf里面出现# 开头的乱码

重要：语音稿是通义听悟自动转写，存在系统性同音错字（例如“举证”应为“矩阵”、“转制”应为“转置”、“内机”应为“内积”、“现金代数”应为“线性代数”、“对焦化”应为“对角化”）。你引用老师原话时必须改写为规范数学术语，绝对不能把错字原样抄进pdf；凡是语音听不清或术语可疑的地方，一律以视频里的板书和PPT画面为准。

分析深度要求（必须遵守）：每个知识板块都要引用老师原话并标注录音时间（格式 [录音 mm:ss]），全篇不少于 15 处；每一块板书或 PPT 幻灯片都要标注对应的视频时间（格式 [画面 mm:ss]），并写清楚板书/幻灯片上的具体公式、符号与下标；凡是语音听不清、术语可疑或与板书/PPT 冲突的地方，一律以板书/PPT 画面为准，并在文中注明依据的是哪一帧画面。例题必须标明是否为课堂上老师讲过（课堂例题写“课堂讲授”，并给时间戳）。

交付要求（必须遵守）：最终只交付一个编译好的 pdf 文件，并且必须把这个 pdf 作为“生成的文件”里的附件直接给出，让我能点击下载；不要交付 tex、py、图片、压缩包等任何中间文件，也不要把 pdf 只保存在沙箱里而不作为附件输出。交付前请确认“生成的文件”列表中能看到该 pdf。

这几节课程对应的语音转文字如下txt文件，这个txt文件你需要全量读取不要遗漏，这是老师完整的语音转文字内容：
```

> 提示词末尾必须保留这句"引导语"——后面紧跟着上传的 txt，模型才知道该读它。

### 5.3 并发上限

**同时最多 3 个生成任务**。更多会互相拖慢，且容易触发平台限流或任务相互干扰。

### 5.4 等待与轮询

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
python -I scripts\check_pdf.py "<pdf>" "<报告.txt>"
```

检查项与判据：

| 项 | 合格标准 |
|---|---|
| 页数 / 字数 | 有值，字数与课长匹配（一般 2 万–5 万） |
| 空白页 | `blank=[]` |
| 目录 | `toc=True` |
| 例题 / 考点 | `example=True`、`exam=True` |
| 语音错字 | 命中的必须**全部**落在勘误对照表页内 |
| LaTeX 泄漏 | `hash_line=0`、`displaystyle=0`、`begin_cmd=0`、`frac=0`、`dollar=0` |
| 引号配对 | `“` 与 `”` 数量接近（跨页引用允许少量差值） |

错字命中要人工回看上下文——在附录"转写原样 → 应为"对照表里属正常，出现在正文就返工重生成。

### 6.3 重生成

不合格时不要手工改 PDF。回到 Tabbit，新开一个 request，把失败点写进 prompt 追加段（例如"上一版第 25 页出现 `\frac` 残留，请检查所有公式环境"），重新生成。

---

## 阶段 7：归档与清理

```
交付目录/
├── 数据科学与工程数学基础-第十一次课.pdf
└── 交付说明.md          ← 明细表：文件 / 对应课堂 / 页数 / 字数 / 状态
```

更新交付说明时：
- 加一行明细
- 更新总数
- 记录本课特殊说明（旧版缺陷、转写工具变更等）

清理（用户通常明确要求）：
1. 关闭 Tabbit 相关标签页（或直接关掉整个 Tabbit 进程）
2. 关闭 Motrix 前先确认 `aria2.tellActive` 返回空
3. 停掉后台轮询脚本
4. 确认没有残留的 python / ffmpeg 进程

> 关浏览器进程会丢掉用户其他标签，**先问一句**；用户说"直接关"再关。

---

## 交付前的最后一道检查

```
[ ] PDF 在交付目录，文件名符合「<课程名>-第X次课.pdf」
[ ] 无压缩包、无 tex、无中间图片一起交付
[ ] check_pdf.py 全绿
[ ] 交付说明.md 已更新
[ ] 临时进程已清理
```

---

## 相关文档

- [批量处理多节课](references/batch-mode.md)
- [工具与 API 速查](references/toolchain.md)
- [故障排查](references/troubleshooting.md)
