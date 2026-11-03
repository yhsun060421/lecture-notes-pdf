# -*- coding: utf-8 -*-
"""PDF 交付前体检。

用法：
    python -I check_pdf.py <pdf 路径> <报告输出路径>

检查项：
- 页数、字数、空白页（单页正文字符 < 30 视为空白）
- 目录 / 例题 / 考点标注是否存在
- 语音同音错字命中（需人工确认是否在勘误对照表内）
- LaTeX 泄漏：以 # 开头的行、\\displaystyle、\\begin{、\\frac、$ 残留
- 引号配对
"""
import sys

import pymupdf

# 通义听悟 / faster-whisper 在数学课堂语境下的高频同音错字
BAD = [
    "举证", "转制", "内机", "项链", "对焦化", "现金代数", "向亮", "取证",
    "航列式", "转旨", "正订", "范书", "矩正", "象量", "二词型",
]


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    path, out = sys.argv[1], sys.argv[2]

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
        f"pages={doc.page_count} chars={len(full)} blank={blank}",
        f"toc={'目录' in full} example={'例题' in full} exam={'考点' in full}",
        f"hits={hits or '无'}",
        f"leak={leak}",
        f"quotes=“{full.count('“')} ”{full.count('”')}",
        f"unbalanced_pages={per_page}",
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
