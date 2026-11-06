# -*- coding: utf-8 -*-
"""向 Tabbit 任务模式提交一节课的讲义生成任务（分三步，规避 180 秒超时）。

用法：
    python -I submit_to_tabbit.py \
        --course "数据科学与工程数学基础" \
        --lesson "第8周周二" \
        --sections 2 \
        --txt "语音文字稿_清洗\\第8周周二.txt" \
        --video "C:\\Users\\你\\Videos\\课程合并\\数据科学与工程数学基础-第8周周二.mp4" \
        --style html-color \
        [--ref assets/reference_lecture_style.html] \
        [--task 课程讲义] [--video-title 自定义视频标题] [--out-name 输出文件名]

--style 三选一（对应 scripts/ 下三份提示词）：
    latex       LaTeX 排版（xelatex -> PDF）
    html-color  彩色 HTML 排版（Chromium 打印 A4 彩色 PDF）
    html-bw     黑白 HTML 排版（Chromium 打印 A4 黑白 PDF）

html-color / html-bw 会自动把 assets/reference_lecture_style.html 作为
「样式参考」随语音稿一起上传；这一步是强制的，不传样板就没有统一版式。

三步：
    1) 新开 newtab -> 任务模式 -> 添加引用 -> 上传 txt
    2) 新开视频 file:// 页 -> 回到 composer 输入 @ 引用视频
    3) insertText 灌 prompt -> 点 Run

提交后任务在 Tabbit 侧异步运行，用文件库接口轮询产物。
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import quote

# Windows 控制台默认 GBK，打印会话摘要里的特殊字符会直接崩
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(HERE, "js")
CLI = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tabbit", "LocalAgent", "bin", "tabbit-cli.exe")

PROMPTS = {
    "latex": "prompt_latex.txt",
    "html-color": "prompt_html_color.txt",
    "html-bw": "prompt_html_bw.txt",
}

JS_STEP1 = r"""const LESSON = __LESSON__;
const TXTNAME = __TXTNAME__;
const TXT = __TXT__;
const REFS = __REFS__;
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
try {
  await p.getByText("任务", {exact: true}).first().click({timeout: 8000});
} catch (e) {
  await p.getByText("生成文件、操作网页和长程任务。", {exact: false}).first().click({timeout: 12000});
}
await p.waitForTimeout(2000);

// 一次上传：语音稿 + 所有参考文件；缺哪个补哪个
async function uploadOne(files) {
  await p.locator("button[aria-label='添加引用内容']").click({timeout: 15000});
  await p.waitForTimeout(1600);
  const w = p.waitForEvent("filechooser", {timeout: 12000}).catch(() => null);
  await p.getByText("上传本地文件", {exact: true}).first().click({timeout: 10000});
  const fc = await w;
  if (fc) await fc.setFiles(files);
  await p.waitForTimeout(5000);
  return !!fc;
}

const base = f => f.replace(/\\/g, "/").split("/").pop();
const first = await uploadOne([TXT].concat(REFS));
const full = () => p.evaluate(() => document.body.innerText || "");
let body = await full();
const missing = REFS.filter(f => !body.includes(base(f)));
for (const one of missing) {
  await uploadOne([one]);
  body = await full();
}
return {url: p.url(), uploaded: first, hasTxt: body.includes(TXTNAME),
        refs: REFS.map(f => [base(f), body.includes(base(f))]), body: body.slice(0, 900)};
