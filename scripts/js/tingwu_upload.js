// 听悟：上传本地音视频
// 占位符由调用方替换：__FILE__（Windows 绝对路径，JSON 字符串形式）
// 说明：必须点三层才触发隐藏的 input[type=file]
const FILE = __FILE__;

await page.getByText("上传音视频", {exact: true}).first().click({timeout: 12000}).catch(() => {});
await page.waitForTimeout(2000);
await page.getByText("上传本地音视频文件", {exact: false}).first().click({timeout: 12000}).catch(() => {});
await page.waitForTimeout(2000);

const fcWait = page.waitForEvent("filechooser", {timeout: 20000}).catch(() => null);
await page.getByText("点击 / 拖拽", {exact: false}).first().click({timeout: 10000}).catch(() => {});
const fc = await fcWait;
let set = false;
if (fc) {
  await fc.setFiles(FILE);
  set = true;
}
await page.waitForTimeout(6000);

const after = await page.evaluate(() => ({
  url: location.href,
  modals: [...document.querySelectorAll(".ant-modal, [class*=modal]")]
    .map(e => (e.innerText || "").replace(/\s+/g, " ").slice(0, 200)).filter(Boolean),
  toast: [...document.querySelectorAll("[class*=message], [class*=notification], [class*=toast]")]
    .map(e => (e.innerText || "").trim()).filter(Boolean).slice(0, 5),
  progress: [...document.querySelectorAll("[class*=progress]")]
    .map(e => (e.innerText || "").trim()).filter(Boolean).slice(0, 5),
}));

return {set, after};
