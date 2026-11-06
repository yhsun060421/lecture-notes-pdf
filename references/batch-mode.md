# 批量处理多节课

一次处理 5–20 节课时，单课流程照样走，但**阶段必须拉平成"按阶段批处理"**，而不是"一节课走到底再下一节"。原因：下载、转写、生成三个阶段的瓶颈完全不同，串行会被最慢的一环卡住。

---

## 一、正确的批量节奏

```
全部课程  ──▶ [A] 批量取直链 + 批量丢进 Motrix（每任务 8 连接，同时 2–3 个）
                    ↓
                [B] 批量抽音频 + 逐节上传听悟（上传串行，转写并行）
                    ↓
                [C] 批量取回全文 + 批量清洗
                    ↓
                [D] 分批提交 Tabbit（同时最多 3 个任务）
                    ↓
                [E] 轮流轮询 → 取回 → 质检 → 归档
```

**不要**：第 1 节下载完→转写→生成→交付，再开第 2 节。这样 GPU/网络/平台额度全程只有一条线在跑。

---

## 二、状态文件（批量模式的中枢）

一节课一个状态文件，放在 `state/<课次>.json`：

```json
{
  "lesson": "第8周周二",
  "order": 11,
  "video_url": "https://...",
  "video_path": "C:\\Users\\<你>\\Videos\\课程合并\\数据科学与工程数学基础-第8周周二.mp4",
  "video_size": 885483291,
  "style": "html-color",
  "download": "done",
  "transcribe": "done",
  "trans_id": "klrbn2oozrxbq5zy",
  "transcript_txt": "语音文字稿/第8周周二.txt",
  "clean_txt": "语音文字稿_清洗/第8周周二.txt",
  "submit": "done",
  "session_id": "865a4e5e-48f2-4ce6-8e93-6393bd429136",
  "pdf": "数据科学与工程数学基础-复习讲义PDF/数据科学与工程数学基础-第十一次课.pdf",
  "pages": 33,
  "chars": 40504,
  "status": "delivered"
}
```

各字段取值：`pending / running / done / failed / skipped`。

**每完成一步立刻落盘**，这是断点续跑的唯一依据。批量脚本重启时只处理非 `done` 的项。

---

## 三、并发控制表

| 阶段 | 建议并发 | 原因 |
|---|---|---|
| 取直链 | 1（串行） | 浏览器只有一个登录态，并发点页面会互相干扰 |
| 下载 | 2–3 个 Motrix 任务（每个 8 连接） | 源站限单 IP，任务开太多反而互相抢带宽 |
| 抽音频 / 合并 | 2–4 | ffmpeg 吃 CPU，别和转写抢 |
| 听悟上传 | 1（串行） | 网页端同一个上传面板，并发会互相覆盖 |
| 听悟转写（排队中） | 平台侧并行 | 上传后即可传下一节，不用等 |
| 术语清洗 | 4 | 纯文本处理，很快 |
| **Tabbit 生成** | **≤3** | 用户硬性要求，超过会互相拖慢并触发限流 |
| PDF 取回 | 1–2 | 会话页点击下载需要串行确认 |

---

## 四、分步实施

### A. 批量取直链

课程平台的播放页需要登录态和短时签名，必须用浏览器：

1. 用 Windows-MCP 打开资源列表 → `Snapshot` 拿全部课程条目
2. 逐节 `Click` 进入播放页，抓 `.mp4` 请求 URL
3. 立刻写进对应 `state/*.json`（签名会过期）

若平台结构稳定，可退化为：在已登录的浏览器里用 JS 批量取 `performance.getEntriesByType("resource")`，一次拿一页的所有媒体请求。

### B. 批量下载（Motrix）

```powershell
# 每节课一条 Motrix（aria2 RPC）任务，8 连接；同时最多 2–3 个任务
foreach ($s in $states) {
  if ($s.download -ne "done") { 添加 Motrix 任务 }
}
# 轮询 tellActive，全部为空后再校验
```

图形界面等价操作：把直链逐条粘贴进 Motrix 新建任务。**不要用自写下载器当主路径**。

校验统一走 `ffprobe` + 非零字节抽样（见主文档 2.3）。**校验不过的一律重下**，不要试图修复。

### C. 批量转写

听悟上传必须串行：

```powershell
foreach ($lesson in $lessons) {
  ffmpeg 抽音频
  tabbit-cli 执行 tingwu_upload.js   # 上传
  tabbit-cli 执行 tingwu_start.js    # 点开始转写
  记录 trans_id 到 state
}   # 全部提交后统一等待，不要一个个等
```

全部提交后，每隔 10–15 分钟查一次各 `trans_id` 的字数与时长，齐了再统一取全文。

### D. 分批提交 Tabbit

按 `order` 顺序，每次取 3 节：

```
提交 1/2/3 → 等 1 完成 → 补 4 → 等 2 完成 → 补 5 …
```

保持"完成一个补一个"的滑动窗口，而不是等 3 个全完再提交下一批（会有空窗）。

提交后用文件库接口统一轮询，命中即取回。

### E. 质检与归档

- 每份 PDF 跑 `check_pdf.py --style <latex|html-color|html-bw>`（与提交时的 `--style` 一致）
- 不合格的进重试队列，失败原因写进 `state.fail_reason`
- 合格的复制到交付目录并按中文序数改名
- 全部完成后一次性更新 `交付说明.md`

---

## 五、批量脚本骨架

```python
import json, pathlib, subprocess, sys

STATE = pathlib.Path("state")
PY = sys.executable

def load_all():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(STATE.glob("*.json"))]

def save(st):
    (STATE / f"{st['lesson']}.json").write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

def step_download(st):
    if st.get("download") == "done":
        return
    # 硬约束：走 Motrix 的 aria2 RPC（图形界面等价于把直链粘贴进 Motrix）
    add_motrix_task(st["video_url"], st["video_path"], split=8)
    wait_motrix_done(st["video_path"])
    # 校验通过才置 done
    st["download"] = "done"
    save(st)

def main():
    todo = [s for s in load_all() if s.get("status") != "delivered"]
    for st in todo:
        step_download(st)
    # 其余阶段同理，按阶段整体推进
```

要点：
- **阶段内批量、阶段间串行**（A 全做完再 B）
- 每步前后都写状态文件
- 失败不中断整体流程，记为 `failed` 后继续，最后统一重试

---

## 六、批量模式下最容易犯的三个错

1. **并发超额**：图快同时开 5 个 Tabbit 任务 → 全部变慢，还可能互相串上下文。严守 3 个。
2. **状态不落盘**：脚本跑到一半断了，重跑时不知道哪些已完成，重复下载/重复提交浪费额度。每步必写。
3. **把单课脚本套在循环里**：单课脚本里有"等待生成完成"的阻塞逻辑，套循环会变成串行。要拆成可重入的单步函数。

---

## 七、批量完成后的统一收尾

```powershell
# 1. 检查状态文件里没有非 done 的项
Select-String -Path state\*.json -Pattern '"status": "(pending|running|failed)"'

# 2. 核对交付目录数量与 `ls` 一致
(Get-ChildItem "数据科学与工程数学基础-复习讲义PDF\*.pdf").Count

# 3. 更新交付说明.md 的总数
# 4. 关闭 Tabbit / Motrix / 后台轮询
```