"""

JS_STEP2 = r"""const LESSON = __LESSON__;
const TXTNAME = __TXTNAME__;
const VIDEO = __VIDEO__;
const TITLE = __TITLE__;
const KEY = __KEY__;
const vid = await context.newPage();
await vid.goto(VIDEO, {waitUntil: "domcontentloaded", timeout: 30000});
await vid.waitForTimeout(1500);
const news = context.pages().filter(x => x.url().includes("web.tabbit.com") && x.url().includes("newtab"));
let p = null;
for (const c of news) {
  try { const b = await c.evaluate(() => document.body.innerText || "");
        if (b.includes(TXTNAME) && !b.includes(TITLE)) { p = c; break; } } catch (e) {}
}
if (!p && news.length) p = news[0];
if (!p) return {err: "composer page missing"};
let refOk = false, lastErr = null;
for (let k = 0; k < 2 && !refOk; k++) {
  try { await vid.waitForFunction(t => document.title.includes(t), KEY, {timeout: 15000}); } catch (e) { lastErr = "title"; }
  try {
    const bx = p.locator("[role=textbox]").first();
    await bx.click({timeout: 10000});
    await p.keyboard.type("@");
    await p.waitForTimeout(1800);
    await p.keyboard.type(KEY);
    await p.waitForTimeout(2400);
    await p.getByText(TITLE, {exact: false}).first().click({timeout: 8000});
    refOk = true;
  } catch (e) {
    lastErr = String(e).slice(0, 120);
    await p.keyboard.press("Escape").catch(() => {});
    await p.waitForTimeout(1500);
  }
}
await p.waitForTimeout(1200);
const body = await p.evaluate(() => (document.body.innerText || "").slice(0, 400));
return {refOk, lastErr, hasMp4: body.includes(TITLE), body};
"""

JS_STEP3 = r"""const LESSON = __LESSON__;
const TXTNAME = __TXTNAME__;
const B64 = __B64__;
const news = context.pages().filter(x => x.url().includes("web.tabbit.com") && x.url().includes("newtab"));
let p = null;
for (const c of news) {
  try { const b = await c.evaluate(() => document.body.innerText || ""); if (b.includes(TXTNAME)) { p = c; break; } } catch (e) {}
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


def fill_prompt(prompt: str, course: str, lesson: str, sections: str,
                video_name: str, out_name: str, txt_name: str) -> str:
    """把模板里的 {{...}} 占位符替换成实际值。"""
    mapping = {
        "课程名": course,
        "讲次": lesson,
        "节数": sections,
        "视频文件": video_name,
        "输出文件名": out_name,
        "语音稿": txt_name,
    }
    for k, v in mapping.items():
        prompt = prompt.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[^}]+\}\}", prompt)
    if left:
        raise SystemExit(f"提示词里还有未替换的占位符：{sorted(set(left))}")
    return prompt


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
    ap.add_argument("--course", default="课程", help="课程全称，如 数据科学与工程数学基础")
    ap.add_argument("--lesson", required=True, help="课次标识，如 第8周周二")
    ap.add_argument("--sections", default="2", help="合并进本视频的节数")
    ap.add_argument("--txt", required=True, help="清洗后的语音稿路径")
    ap.add_argument("--video", required=True, help="本地视频文件路径")
    ap.add_argument("--style", default="latex", choices=sorted(PROMPTS),
                    help="排版风格：latex / html-color / html-bw")
    ap.add_argument("--prompt", default="", help="自定义提示词路径（覆盖 --style）")
    ap.add_argument("--ref", action="append", default=[],
                    help="随任务上传的参考文件（可重复）。html 排版默认自动带 assets/reference_lecture_style.html")
    ap.add_argument("--out-name", default="", help="交付 PDF 文件名，默认 <课程>_<讲次>.pdf")
    ap.add_argument("--task", default="课程讲义")
    ap.add_argument("--video-title", default="", help="引用区显示的视频标题，默认取视频文件名")
    ap.add_argument("--steps", default="123",
                    help="执行哪几步，默认 123。上一轮某步失败时用 --steps 23 续跑，不重复开新标签")
    args = ap.parse_args()

    lesson = args.lesson
    txt = os.path.abspath(args.txt)
    txt_name = os.path.basename(txt)
    video_path = os.path.abspath(args.video).replace("\\", "/")
    video_name = os.path.basename(video_path)
    video_url = "file:///" + quote(video_path, safe="/:")
    title = args.video_title or video_name
    key = os.path.splitext(video_name)[0]
    out_name = args.out_name or f"{args.course}_{lesson}.pdf"

    prompt_path = args.prompt or os.path.join(HERE, PROMPTS[args.style])
    prompt = fill_prompt(open(prompt_path, encoding="utf-8").read().strip(),
                         args.course, lesson, args.sections, video_name, out_name, txt_name)

    # 参考文件：html 排版必须带上官方样式样板
    refs = [os.path.abspath(p) for p in args.ref]
    if args.style.startswith("html"):
        sample = os.path.join(HERE, "..", "assets", "reference_lecture_style.html")
        sample = os.path.abspath(sample)
        if not refs:
            if not os.path.exists(sample):
                raise SystemExit(f"找不到样式样板：{sample}")
            refs = [sample]
    for r in refs:
        if not os.path.exists(r):
            raise SystemExit(f"参考文件不存在：{r}")

    b64 = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
    tag = time.strftime("%m%d%H%M")
    # requestId \u5fc5\u987b\u662f\u8def\u5f84\u5b89\u5168\u7684 ASCII\uff0c\u4e2d\u6587\u8bfe\u6b21\u540d\u4e00\u5f8b\u9000\u5316\u4e3a lesson
    slug = re.sub(r"[^0-9A-Za-z]+", "", lesson)[-12:] or "lesson"

    steps = args.steps
    js1 = JS_STEP1.replace("__LESSON__", json.dumps(lesson, ensure_ascii=False)).replace(
        "__TXTNAME__", json.dumps(txt_name, ensure_ascii=False)).replace(
        "__TXT__", json.dumps(txt, ensure_ascii=False)).replace(
        "__REFS__", json.dumps(refs, ensure_ascii=False))
    js2 = JS_STEP2.replace("__LESSON__", json.dumps(lesson, ensure_ascii=False)).replace(
        "__TXTNAME__", json.dumps(txt_name, ensure_ascii=False)).replace(
        "__VIDEO__", json.dumps(video_url, ensure_ascii=False)).replace(
        "__TITLE__", json.dumps(title, ensure_ascii=False)).replace(
        "__KEY__", json.dumps(key, ensure_ascii=False))
    js3 = JS_STEP3.replace("__LESSON__", json.dumps(lesson, ensure_ascii=False)).replace(
        "__TXTNAME__", json.dumps(txt_name, ensure_ascii=False)).replace(
        "__B64__", json.dumps(b64))

    if "1" in steps:
        r1 = run_js("1", js1, args.task, f"st1-{slug}-{tag}", 120000)
        print("STEP1", json.dumps(r1.get("result", {}).get("value", r1), ensure_ascii=False)[:500])
        if not (r1.get("result", {}).get("value") or {}).get("hasTxt"):
            raise SystemExit("STEP1 未成功上传语音稿，终止")
    if "2" in steps:
        r2 = run_js("2", js2, args.task, f"st2-{slug}-{tag}", 150000)
        print("STEP2", json.dumps(r2.get("result", {}).get("value", r2), ensure_ascii=False)[:500])
    if "3" in steps:
        r3 = run_js("3", js3, args.task, f"st3-{slug}-{tag}", 120000)
        print("STEP3", json.dumps(r3.get("result", {}).get("value", r3), ensure_ascii=False)[:500])
    print("\n提交完成。下一步：记录会话 URL，用文件库接口轮询 PDF 产物。")


if __name__ == "__main__":
    main()
