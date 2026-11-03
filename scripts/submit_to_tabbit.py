# -*- coding: utf-8 -*-
"""向 Tabbit 任务模式提交一节课的双线分析任务（分三步，规避 180 秒超时）。

用法：
    python -I submit_to_tabbit.py \
        --lesson "第8周周二" \
        --txt "语音文字稿_清洗\\第8周周二.txt" \
        --video "C:\\Users\\你\\Videos\\课程合并\\数据科学与工程数学基础-第8周周二.mp4" \
        --prompt prompt_template.txt \
        [--task 课程视频整理] [--video-title 自定义视频标题]

三步：
    1) 新开 newtab -> 任务模式 -> 添加引用 -> 上传 txt
    2) 新开视频 file:// 页 -> 回到 composer 添加视频引用
    3) insertText 灌 prompt -> 点 Run

提交后任务在 Tabbit 侧异步运行，用文件库接口轮询产物。
"""
import argparse
import base64
import json
import os
import subprocess
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(HERE, "js")
CLI = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tabbit", "LocalAgent", "bin", "tabbit-cli.exe")

JS_STEP1 = r"""const LESSON = __LESSON__;
const TXT = __TXT__;
const p = await context.newPage();
await p.goto("https://web.tabbit.com/newtab", {waitUntil: "domcontentloaded", timeout: 40000});
await p.waitForFunction(() => !!document.querySelector("button[aria-label='选择输入模式']"), null, {timeout: 45000});
await p.waitForTimeout(2500);
for (let i = 0; i < 4; i++) {
  const g = p.locator("button[aria-label='关闭引导']");
  const n = await g.count().catch(() => 0);
  if (!n) break;
  await g.first().click({timeout: 3000, force: true}).catch(() => {});
  await p.waitForTimeout(400);
}
try {
  await p.locator("button[aria-label='选择输入模式']").click({timeout: 10000});
} catch (e) {
  await p.mouse.click(57, 356);
}
await p.waitForTimeout(1500);
await p.getByText("生成文件、操作网页和长程任务。", {exact: false}).first().click({timeout: 12000});
await p.waitForTimeout(2000);
await p.locator("button[aria-label='添加引用内容']").click({timeout: 15000});
await p.waitForTimeout(1800);
const fcWait = p.waitForEvent("filechooser", {timeout: 12000}).catch(() => null);
await p.getByText("上传本地文件", {exact: true}).first().click({timeout: 10000});
const fc = await fcWait;
if (fc) await fc.setFiles(TXT);
await p.waitForTimeout(5000);
const body = await p.evaluate(() => (document.body.innerText || "").slice(0, 400));
return {url: p.url(), uploaded: !!fc, hasTxt: body.includes(LESSON + ".txt"), body};
"""

JS_STEP2 = r"""const LESSON = __LESSON__;
const VIDEO = __VIDEO__;
const TITLE = __TITLE__;
const vid = await context.newPage();
await vid.goto(VIDEO, {waitUntil: "domcontentloaded", timeout: 30000});
await vid.waitForTimeout(1500);
const news = context.pages().filter(x => x.url().includes("web.tabbit.com") && x.url().includes("newtab"));
let p = null;
for (const c of news) {
  try { const b = await c.evaluate(() => document.body.innerText || ""); if (b.includes(LESSON + ".txt")) { p = c; break; } } catch (e) {}
}
if (!p && news.length) p = news[0];
if (!p) return {err: "composer page missing"};
let refOk = false, lastErr = null;
for (let k = 0; k < 2 && !refOk; k++) {
  try { await vid.waitForFunction(t => document.title.includes(t), TITLE, {timeout: 15000}); } catch (e) { lastErr = "title"; }
  await p.locator("button[aria-label='添加引用内容']").click({timeout: 15000});
  await p.waitForTimeout(1800);
  await p.keyboard.type(LESSON);
  await p.waitForTimeout(2200);
  try {
    await p.getByText(TITLE, {exact: false}).first().click({timeout: 8000});
    refOk = true;
  } catch (e) {
    lastErr = String(e).slice(0, 100);
    await p.keyboard.press("Escape").catch(() => {});
    await p.waitForTimeout(1500);
  }
}
await p.waitForTimeout(1200);
const body = await p.evaluate(() => (document.body.innerText || "").slice(0, 400));
return {refOk, lastErr, hasMp4: body.includes(TITLE), body};
"""

