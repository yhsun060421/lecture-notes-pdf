# 故障排查

按"症状 → 判据 → 处置"组织。这些都是真实踩过的坑。

---

## 一、下载

### 视频文件大小正确但内容空洞

**症状**：`ls` 显示 885 MB，`ffprobe` 报 `moov atom not found`，播放器打不开或只能播开头几秒。

**判据**：抽文件中间 1 MB 看非零字节占比：

```powershell
python -c "f=open(r'<文件>','rb');f.seek(<size>//2);d=f.read(1048576);print(round(sum(b!=0 for b in d)/len(d),3))"
```

占比远低于 1 就确认是空洞文件。

**根因**：用 `f.truncate(total)` 预分配后单线程顺序写，中途异常但文件大小已经是最终值，看起来"下完了"。

**处置**：删掉重下，改用 8 MB 分块 + 每块独立 Range + 状态文件。用 `scripts/download_chunked.py`，只有输出 `ALL_OK` 才算成功。

### 不支持 Range

**症状**：`curl -sI -H "Range: bytes=0-1"` 返回 `200` 而不是 `206`，响应头没有 `Content-Range`。

**处置**：只能单线程下载。仍用 `download_chunked.py` 但并发数设 1，或改用 `curl -C -` 断点续传。

### aria2 任务一直 `active` 但不增长

**判据**：`aria2.tellStatus` 里 `connections` 为 0 且 `errorCode` 有值（常见 22 = HTTP 响应头异常，可能签名过期）。

**处置**：重新取直链（签名通常几小时过期），删旧任务重建。

---

## 二、转写

### 点「上传音视频」没有文件选择框

**根因**：听悟的上传是一个三步 UI，不是直接弹选择器。

**处置**：必须依次点「上传音视频」→「上传本地音视频文件」→「点击 / 拖拽」。第三步才触发隐藏的 `input[type=file]`。用 `scripts/js/tingwu_upload.js`。

### 上传成功但一直"排队中"

**根因**：文件只是进了列表，**还没点「开始转写」**。

**处置**：调用 `scripts/js/tingwu_start.js`，页面出现"转写中，预计剩余 xx:xx"才算真的开始。

### 导出的文本只有两三千字

**根因**：转写页是虚拟列表，`document.body.innerText` 只包含视口附近的节点；「导出」按钮的菜单也常常点不出来。

**处置**：走接口 `POST /api/trans/getTransResult?c=web`，body `{"transId":"<id>"}`。详见主文档 3.3。

### 接口返回 405 / `TRS.InvalidTrans`

- `GET` → 必须 `POST`
- `{"transIds":[...]}` → 必须单个 `transId`
- `data.result` 是字符串 → 要再 `JSON.parse` 一次

### 结果太长，CLI 返回 resourceId

**处置**：`tabbit-cli resource --offset <nextOffset> --max-bytes 20000` 循环读到 `eof=true`，把各片 `data` 拼接再 `json.loads`。注意 `offsetUnit=4` 表示 UTF-16 code units。

---

## 三、Tabbit 生成

### 单次程序 180 秒超时

**根因**：上传 txt + 引用视频 + 灌长 prompt 放一个程序里必超。

**处置**：拆三步，每步一个 `--request-id`（见 `scripts/submit_to_tabbit.py`）。

### 长 prompt 被截断

**根因**：`locator.fill()` 对富文本编辑器会触发校验或只写第一段。

**处置**：用 `document.execCommand("insertText", false, text)`，文本经 base64 传入，避免引号/换行导致 JS 语法错误。

### 任务被平台自动取消

**判据**：页面出现「任务已取消」。

**处置**：检查引用是否成功（视频标题是否出现在引用区）、TXT 是否上传完成。重新提交时换新 `request-id`。

### 轮询文件库一直没新文件

**判据**：`created_at` 没有晚于提交时间的项。

**处置**：先看会话页是否有「任务错误」；再确认任务是否还在执行。PDF 生成通常 20–50 分钟，别过早判失败。

---

## 四、取回与质检

### 从文件库 file_id 换下载链接返回 `file.notFound`

**根因**：预签名接口只认 COS 对象，不认文件库条目。

**处置**：打开会话页，点附件卡片的「下载」，用 CDP 监听 `Network.requestWillBeSent` 抓 `myqcloud.com` URL。用 `scripts/fetch_pdf.py`。

### 引号数量不相等

**判据**：`“` 与 `”` 差 1–3 个。

**处置**：多数是跨页引用（左引号在上一页末尾、右引号在下一页开头），属正常。差值超过 5 再回看。

### 术语错字命中

**判据**：`check_pdf.py` 的 `hits` 非空。

**处置**：看上下文位置。在附录"转写原样 → 应为"对照表里属**刻意保留**；出现在正文说明模型直接抄了听悟错字，必须重生成。

### 出现 `#` 开头的行

**根因**：LaTeX 宏参数写坏或 `#` 未转义。

**处置**：直接返工。在重生成 prompt 里追加"上一版出现以 # 开头的乱码行，请检查所有宏参数与特殊字符转义"。

---

## 五、收尾

### 关不掉某个标签页

三种情况：

1. **`chrome.tabs.remove is not a function`** —— `tabbit.evaluate` 只有只读 `chrome.*`，改用 Playwright `page.close()`（需 `--tab` 收购）
2. **`CROSS_WINDOW_CLAIM`** —— 该标签在另一个窗口。换一个新任务名收购（新任务未绑定窗口），或直接跳过
3. **`CLAIM_FAILED` + 页面显示"正在与 Gemini 分享"** —— 扩展页或被其他会话占用，Playwright 无法接管。用 UIA 点标签的「关闭」按钮：

```powershell
powershell -File scripts\close_tab_uia.ps1 -TitleLike "*复习讲义*"
```

### 批量关标签时全部失败

**根因**：ID 列表是 CRLF 行尾，`read` 进来的 id 末尾带 `\r`，传给 CLI 变成无效 ID。

**判据**：`file ids.txt` 显示 `with CRLF line terminators`。

**处置**：`tr -d '\r' < ids.txt > ids2.txt`，或脚本里 `id=${id%$'\r'}`。

### 文件删不掉，提示 `Device or resource busy`

**根因**：还有下载进程持有句柄。

**处置**：先用 `Process`/`Get-CimInstance` 确认是哪个 python/curl 在跑，结束后再删。不要直接 `rm -rf` 硬删。

---

## 六、环境

### `python` 不是 Anaconda

**症状**：`import pymupdf` 失败，`ModuleNotFoundError`。

**根因**：Git Bash 的 `python` 指向 `C:\msys64\mingw64\bin\python.exe`。

**处置**：一律写全路径 `D:\Anaconda\python.exe`，并加 `-I`。

### 控制台中文乱码

**根因**：Windows 控制台默认 GBK。

**处置**：不要直接 `print` 中文。把结果写 UTF-8 文件，再用 Read 工具读。

```python
open("out.txt", "w", encoding="utf-8").write(text)
```

### Tabbit 任务空闲过期

**症状**：`task.expired`。

**处置**：90 秒无操作会释放所有权（标签保留）。重新用同名任务 + 新 `request-id` 即可继续，不需要重建页面。
