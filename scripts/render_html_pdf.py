# -*- coding: utf-8 -*-
"""把 HTML 讲义打印成 A4 PDF（Playwright / Chromium）。

用法：
    python -I render_html_pdf.py <输入.html> <输出.pdf> \
        [--header "课程名 · 讲次"] [--title "当前章名"] [--bw]

做的事：
- 打开本地 HTML，等 MathJax 渲染完成（最多 30 秒）
- 用 Chromium 打印 A4，保留背景色，页眉页脚走 displayHeaderFooter
- 打印后校验页数、空白页、公式残留，并打印一行摘要

注意：目录页码不在这里回填；需要两遍法时先打 pass1，再用
scripts/check_pdf.py 的思路定位标题页码，回填 HTML 后重跑本脚本。
"""
import argparse
import asyncio
import os
import sys

import pymupdf
from playwright.async_api import async_playwright

HEADER = """
<div style="width:100%;font-size:7.6pt;color:#66707c;font-family:'Microsoft YaHei',sans-serif;
            padding:0 16mm;display:flex;justify-content:space-between;align-items:flex-end;
            border-bottom:0.5px solid #d8dde3;padding-bottom:1.6mm;margin-top:5mm;">
  <span>{left}</span><span>{right}</span>
</div>
"""

FOOTER = """
<div style="width:100%;font-size:7.6pt;color:#66707c;font-family:'Microsoft YaHei',sans-serif;
            padding:0 16mm;text-align:right;">
  第 <span class="pageNumber"></span> / <span class="totalPages"></span> 页
</div>
"""


async def render(src: str, out: str, left: str, right: str, margin: dict) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("file:///" + os.path.abspath(src).replace("\\", "/"),
                        wait_until="networkidle", timeout=60000)
        try:
            await page.wait_for_function(
                "window.MathJax && MathJax.startup && MathJax.startup.promise",
                timeout=30000)
            await page.evaluate("MathJax.startup.promise")
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"[warn] MathJax 未就绪：{exc}\n")
        await page.wait_for_timeout(600)
        await page.pdf(
            path=out, format="A4", print_background=True,
            margin=margin, prefer_css_page_size=False,
            display_header_footer=True,
            header_template=HEADER.format(left=left, right=right),
            footer_template=FOOTER,
        )
        await browser.close()


def report(path: str) -> None:
    doc = pymupdf.open(path)
    texts = [pg.get_text() for pg in doc]
    full = "".join(texts)
    blank = [i + 1 for i, t in enumerate(texts) if len(t.strip()) < 30]
    leaks = {k: full.count(k) for k in ("\\frac", "\\displaystyle", "\\begin{", "$")}
    print(f"pages={doc.page_count} chars={len(full)} blank={blank} leak={leaks}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--header", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--bw", action="store_true", help="黑白版：下边距略放宽")
    ap.add_argument("--no-header", action="store_true")
    args = ap.parse_args()

    bottom = "15mm" if args.bw else "16mm"
    side = "18mm" if args.bw else "16mm"
    margin = {"top": "18mm", "bottom": bottom, "left": side, "right": side}

    if args.no_header:
        globals()["HEADER"] = ""  # noqa: PLW0603
    asyncio.run(render(args.src, args.out, args.header, args.title, margin))
    report(args.out)


if __name__ == "__main__":
    main()
