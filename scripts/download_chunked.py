# -*- coding: utf-8 -*-
"""分块并发下载器：8 MB 块 + 状态文件断点续传。

用法：
    python -I download_chunked.py <url> <输出文件> [并发数，默认 8]

特点：
- 文件切成 8 MB 块，每块独立 Range 请求，互不影响
- 每块成功后写入 <输出文件>.state，中断后可续传
- 只有全部块成功才打印 ALL_OK 并以 0 退出；有缺失块退出码为 2

注意：绝不能用 truncate 预分配后单线程写——那会产生"大小正确但内容全零"的假文件。
"""
import json
import os
import sys
import threading
import time
import urllib.request

CHUNK = 8 * 1024 * 1024
LOCK = threading.Lock()


def get_size(url: str) -> int:
    """先用 Range 探测总大小；服务端不支持 Range 时退回 Content-Length。"""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        cr = r.headers.get("Content-Range", "")
        if "/" in cr:
            return int(cr.split("/")[-1])
        return int(r.headers.get("Content-Length", 0))


def load_state(path: str, total: int) -> set:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                st = json.load(f)
            if st.get("total") == total:
                return set(st.get("done", []))
        except Exception:
            pass
    return set()


def save_state(path: str, total: int, done: set) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"total": total, "done": sorted(done)}, f)
    os.replace(tmp, path)


def fetch_block(url: str, path: str, s: int, e: int, log: list) -> bool:
    """下载闭区间 [s, e]，成功返回 True。最多重试 8 次。"""
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={s}-{e}"})
            with urllib.request.urlopen(req, timeout=60) as r, open(path, "r+b") as f:
                f.seek(s)
                pos = s
                while pos <= e:
                    buf = r.read(min(262144, e - pos + 1))
                    if not buf:
                        break
                    f.write(buf)
                    pos += len(buf)
            if pos > e:
                return True
            log.append(f"块 {s} 只收到 {pos - s}/{e - s + 1} 字节，重试 {attempt}")
        except Exception as ex:  # noqa: BLE001
            log.append(f"块 {s} 重试 {attempt}: {str(ex)[:80]}")
            time.sleep(2 + attempt)
    return False


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    url, out = sys.argv[1], sys.argv[2]
    nworkers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    state_path = out + ".state"

    total = get_size(url)
    if total <= 0:
        print("无法获取文件大小，检查 URL 是否有效")
        sys.exit(1)

    blocks = [(s, min(total - 1, s + CHUNK - 1)) for s in range(0, total, CHUNK)]
    done = load_state(state_path, total)

    with open(out, "ab") as f:
        f.truncate(total)

    todo = [b for i, b in enumerate(blocks) if i not in done]
    print(f"总大小 {total} 字节，块数 {len(blocks)}，已完成 {len(done)}，待下 {len(todo)}", flush=True)
    if not todo:
        print("ALL_OK")
        return

    log: list = []
    idx = 0
    ilock = threading.Lock()
    finished = [0]

    def worker() -> None:
        nonlocal idx
        while True:
            with ilock:
                if idx >= len(todo):
                    return
                k = idx
                idx += 1
            s, e = todo[k]
            bi = blocks.index((s, e))
            if fetch_block(url, out, s, e, log):
                with LOCK:
                    done.add(bi)
                    finished[0] += 1
                    if finished[0] % 10 == 0:
                        save_state(state_path, total, done)
                        print(f"进度 {finished[0]}/{len(todo)} 块", flush=True)

    ths = [threading.Thread(target=worker) for _ in range(min(nworkers, len(todo)))]
    for t in ths:
        t.start()
    for t in ths:
        t.join()

    save_state(state_path, total, done)
    miss = [i for i in range(len(blocks)) if i not in done]
    print(f"完成：成功 {len(done)}/{len(blocks)}，缺失块 {len(miss)}", flush=True)
    if miss:
        print("缺失块索引（重跑同一命令会只补这些块）：", miss[:20], flush=True)
        sys.exit(2)
    print("ALL_OK")


if __name__ == "__main__":
    main()
