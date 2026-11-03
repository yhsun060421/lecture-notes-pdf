// Tabbit 文件库轮询：查找某课次新生成的 PDF
// 占位符：__LESSON__（文件名关键词）、__SINCE__（ISO 时间，只认此时间之后创建的）
const LESSON = "__LESSON__";
const SINCE = "__SINCE__";

const p = await context.newPage();
await p.goto("https://web.tabbit.com/newtab", {waitUntil: "domcontentloaded", timeout: 40000});
await p.waitForTimeout(2500);

const res = await p.evaluate(async ({lesson, since}) => {
  const r = await fetch("/api/v0/tabbit-space/files?type=all&limit=36", {credentials: "include"});
  const j = await r.json();
  const items = (j.items || j.data || []).map(it => ({
    id: it.id,
    filename: it.filename,
    type: it.content_type,
    session: (it.source || {}).chat_session_id || null,
    created: it.created_at,
  }));
  const hit = items.filter(it =>
    (it.filename || "").includes(lesson) &&
    /\.pdf$/i.test(it.filename || "") &&
    (!since || (it.created || "") > since)
  );
  return {total: items.length, hit, recent: items.slice(0, 6)};
}, {lesson: LESSON, since: SINCE});

await p.close();
return res;