JS_STEP3 = r"""const LESSON = __LESSON__;
const B64 = __B64__;
const news = context.pages().filter(x => x.url().includes("web.tabbit.com") && x.url().includes("newtab"));
let p = null;
for (const c of news) {
  try { const b = await c.evaluate(() => document.body.innerText || ""); if (b.includes(LESSON + ".txt")) { p = c; break; } } catch (e) {}
}
if (!p && news.length) p = news[0];
if (!p) return {err: "composer page missing"};
await p.evaluate(({b64}) => {
  const bin = atob(b64);
  const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
  const text = new TextDecoder().decode(bytes);
  const el = document.querySelector("[role=textbox]");
  el.focus();
  document.execCommand("insertText", false, text);
}, {b64: B64});
await p.waitForTimeout(2000);
let sent = false, err = null;
try {
  await p.getByRole("button", {name: "Run", exact: true}).first().click({timeout: 10000});
  sent = true;
} catch (e) { err = String(e).slice(0, 200); }
await p.waitForTimeout(14000);
const body = await p.evaluate(() => (document.body.innerText || "").slice(-400));
return {sent, err, url: p.url(), cancelled: body.includes("任务已取消"), tail: body.replace(/\s+/g, " ").slice(-160)};
"""


def run_js(name: str, code: str, task: str, rid: str, timeout_ms: int = 150000) -> dict:
    os.makedirs(JS_DIR, exist_ok=True)
    path = os.path.join(JS_DIR, f"_stage_{name}.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    proc = subprocess.run(
        [CLI, "nodejs", "--task", task, "--request-id", rid, "--timeout-ms", str(timeout_ms)],
        stdin=open(path, "rb"), capture_output=True,
    )
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    with open(os.path.join(HERE, "submit.log"), "a", encoding="utf-8") as f:
        f.write(f"=== {rid} ===\n{out}\n{err}\n")
    print(f"[{rid}] exit={proc.returncode} out={len(out)} err={len(err)}")
    try:
        return json.loads(out.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return {"raw": out[-300:], "err": err[-300:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson", required=True, help="课次标识，如 第8周周二")
    ap.add_argument("--txt", required=True, help="清洗后的语音稿路径")
    ap.add_argument("--video", required=True, help="本地视频文件路径")
    ap.add_argument("--prompt", default=os.path.join(HERE, "prompt_template.txt"))
    ap.add_argument("--task", default="课程视频整理")
    ap.add_argument("--video-title", default="", help="引用区显示的视频标题，默认按命名约定推导")
    args = ap.parse_args()

    lesson = args.lesson
    txt = os.path.abspath(args.txt)
    video_path = os.path.abspath(args.video).replace("\\", "/")
    video_url = "file:///" + quote(video_path, safe="/:")
    title = args.video_title or f"数据科学与工程数学基础-{lesson}.mp4"
    prompt = open(args.prompt, encoding="utf-8").read().strip()
    b64 = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
    tag = time.strftime("%m%d%H%M")
    slug = lesson.replace("第", "w").replace("周", "").replace("周", "")

    js1 = JS_STEP1.replace("__LESSON__", json.dumps(lesson, ensure_ascii=False)).replace(
        "__TXT__", json.dumps(txt, ensure_ascii=False))
    r1 = run_js("1", js1, args.task, f"st1-{slug}-{tag}", 120000)
    print("STEP1", json.dumps(r1.get("result", {}).get("value", r1), ensure_ascii=False)[:500])

    js2 = JS_STEP2.replace("__LESSON__", json.dumps(lesson, ensure_ascii=False)).replace(
        "__VIDEO__", json.dumps(video_url, ensure_ascii=False)).replace(
        "__TITLE__", json.dumps(title, ensure_ascii=False))
    r2 = run_js("2", js2, args.task, f"st2-{slug}-{tag}", 150000)
    print("STEP2", json.dumps(r2.get("result", {}).get("value", r2), ensure_ascii=False)[:500])

    js3 = JS_STEP3.replace("__LESSON__", json.dumps(lesson, ensure_ascii=False)).replace(
        "__B64__", json.dumps(b64))
    r3 = run_js("3", js3, args.task, f"st3-{slug}-{tag}", 120000)
    print("STEP3", json.dumps(r3.get("result", {}).get("value", r3), ensure_ascii=False)[:500])
    print("\n提交完成。下一步：记录会话 URL，用文件库接口轮询 PDF 产物。")


if __name__ == "__main__":
    main()
