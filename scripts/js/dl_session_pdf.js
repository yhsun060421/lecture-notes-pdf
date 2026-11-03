// Tabbit：从会话页取 PDF 附件的预签名下载 URL
// 占位符：__SESS__（sessionId）、__MATCH__（文件名关键词）
// 原理：点卡片上的「下载」按钮，用 CDP 监听 myqcloud.com 的请求
const SESS = "__SESS__";
const MATCH = "__MATCH__";

const p = await context.newPage();
const cdp = await context.newCDPSession(p);
await cdp.send("Network.enable");

let getUrl = null;
cdp.on("Network.requestWillBeSent", e => {
  if (e.request.url.includes("myqcloud.com")) getUrl = e.request.url;
});

await p.goto("https://web.tabbit.com/session/" + SESS, {waitUntil: "domcontentloaded", timeout: 30000});
await p.waitForTimeout(8000);

const pos = await p.evaluate((m) => {
  const cards = Array.from(document.querySelectorAll("div[role=button]"))
    .filter(e => /\.pdf/i.test(((e.innerText || "").trim().split("\n")[0] || "")));
  const card = cards.find(e => (e.innerText || "").includes(m)) || cards[0];
  if (!card) {
    return {none: "no-card", names: cards.map(c => (c.innerText || "").trim().slice(0, 60))};
  }
  card.scrollIntoView({block: "center"});
  const b = Array.from(card.querySelectorAll("button"))
    .find(x => ((x.getAttribute("aria-label") || "") + (x.getAttribute("title") || "")).includes("下载"));
  if (!b) return {none: "no-btn", txt: card.innerText.trim().slice(0, 80)};
  const r = b.getBoundingClientRect();
  return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
          txt: card.innerText.trim().slice(0, 80)};
}, MATCH);

if (pos && pos.x) {
  await p.mouse.click(pos.x, pos.y);
  await p.waitForTimeout(8000);
}
await cdp.detach().catch(() => {});
return {pos, getUrl};
