# -*- coding: utf-8 -*-
"""PDF 交付前体检。

用法：
    python -I check_pdf.py <pdf 路径> <报告输出路径> [--style latex|html-color|html-bw]

检查项（三条路线共用）：
- 页数、字数、空白页（单页正文字符 < 30 视为空白）
- 目录 / 例题 / 考点标注是否存在
- 语音同音错字命中（需人工确认是否在勘误对照表内）
- LaTeX 泄漏：以 # 开头的行、\\displaystyle、\\begin{、\\frac、$ 残留
- 引号配对

HTML 路线追加：
- 位图数量（应为 0，插图全部内联 SVG）
- 文字块（BT…ET）内的描边算子 S/B/b 数量（应为 0）
- 文本越出页面边界（应为 0）
- 黑白版：彩色像素占比（应为 0）
"""
import argparse
import re

import pymupdf

# 通义听悟 / faster-whisper 在数学课堂语境下的高频同音错字
BAD = [
    "举证", "转制", "内机", "项链", "对焦化", "现金代数", "向亮", "取证",
    "航列式", "转旨", "正订", "范书", "矩正", "象量", "二词型",
]

STROKE_RE = re.compile(rb"(?<![A-Za-z])(S|s|B|B\*|b|b\*)(?![A-Za-z*])")


def count_text_strokes(doc, page):
    """统计页面内容流里文字块（BT…ET）内的描边算子数量。"""
    n = 0
    for x in page.get_contents() or []:
        try:
            data = doc.xref_stream(x) or b""
        except Exception:  # noqa: BLE001
            continue
        for seg in re.findall(rb"BT(.*?)ET", data, re.S):
            n += len(STROKE_RE.findall(seg))
    return n


def color_ratio(page, dpi=60):
    """返回彩色像素占比：max(R,G,B) - min(R,G,B) > 10 视为彩色。"""
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    s = pix.samples
    total = pix.width * pix.height
    if not total:
        return 0.0
    step = 3 * max(1, total // 40000)  # 抽样，最多约 4 万像素
    colored = 0
    seen = 0
    for i in range(0, len(s) - 2, step):
        r, g, b = s[i], s[i + 1], s[i + 2]
        seen += 1
        if max(r, g, b) - min(r, g, b) > 10:
            colored += 1
    return round(colored / seen, 5) if seen else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("out")
    ap.add_argument("--style", default="latex", choices=["latex", "html-color", "html-bw"])
    args = ap.parse_args()
    path, out = args.path, args.out

    doc = pymupdf.open(path)
    texts = [p.get_text() for p in doc]
    full = "".join(texts)

    blank = [i + 1 for i, t in enumerate(texts) if len(t.strip()) < 30]
    hits = {w: full.count(w) for w in BAD if full.count(w)}
    leak = {
        "hash_line": sum(1 for ln in full.splitlines() if ln.strip().startswith("#")),
        "displaystyle": full.count("\\displaystyle"),
        "begin_cmd": full.count("\\begin{"),
        "frac": full.count("\\frac"),
        "dollar": full.count("$"),
    }

    # 逐页引号统计，便于识别跨页引用
    per_page = [(i + 1, t.count("“"), t.count("”")) for i, t in enumerate(texts)
                if t.count("“") != t.count("”")]

    lines = [
        f"file={path}",
        f"style={args.style}",
        f"pages={doc.page_count} chars={len(full)} blank={blank}",
        f"toc={'目录' in full} example={'例题' in full} exam={'考点' in full}",
        f"hits={hits or '无'}",
        f"leak={leak}",
        f"quotes=“{full.count('“')} ”{full.count('”')}",
        f"unbalanced_pages={per_page}",
    ]

    if args.style in ("html-color", "html-bw"):
        images = sum(len(p.get_images(full=True)) for p in doc)
        strokes = sum(count_text_strokes(doc, p) for p in doc)
        outside = 0
        for p in doc:
            r = p.rect
            for b in p.get_text("blocks"):
                x0, y0, x1, y1 = b[:4]
                if x0 < r.x0 - 2 or y0 < r.y0 - 2 or x1 > r.x1 + 2 or y1 > r.y1 + 2:
                    outside += 1
        lines.append(f"images={images} (应为 0，插图均为内联 SVG)")
        lines.append(f"text_strokes={strokes} (应为 0)")
        lines.append(f"text_outside_page={outside} (应为 0)")
        if args.style == "html-bw":
            ratios = [(i + 1, color_ratio(p)) for i, p in enumerate(doc)]
            worst = max(ratios, key=lambda t: t[1], default=(0, 0.0))
            colored_pages = [i for i, r in ratios if r > 0.0005]
            lines.append(f"color_ratio_max={worst} color_pages={colored_pages} (应为空)")

    lines += [
        "--- p1 ---",
        texts[0][:600] if texts else "",
        "--- p2 ---",
        texts[1][:400] if len(texts) > 1 else "",
        "--- last ---",
        texts[-1][:400] if texts else "",
    ]
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print(out)


if __name__ == "__main__":
    main()
