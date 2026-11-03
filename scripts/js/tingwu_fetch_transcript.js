// 听悟：取回带时间戳的完整转写文本
// 占位符：__TRANS_ID__
// 原理：转写页是虚拟列表，innerText 只有几千字；必须调接口
//   POST /api/trans/getTransResult?c=web  body {"transId":"..."}
// 返回的 data.result 是 JSON 字符串，要再 parse 一次
const TRANS = "__TRANS_ID__";

const p = await context.newPage();
await p.goto("https://tingwu.aliyun.com/doc/transcripts/" + TRANS, {waitUntil: "domcontentloaded", timeout: 45000});
await p.waitForTimeout(7000);

const res = await p.evaluate(async (transId) => {
  const r = await fetch("/api/trans/getTransResult?c=web", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({transId}),
    credentials: "include",
  });
  const j = await r.json();
  if (!j || !j.data || !j.data.result) {
    return {err: "no-result", raw: JSON.stringify(j).slice(0, 300)};
  }
  const root = JSON.parse(j.data.result);
  const pgs = root.pg || [];
  const fmt = ms => {
    const s = Math.floor(ms / 1000), m = Math.floor(s / 60), q = s % 60;
    return String(m).padStart(2, "0") + ":" + String(q).padStart(2, "0");
  };
  const out = [];
  for (const g of pgs) {
    let sc = g.sc;
    if (typeof sc === "string") { try { sc = JSON.parse(sc); } catch (e) { sc = []; } }
    if (!Array.isArray(sc) || !sc.length) continue;
    const text = sc.map(x => x.tc || "").join("").trim();
    if (!text) continue;
    out.push(fmt(sc[0].bt || 0) + "\t" + text);
  }
  return {
    nLines: out.length,
    chars: out.join("").length,
    duration: j.data.duration,
    wordCount: j.data.wordCount,
    text: out.join("\n"),
  };
}, TRANS);

await p.close();
return res;
