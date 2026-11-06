# HTML 排版 → A4 打印 PDF

> 本文件是「彩色 HTML」「黑白 HTML」两条排版路线的技术规范。LaTeX 路线见 `scripts/prompt_latex.txt`。

---

## 一、三条排版路线怎么选

| 路线 | 提示词 | 产物 | 适用场景 |
|---|---|---|---|
| LaTeX | `scripts/prompt_latex.txt` | `xelatex` 编译出的 A4 PDF | 公式极多、需要严格分页与交叉引用；环境里 LaTeX 可用 |
| 彩色 HTML | `scripts/prompt_html_color.txt` | Chromium 打印的 A4 彩色 PDF | 屏幕上阅读、彩色标注体系（四色标签）、插图多 |
| 黑白 HTML | `scripts/prompt_html_bw.txt` | Chromium 打印的 A4 黑白 PDF | 要打印、要省墨、黑白激光打印机；不依赖颜色传达信息 |

三条路线的**内容要求完全一致**（三线还原、全量读稿、`[录音 mm:ss]` ≥ 15、`[画面 mm:ss]` 覆盖板书、例题标注、术语纠错、只交付一个 PDF）。差别只在排版实现。

---

## 二、A4 打印的三个前提

1. **HTML 不是交付物，PDF 才是。** 模型必须在沙箱里把 HTML 用无头 Chromium 打成 PDF，只把 PDF 作为附件交出来。
2. **打印参数必须显式给全**：纸张 A4、四边页边距、`printBackground: true`、页眉页脚模板。缺 `printBackground` 会让所有底纹/色块消失。
3. **打印前必须等 MathJax 渲染完成**，否则公式位置是空白或原始 `\(...\)` 文本。

### 2.1 Playwright 打印（首选）

```js
await page.waitForFunction(() => window.MathJax && MathJax.startup && MathJax.startup.promise);
await page.evaluate(() => MathJax.startup.promise);
await page.pdf({
  path: "out.pdf",
  format: "A4",
  printBackground: true,
  margin: { top: "17mm", bottom: "13mm", left: "15mm", right: "15mm" },
  displayHeaderFooter: true,
  headerTemplate: headerHTML,
  footerTemplate: footerHTML,
  preferCSSPageSize: false
});
```

彩色版边距 `17/13/15/15`，黑白版 `18/15/18/18`（黑白版留白略大，便于装订）。

### 2.2 Chromium 命令行（沙箱没有 Playwright 时）

```bash
chromium --headless=new --no-sandbox --disable-gpu \
  --print-to-pdf=out.pdf --no-pdf-header-footer \
  "file:///abs/path.html"
```

此时页眉页脚只能靠 CSS：

```css
@page { size: A4; margin: 17mm 15mm 13mm 15mm; }
```

页码用 CSS `@page` 的 `counter(page)` 在部分 Chromium 版本可用；不稳定时改为**在 HTML 里手工分页并写死页码**，或在打印后用 `pymupdf` 加页码。交付前必须抽查页码。

---

## 三、CSS 骨架

```css
:root{
  --ink:#1f2937; --muted:#64748b; --rule:#e5e7eb;
  --navy:#0f2743;
  --blue:#1d4ed8;  --blue-bg:#eff6ff;   --blue-line:#bfdbfe;
  --green:#047857; --green-bg:#ecfdf5;  --green-line:#a7f3d0;
  --red:#b91c1c;   --red-bg:#fef2f2;    --red-line:#fecaca;
  --amber:#b45309; --amber-bg:#fffbeb;  --amber-line:#fde68a;
  --purple:#6d28d9;--purple-bg:#f5f3ff; --purple-line:#ddd6fe;
}
*{ box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body{ margin:0; color:var(--ink); font-size:10.5pt; line-height:1.75;
      font-family:"Source Han Sans SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;
      text-align:justify; }
p{ orphans:2; widows:2; margin:0 0 6pt; }
h2,h3{ break-after:avoid; page-break-after:avoid; }
.box, table, figure{ break-inside:avoid; page-break-inside:avoid; }
```

