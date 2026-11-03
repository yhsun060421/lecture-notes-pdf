# 工具与 API 速查

---

## 一、Windows-MCP（本机全局安装）

### 安装与注册

```powershell
# 全局安装（PyPI，要求 Python 3.14+）
uv tool install windows-mcp

# 可执行文件位置
C:\Users\<你>\.local\bin\windows-mcp.exe

# 注册到 Claude Code（user 作用域，所有项目可用）
claude mcp add --scope user windows-mcp -- "C:\Users\<你>\.local\bin\windows-mcp.exe" serve

# 验证
claude mcp get windows-mcp    # 应显示 Status: ✔ Connected, Scope: User config
```

可选：开机自启的后台服务

```powershell
windows-mcp install            # 创建计划任务 windows-mcp-server
windows-mcp uninstall          # 卸载
# 日志：~/.windows-mcp/server.log
```

### 在本流水线里什么时候用

| 场景 | 工具 | 说明 |
|---|---|---|
| 找课程、进播放页 | `Snapshot` → `Click` | 先看元素树，再按 id/文本点击 |
| 确认页面长什么样 | `Screenshot` | 视觉核对，比元素树直观 |
| 播放页取直链 | `Snapshot` + `PowerShell` | 元素树里找 media 链接，或开 DevTools |
| 文件选择框 | `Type` + `Enter` | 直接输入完整路径，比点目录快 |
| 等页面加载 | `WaitFor` | 等元素出现/文本变化，别用固定等待 |
| 批量文件操作 | `FileSystem` / `PowerShell` | 改名、复制、统计 |
| 进程收尾 | `Process` / `PowerShell` | 关 Motrix、查残留 |

### 调用契约

- **所有工具都是同步阻塞的**，一次一个动作
- `Snapshot` 返回的元素 id 会随页面变化失效，**操作后重新 Snapshot**
- 输入文本用 `Type`；长文本（>2000 字）用 `Clipboard` + `Shortcut("ctrl","v")`
- 鼠标坐标与 UIA 同一坐标系，无 DPI 偏差
- 截图默认上限 1920×1080；4K 屏加 `WINDOWS_MCP_SCREENSHOT_SCALE=0.6`

### 典型代码块（伪代码，实际由 agent 调用工具）

```
App(name="chrome")                      # 切到浏览器
Snapshot()                              # 看当前页
Click(element_id=42)                    # 点"资源管理"
WaitFor(text="播放")                     # 等加载
Snapshot()                              # 重新看
Click(element_id=88)                    # 点某一节
Screenshot()                            # 视觉确认播放器已加载
```

---

## 二、Tabbit CLI（浏览器自动化与任务模式）

### 路径

```text
C:\Users\<你>\AppData\Local\Tabbit\LocalAgent\bin\tabbit-cli.exe
```

### 常用命令

```powershell
# 查看标签库存（不打开任何东西）
tabbit-cli create --task "课程整理"

# 执行一段 JS（每次都换新的 request-id，复用会返回旧回执）
tabbit-cli nodejs --task "课程整理" --request-id "job-20261103-01" --timeout-ms 150000 < script.js

# 收购指定标签后操作
tabbit-cli nodejs --task "课程整理" --tab 487459404 --request-id "close-1" --timeout-ms 60000 < close_one.js

# 读大结果（分片，offsetUnit=4 是 UTF-16 code units）
tabbit-cli resource --task "课程整理" --resource "result-xxxx" --offset 0 --max-bytes 20000

# 结束任务（保留标签）
tabbit-cli finish --task "课程整理"
# 连任务拥有的标签一起关（慎用：会关掉收购来的用户标签）
tabbit-cli finish --task "课程整理" --discard
```

### 约束

