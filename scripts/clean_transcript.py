# -*- coding: utf-8 -*-
"""清洗通义听悟 / whisper 语音稿：繁转简 + 碎段合并 + 数学术语同音错字修正。

用法：
    python -I clean_transcript.py <源目录> <输出目录> [--report 报告路径]

输入目录下每个 .txt 一行一句，格式任意；输出同名 .txt。
提交给 Tabbit 的是清洗后的版本。
"""
import os
import re
import sys

try:
    from opencc import OpenCC
except ImportError:  # 没装 opencc 时跳过繁转简
    OpenCC = None

# 只收录数学课堂语境下几乎不可能误判的词。发现新错字就往下加。
FIX = [
    # —— 基础代数 ——
    ("举证", "矩阵"), ("取证", "矩阵"), ("巨阵", "矩阵"), ("矩正", "矩阵"), ("矩折", "矩阵"), ("矩卷", "矩阵"),
    ("转制", "转置"), ("转旨", "转置"), ("转至", "转置"), ("短字", "转置"), ("短政", "转置"),
    ("内机", "内积"), ("内极", "内积"), ("内急", "内积"),
    ("项链", "向量"), ("象量", "向量"), ("向亮", "向量"),
    ("对焦化", "对角化"), ("对角华", "对角化"), ("增焦化", "正交化"), ("正交话", "正交化"),
    ("现金代数", "线性代数"), ("现性代数", "线性代数"), ("线形", "线性"),
    ("航列式", "行列式"), ("行里式", "行列式"), ("行乐式", "行列式"), ("行业式", "行列式"),
    ("特征直", "特征值"), ("特质值", "特征值"), ("特点值", "特征值"),
    ("半随矩阵", "伴随矩阵"), ("伴谁矩阵", "伴随矩阵"),
    ("二次行", "二次型"), ("二词型", "二次型"),
    ("可拟", "可逆"), ("克逆", "可逆"),
    ("正订", "正定"),
    ("范书", "范数"), ("泛数", "范数"),
    ("方程阻", "方程组"), ("放程组", "方程组"),
    ("初等变缓", "初等变换"), ("初调行电换", "初等行变换"), ("出版旁边换", "初等行变换"),
    ("分快", "分块"), ("崩溃组成法", "分块相乘"),
    ("施立特", "施密特"), ("室内特", "施密特"), ("施密特增加化", "施密特正交化"),
    ("主词", "主子式"), ("组员", "主元"), ("选组员", "选主元"), ("图圆", "主元"),
    ("消费", "消去"), ("消炎", "消元"), ("高丝下去", "高斯消去"), ("钢丝下去", "高斯消去"),
    ("层积", "乘积"),
    ("非歧义", "非奇异"),
    ("上代表矩阵", "上三角矩阵"),
    ("LE分解", "LU分解"), ("L一分解", "LU分解"), ("L1U1", "LU分解"),
    ("追忆矩阵", "矩阵"),
    ("销量", "向量"), ("防御数", "行列式"),
    ("证交", "正交"), ("正焦", "正交"), ("症调", "正交"),
    # —— 分解类 ——
    ("hospital变化", "householder变换"),
]


def normalize(text: str) -> str:
    if OpenCC is not None:
        text = OpenCC("t2s").convert(text)
    return text


def fix_terms(text: str) -> tuple[str, dict]:
    counts = {}
    for wrong, right in FIX:
        n = text.count(wrong)
        if n:
            text = text.replace(wrong, right)
            counts[f"{wrong}->{right}"] = n
    return text, counts


def merge_fragments(lines: list[str]) -> list[str]:
    """把被切成碎句的行合并：原文格式为 'MM:SS\\t文本'。"""
    # 分钟数允许 1–3 位：超过 100 分钟的课会出现 100:13 这种时间戳
    pat = re.compile(r"^\s*(?:\[?)(\d{1,3}):(\d{2})(?:\]?)[\s\t]+(.*)$")
    merged = []  # [(start_sec, end_sec, text)]
    for ln in lines:
        m = pat.match(ln)
        if not m:
            if merged and ln.strip():
                merged[-1] = (merged[-1][0], merged[-1][1], merged[-1][2] + ln.strip())
            continue
        sec = int(m.group(1)) * 60 + int(m.group(2))
        text = m.group(3).strip()
        if not text:
            continue
        # 开头的极短残句多为识别幻觉，丢弃；阈值不要定太狠，否则会误删正常短句
        if sec < 120 and len(text) < 8:
            continue
        if merged and sec - merged[-1][1] <= 6 and len(merged[-1][2]) + len(text) <= 110:
            merged[-1] = (merged[-1][0], sec, merged[-1][2] + text)
        else:
            merged.append((sec, sec, text))
    return [f"{s // 60:02d}:{s % 60:02d}\t{t}" for s, _, t in merged]


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    report = sys.argv[sys.argv.index("--report") + 1] if "--report" in sys.argv else os.path.join(dst, "_清洗报告.txt")
    os.makedirs(dst, exist_ok=True)

    rows = []
    for name in sorted(os.listdir(src)):
        if not name.lower().endswith(".txt"):
            continue
        raw = open(os.path.join(src, name), encoding="utf-8").read()
        text = normalize(raw)
        text = "\n".join(merge_fragments(text.splitlines()))
        text, counts = fix_terms(text)
        open(os.path.join(dst, name), "w", encoding="utf-8").write(text)
        rows.append(f"{name}\t{len(text)} 字\t" + ("; ".join(f"{k}={v}" for k, v in counts.items()) or "无需修改"))

    open(report, "w", encoding="utf-8").write("\n".join(rows))
    print(report)


if __name__ == "__main__":
    main()