要点：

- `print-color-adjust: exact` 必须给到所有元素（`*`），否则彩色底纹会被浏览器自动去掉。
- 不要用 `position: fixed` 做页眉页脚——分页后每页只会出现一次或错位；用 Playwright 的 `headerTemplate` / `footerTemplate`。
- 不要给 `body` 设固定高度或 `overflow: hidden`，否则内容会被裁掉且不报错。

---

## 四、公式：MathJax 3 + CHTML

```html
<script>
MathJax = {
  tex: { inlineMath: [['\\(','\\)']], displayMath: [['\\[','\\]']] },
  chtml: { scale: 1.0, displayAlign: 'left' },
  options: { enableMenu: false }
};
</script>
<script id="MathJax-script" async
        src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
```

必须遵守：

1. **只准 `tex-chtml.js`**，不准 `tex-svg.js`。SVG 输出把字形变成路径，Chromium 打印时会加同色发丝描边，400 dpi 下呈空心轮廓。
2. 打印前 `await MathJax.startup.promise`，并再等一帧（`requestAnimationFrame`）。
3. 行间公式 `\[ ... \]`，不要用 `$$...$$`（MathJax 3 默认不认）。
4. 公式容器加 `break-inside: avoid`，避免一个公式被分页切成两半。
5. 长公式用 `\begin{aligned}` 主动换行，不要让浏览器横向溢出。

---

## 五、字体

| 用途 | 字体栈 |
|---|---|
| 正文（彩色版） | `"Source Han Serif SC","Noto Serif CJK SC","Microsoft YaHei"` |
| 正文（黑白版） | `"Source Han Serif SC","Noto Serif CJK SC","SimSun"` |
| 标题 | `"Source Han Sans SC","Noto Sans CJK SC","Microsoft YaHei"` |
| 公式 | MathJax 自带 Web 字体（CHTML 输出为真实字体） |

- 沙箱里没有中文字体时先 `fc-list :lang=zh` 查，再从系统字体里选可用的；不得让中文变成方框。
- 打印前确认 `pdffonts` 里中文字体是内嵌的（`emb = yes`）。

---

## 六、版面组件

### 6.1 封面
深色（彩色版深蓝 / 黑白版纯黑）色块 + 课程名 + 讲次 + 一句话梗概 + 信息表 + 速览 + 标注体系说明 + 目录。色块高度约 65–70 mm，占满页宽。

### 6.2 章节标题
`序号徽章` + `标题` + `右侧 pill`。左侧 4–5 px 竖条。**禁止 `page-break-before: always`**，章节连续排版。

### 6.3 内容盒子
一类一个固定样式，全篇不得混用：

| 盒子 | 彩色版 | 黑白版 |
|---|---|---|
| 定义 | 蓝底 + 4px 蓝左边框 | 白底 + 1.5px 黑框 + 左侧 6px 黑条 |
| 定理 | 绿底 + 4px 绿左边框 | 浅灰底 + 3px 双线黑框 |
| 方法小结 | 琥珀底 + 4px 琥珀左边框 | 中灰底 + 1.5px 虚线框 |
| 易错点 | 红底 + 4px 红左边框 | 深灰底 + 2px 黑框 + 左上角黑三角 |
| 考点提示 | 紫底 + 4px 紫左边框 | 浅灰底 + 2px 黑框 + 右侧 6px 黑条 |
| 老师原话 | 青底 + 4px 青左边框 | 白底 + 左侧点线 + 斜体 |
| 例题 | 白底 + 1px 深蓝全框 | 白底 + 1px 黑全框 |

统一圆角 3–4 px、内边距 8 mm 6 mm、`break-inside: avoid`。

### 6.4 标注标签
- 彩色版：胶囊 + 白字 + 四色（蓝课堂讲授 / 绿定理定义 / 红重点 / 紫可能考）。
- 黑白版：白底黑边胶囊 + **符号**（● 课堂讲授 / ▲ 定理定义 / ■ 重点 / ◆ 可能考），不能只靠灰度。

