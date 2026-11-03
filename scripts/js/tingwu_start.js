// 听悟：点击「开始转写」
// 上传后文件只进入待转写列表，必须再点一次才真正开始
await page.getByText("开始转写", {exact: false}).first().click({timeout: 12000});

const shots = [];
for (let i = 0; i < 10; i++) {
  await page.waitForTimeout(6000);
  shots.push(page.url());
  if (/transcripts?\//.test(page.url())) break;
}

const b = await page.evaluate(() =>
  (document.body.innerText || "").replace(/\n{2,}/g, "\n").slice(0, 400));

return {
  url: page.url(),
  urls: [...new Set(shots)].slice(0, 4),
  started: /转写中|预计剩余/.test(b),
  preview: b,
};