| 项 | 值 |
|---|---|
| 单次 JS 超时 | 默认 60 秒，最大 180 秒 |
| 任务空闲过期 | 90 秒 |
| `--request-id` | 每次必须唯一，否则拿到旧回执 |
| JS 全局 | `page`、`pages()`、`usePage`、`context`、`tabbit`、`expect`、`artifactPath` |
| `tabbit.evaluate` | 只读 `chrome.*`（`chrome.tabs.remove` 不存在） |

### 关闭标签的两条路

1. **Playwright**：`--tab <id>` 收购后 `page.close()` —— 适用于普通网页
2. **UIA**：扩展页（`chrome-extension://`）无法收购，用 Windows UIAutomation 找到标签的「关闭」按钮并 `Invoke()`

```powershell
# 第 2 条的完整实现见 scripts/close_tab_uia.ps1
powershell -File scripts\close_tab_uia.ps1 -TitleLike "*复习讲义*"
```

---

## 三、通义听悟

| 项 | 值 |
|---|---|
| 地址 | `https://tingwu.aliyun.com` |
| 上传路径 | 首页「上传音视频」→「上传本地音视频文件」→「点击 / 拖拽」 |
| 转写记录页 | `/doc/transcripts/<transId>` |
| 取全文接口 | `POST /api/trans/getTransResult?c=web` |
| 请求体 | `{"transId":"<id>"}` |
| 返回 | `data.result` 是 JSON **字符串**，再 parse 得 `{pg:[{sc:[{bt,et,tc}]}]}` |
| 时长 | `data.duration`（秒） |
| 字数 | `data.wordCount` |

常见错误：

- `GET` → `405 Method Not Allowed`，必须 POST
- `{"transIds":[...]}` → `TRS.InvalidTrans`，必须单个 `transId`
- 直接读 `innerText` → 只有几千字（虚拟列表）

---

## 四、Motrix / aria2 JSON-RPC

```text
POST http://127.0.0.1:16800/jsonrpc
Content-Type: application/json
```

无 secret 时 params 直接传数组；有 secret 时第一个参数为 `"token:<secret>"`。

| 方法 | 用途 |
|---|---|
| `aria2.addUri` | 添加下载 |
| `aria2.tellStatus` | 查单个任务 |
| `aria2.tellActive` | 查所有进行中（收尾前必查） |
| `aria2.pauseAll` / `aria2.unpauseAll` | 暂停/恢复 |

推荐选项：

```json
{"split":"8","max-connection-per-server":"8","min-split-size":"8M"}
```

---

## 五、ffmpeg / ffprobe

```powershell
# 抽音频（听悟上传用）
ffmpeg -i in.mp4 -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k out.mp3

# 无损拼接
ffmpeg -f concat -safe 0 -i filelist.txt -c copy merged.mp4

# 校验
ffprobe -v error -show_entries format=duration,size -of default=nw=1 merged.mp4
```

---

## 六、Python 环境（本机）

| 项 | 值 |
|---|---|
| 解释器 | `D:\Anaconda\python.exe`（Git Bash 里的 `python` 指向 msys64，**没有 pymupdf**） |
| 必需包 | `pymupdf`、`opencc-python-reimplemented` |
| 安装 | `D:\Anaconda\python.exe -m pip install pymupdf opencc-python-reimplemented` |

> 所有脚本都用 `-I` 隔离模式跑，避免当前目录的 `json.py` 之类劫持 import。

---

## 七、文件库 API（Tabbit Space）

```js
GET /api/v0/tabbit-space/files?type=all&limit=36
// 分页：next_cursor
// item: { id, filename, content_type, source.chat_session_id, created_at }
```

用途：轮询新生成的 PDF。判据用 `filename` + `created_at`，不要只看 `id`。

预签名下载：

```js
POST /api/v0/cos/presigned-download-url
{"file_id":"...","expires_in":1728000}
```

⚠️ 对**文件库的 file_id** 直接调用会返回 `{'detail': 'file.notFound'}`。正确做法是从会话页的附件卡片点「下载」，用 CDP 抓 `myqcloud.com` 的 URL。