### 6.5 表格
彩色版深蓝表头白字；黑白版纯黑表头白字。隔行浅灰。只画横线不画竖线。

### 6.6 插图
全部内联 SVG，禁止位图。彩色的按组配色；黑白的用黑线 + 灰度填充 + 斜线纹理。每图必须带图注。

---

## 七、目录页码：两遍法

Chromium 不支持 `target-counter`，只能手工算：

```js
// 第一遍：页码留空打印，或在浏览器里量
const PAGE_H = 297 - 17 - 13;          // mm，黑白版换成 297 - 18 - 15
const heads = [...document.querySelectorAll("h2")];
const rows = heads.map(h => ({
  title: h.innerText.trim(),
  page: Math.floor(h.getBoundingClientRect().top / (PAGE_H * 3.7795)) + 1
}));
// 回填目录 -> 第二遍打印
```

注意：

- 上述按 `offsetTop` 的粗算只适用于**单栏、无浮层**的线性文档；有封面色块、分页符时要按实际分页边界累加。
- 最稳的做法是第一遍打印后，用 `pymupdf` 逐页找标题文本，得到**真实页码**，再回填第二遍。
- 交付前抽查目录前 5 条与页脚页码，必须一致。

---

## 八、打印后质检（HTML 路线专用）

| 检查 | 方法 | 合格 |
|---|---|---|
| 页数与空白页 | `pymupdf` 逐页取文本，`len(strip) < 30` 视为空白 | 无空白页 |
| 位图 | `page.get_images()` | 全部页面 0 张位图（插图都是 SVG） |
| 字体 | `pdffonts` | 中文与公式字体全部内嵌，无 Type3 |
| 文字描边 | 解压内容流，统计 `BT…ET` 内的 `S` / `B` 操作符 | 0 |
| 公式缺失 | 逐页搜索 `\(` `\[` 原文残留 | 0 |
| 内容溢出 | 文本块 bbox 与页面边距比较 | 无越界 |
| 黑白纯度（黑白版） | 每页渲染 RGB，统计 `max(R,G,B)-min(R,G,B) > 10` 的像素 | 0 |
| 目录页码 | 目录条目 vs 页脚 | 一致 |

`scripts/check_pdf.py --style html-color|html-bw` 已内置前六项与黑白纯度检查。

---

## 九、黑白版专章

黑白版不是「把彩色版去色」，而是重新设计：

1. **信息层级不能依赖颜色**：用线型（实线/双线/虚线/点线）、灰度（黑/深灰/中灰/浅灰/白）、符号（●▲■◆）三者组合。
2. **灰度只留 4–5 档**，打印后相邻档位要能分辨；浅底不要低于 `#ebebeb`。
3. **封面用纯黑块**，不要深灰（深灰打印发脏）。
4. **公式保持纯黑**，不要加灰底。
5. **SVG 填充只用灰度或斜线纹理**，禁止彩色。
6. 交付前必须做灰度实测（见上表最后一项）。

---

## 十、常见事故

| 症状 | 原因 | 处置 |
|---|---|---|
| PDF 里底纹全白 | 没开 `printBackground` 或没写 `print-color-adjust: exact` | 补参数，重打 |
| 公式位置空白 | 没等 `MathJax.startup.promise` | 等待后重打 |
| 公式放大后是空心轮廓 | 用了 `tex-svg.js` 或给文字加了描边 | 换 CHTML，删 `-webkit-text-stroke` |
| 每页页眉重复错位 | 用 `position: fixed` 做页眉 | 改用 Playwright headerTemplate |
| 目录页码全错 | 用了 `offsetTop` 粗算但文档有分页符 | 第一遍打印后用 pymupdf 回填 |
| 内容被裁掉 | `body` 设了 `overflow: hidden` 或固定高度 | 删掉 |
| 黑白版打印发灰、层次糊 | 灰度档位太密 | 减到 4 档，加深对比 |
| 中文变方框 | 字体栈里的字体沙箱没有 | `fc-list :lang=zh` 后换字体 |
