# -*- coding: utf-8 -*-
"""从 Tabbit 会话页取回 PDF 附件并做基础校验。

用法：
    python -I fetch_pdf.py <sessionId> <匹配关键词> <输出pdf路径> [--task 任务名]

原理：打开会话页 -> 找到标题含关键词的 PDF 卡片 -> 点击卡片上的「下载」
      -> 用 CDP 监听 Network.requestWillBeSent 抓 myqcloud.com 的预签名 URL
      -> curl 下载 -> pymupdf 读页数与字数

注意：直接拿文件库 file_id 调 presigned-download-url 会返回 file.notFound，
      必须走会话页点击这条路。
"""
import json
import os
import re
import subprocess
import sys
import time

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "js", "dl_session_pdf.js")
CLI = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tabbit", "LocalAgent", "bin", "tabbit-cli.exe")


def run_js(code: str, task: str, rid: str, timeout_ms: int = 150000) -> str:
    tmp_js = os.path.join(HERE, "_tmp_fetch.js")
    with open(tmp_js, "w", encoding="utf-8") as f:
        f.write(code)
    proc = subprocess.run(
        [CLI, "nodejs", "--task", task, "--request-id", rid, "--timeout-ms", str(timeout_ms)],
        stdin=open(tmp_js, "rb"), capture_output=True,
    )
    return proc.stdout.decode("utf-8", "replace")


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    sess, match, out_pdf = sys.argv[1], sys.argv[2], sys.argv[3]
    task = "TabbitAuto"
    if "--task" in sys.argv:
        task = sys.argv[sys.argv.index("--task") + 1]

    code = open(JS, encoding="utf-8").read().replace("__SESS__", sess).replace("__MATCH__", match)
    raw = run_js(code, task, "fetch-" + time.strftime("%H%M%S"))

    m = re.search(r'\{"result".*', raw, re.S)
    if not m:
        print(json.dumps({"stage": "js", "err": raw[-300:]}, ensure_ascii=False))
        return
    j = json.loads(m.group(0).strip().splitlines()[0])
    val = j.get("result", {}).get("value", {})
    url = val.get("getUrl")
    if not url:
        print(json.dumps({"stage": "no-url", "pos": val.get("pos")}, ensure_ascii=False))
        return

    subprocess.run(
        ["curl.exe", "-L", "--retry", "3", "--retry-all-errors", "-o", out_pdf, url],
        capture_output=True,
    )

    info = {"size": os.path.getsize(out_pdf) if os.path.exists(out_pdf) else 0}
    if info["size"] > 10000:
        try:
            doc = pymupdf.open(out_pdf)
            text = "".join(p.get_text() for p in doc)
            info.update({
                "pages": doc.page_count,
                "chars": len(text),
                "left_quote": text.count("“"),
                "right_quote": text.count("”"),
            })
            doc.close()
        except Exception as exc:  # noqa: BLE001
            info["pdf_error"] = str(exc)[:120]
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
