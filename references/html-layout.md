# HTML 排版规范（彩色 / 黑白 A4）

本项目的 HTML 讲义只有**一套视觉语言**：深海军蓝封面 + 金色点缀 + 五色盒子 + 衬线正文。
所有课程都必须长成同一个样子，只有黑白版把色相换成灰阶。

**实现基准是仓库里的样板文件：`assets/reference_lecture_style.html`。**
提交任务时必须把它作为「样式参考」附件随语音稿一起上传；`submit_to_tabbit.py --style html-*` 会自动带上。

---

## 一、技术栈

| 项 | 取值 |
|---|---|
| 排版 | 纯 HTML + CSS（无框架、无构建工具） |
| 公式 | MathJax 3，**TeX 输入**，CHTML 输出（`tex-chtml.js`） |
| 插图 | 内联 SVG（禁止位图、截图、外链） |
| 打印 | Chromium / Playwright `page.pdf({format:"A4", printBackground:true})` |
| 交付 | 一个 PDF，A4，彩色或纯黑白 |

三条红线：

1. 不得调用任何 LaTeX 引擎（xelatex / pdflatex / lualatex / tectonic / xdvipdfmx）。
2. 不得用 `tex-svg.js`：字形是路径，Chromium 打印会带同色发丝描边，放大后公式呈空心轮廓。
3. 不得给文字加描边（`-webkit-text-stroke`、`paint-order: stroke`、`text-shadow`）。

---

## 二、样板文件怎么用

```
assets/reference_lecture_style.html   ← 唯一版式基准（4 页：封面 / 目录 / 正文样式 / 表格插图）
```

- **上传**：提交任务 step 1 与语音稿一起上传，提示词开头会要求模型先读它的 `<style>`。
- **复用**：模型必须原样抄 CSS 变量与组件类名（`.box.thm/.board/.exam/.warn/.note`、`.tag`、`.chap`、`.table.t`、`figure`）。
- **替换**：只替换括号占位文案，版式、字号、留白、配色分毫不动。
- **自检**：成品第一眼必须与样板同款——深蓝封面、金色小标、五色盒子；否则重做。

> 样板本身就是可打印的：`python -I scripts/render_html_pdf.py assets/reference_lecture_style.html out.pdf`。

---

## 三、设计令牌（不得改值）

```css
:root{
  --navy:#0d1f33;  --navy2:#142d48;  --gold:#f0a03c;  --gold-l:#f5bf6a;
  --blue:#1a4e8a;  --blue-bg:#e9f1fa;
  --teal:#0e6673;  --teal-bg:#e6f4f5;
  --crimson:#8a1b3b; --crimson-bg:#fae9f0;
  --amber:#a75c00; --amber-bg:#fdf2e3;
  --slate:#6a798b; --slate-bg:#f4f6f9;
  --ink:#111; --mid:#3a434e; --soft:#66707c; --hair:#d8dde3;
}
```

| 令牌 | 用途 |
|---|---|
| `--navy` / `--gold` | 封面底色、章节条、强调竖条 |
| `--blue` | 定义 / 定理盒 |
| `--teal` | 板书 / 关键帧盒 |
| `--crimson` | 例题盒（最醒目） |
| `--amber` | 易错点盒 |
| `--slate` | 整理说明 / 注释盒 |

版式基线：

| 项 | 值 |
|---|---|
| 页面 | A4，`margin: 18mm 16mm 16mm 16mm` |
| 正文 | 10.4 pt / 1.74，两端对齐，衬线（Source Han Serif SC → SimSun） |
| 标题 | 黑体（Source Han Sans SC → Microsoft YaHei） |
| 封面高 | 262 mm，结束后强制分页 |
| 盒子间距 | 4 mm，`break-inside: avoid` |

---

## 四、页面骨架

### 4.1 封面 `.cover`
1. 顶部深蓝色块（左侧 3.2 mm 金色竖条）：英文小标 → 课程名 40 pt → 「第 X 次课」22 pt 金色 → 主线一行 12 pt → 细分隔线。
   - 英文小标写作 `L E C T U R E   N O T E S · 年份`；**年份按本讲课次日期填写**（如课在 2026 年就写 2026）。样板里是 `{{年份}}` 占位符，抄成固定年份是最常见的交付事故。
2. 信息表 `table.meta`：课程名称 / 课次 / 授课人 / 教材范围 / 素材来源 / 输出格式。
3. 「标注体系」框：2×2 网格，四类标签 + 释义。
4. 页脚：左侧两行来源说明，右侧讲义字样，上方 2 px 实线。

### 4.2 目录 `.toc`
- 单独成页；标题 20 pt 深蓝，下缘 2.5 px 实线。
- 一级条目：金色序号 + 点线引导 + 右对齐页码；二级缩进 11 mm、灰色小号。
- 页码必须与正文页脚一致（见第七节）。

### 4.3 章节条 `.chap`
- 深蓝通栏 + 左侧 3.2 mm 金色条；上排英文 `C H A P T E R  0 1`，下排章名 19 pt。
- **不强制分页**，自然接续；但后面至少要跟两行正文（`break-after: avoid`）。

### 4.4 标题
- `h2`：14.4 pt 深蓝、左侧 2.2 mm 金色竖条、灰色序号前缀。
- `h3`：11.8 pt、下缘 0.8 px 细线。
- 节首可加 `.lead` 导语（10.8 pt `--mid`）。

---

## 五、组件

### 5.1 盒子（五类，不得混用）

```html
<div class="box thm">
  <div class="bh"><span class="l">定 理 1.1　（定理名）</span><span class="r">定理 · 定义</span></div>
  <div class="bb">正文</div>
</div>
```

| 类 | 用途 | 标题栏 | 底色 | 右侧标签 |
|---|---|---|---|---|
| `.thm` | 定义、定理、性质 | 蓝底白字 | `--blue-bg` | 定理 · 定义 |
| `.board` | 板书、关键帧 | 青底白字 | `--teal-bg` | 板书 · 关键帧 |
| `.exam` | 例题 + 解答 | 绛红底白字 | `--crimson-bg` | 例题 · 课堂 |
| `.warn` | 易错点、反例 | 赭底白字 | `--amber-bg` | 重点 |
| `.note` | 整理说明、来源核对 | 灰蓝底白字 | `--slate-bg` | 整理说明 |

- 标题栏实色通栏，左侧 3 mm 白色半透明竖条；正文区浅底 + 0.8 px 主色边框。
- 例题的「题目 / 解 / 方法小结」放在同一个 `.exam` 内，不拆盒。

### 5.2 标签 `.tag`
- 7.8 pt，白底细边；变体 `.navy`（深蓝实底）、`.gold`（金底深字）、`.crimson`（绛红实底）、`.blue`。
- 语义固定：课堂讲授 → navy；重点 → gold；可能考 → crimson；定理定义 → blue。

### 5.3 引语 `.quote` 与时间戳 `.ts`
- 引语：左侧 3 px 金色竖线 + `#fffaef` 底；时间戳 8.4 pt `--blue`，固定格式 `[录音 mm:ss]` / `[画面 mm:ss]`。

### 5.4 表格 `table.t`
- 表头深蓝白字；隔行 `#f7f9fb`；只留 0.6 px 横线，无竖线；表题在表上方。

### 5.5 插图 `figure`
- 内联 SVG，`max-width:100%`，居中；图注在下 `图 X-Y 说明`。
- 顶点白填充 + 1.8 px 深蓝描边；有向边必须箭头；语义配色：主结构蓝、已选金、候选青、辅助灰。
- **标签不得压线、压顶点**；密度大就移到空白象限加引线。
- 图的数据必须与正文完全一致。

---

## 六、公式

```html
<script>
window.MathJax = {
  tex: { inlineMath: [['\\(','\\)']], displayMath: [['\\[','\\]']], processEscapes: true, tags: 'none' },
  chtml: { scale: 1.0, mtextInheritFont: true },
  options: { enableMenu: false }
};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" id="MathJax-script" async></script>
```

- 行内 `\(x\)`，行间 `\[ ... \]`；**所有数学符号都写 TeX**，不用半角字符拼凑。
- 打印前必须 `await page.evaluate(() => MathJax.startup.promise)`。
- 沙箱无外网时把 `tex-chtml.js` 与字体一起放进工作目录，改用相对路径。

---

## 七、目录页码：两遍法

Chromium 不支持 `target-counter`，也没有 `page-counter` 可用，按下面做：

1. 第一遍打印，目录页码写占位（如 `00`）。
2. 用 `pymupdf` 逐页 `search_for(标题文本)`，取首次出现的页码。
3. 回填目录，第二遍打印。
4. 抽查前 5 条与页脚「第 X / Y 页」是否一致。

```python
import pymupdf
doc = pymupdf.open("pass1.pdf")
pages = {}
for i, page in enumerate(doc):
    for h in headings:                      # headings 是 (锚点, 文本) 列表
        if h not in pages and page.search_for(h):
            pages[h] = i + 1
```

> 用 `offsetTop` 估算会在有封面色块、强制分页时错位，只作第一遍的粗排。

---

## 八、黑白版

同一套骨架，只把色相压成灰阶，**不新增任何组件**：

| 彩色 | 黑白 |
|---|---|
| `--navy #0d1f33` | `#1a1a1a` |
| `--gold #f0a03c` | `#000`（只作竖条） |
| `--blue #1a4e8a` / `#e9f1fa` | `#3a3a3a` / `#ededed` |
| `--teal #0e6673` / `#e6f4f5` | `#4a4a4a` / `#f1f1f1` |
| `--crimson #8a1b3b` / `#fae9f0` | `#222` / `#ececec` |
| `--amber #a75c00` / `#fdf2e3` | `#5a5a5a` / `#f3f3f3` |
| `--slate #6a798b` / `#f4f6f9` | `#6e6e6e` / `#f5f5f5` |

- 盒型改由**边框样式**区分：定理实线、板书左缘粗竖条、例题最粗、易错虚线、注释点线。
- 页边距放宽到 `18mm 18mm 15mm 18mm`，避免大黑块压边。
- 验收：任意页 `max(R,G,B) − min(R,G,B) > 10` 的像素占比必须为 0。

---

## 九、打印

```js
await page.waitForFunction(() => window.MathJax && MathJax.startup && MathJax.startup.promise);
await page.evaluate(() => MathJax.startup.promise);
await page.pdf({
  path: "out.pdf", format: "A4", printBackground: true,
  margin: {top: "18mm", bottom: "16mm", left: "16mm", right: "16mm"},
  displayHeaderFooter: true, headerTemplate, footerTemplate,
  preferCSSPageSize: false
});
```

页眉模板：左「课程名 · 讲次」，右章名，下缘 0.6 pt 细线；页脚：右「第 X / Y 页」。
无 Playwright 时用 `chromium --headless=new --no-sandbox --print-to-pdf=out.pdf --no-pdf-header-footer file:///...`，页码打印后补。

---

## 十、验收表（`check_pdf.py --style html-color|html-bw`）

| 项 | 合格值 |
|---|---|
| 空白页 | 无（单页文本 < 30 字视为空白） |
| LaTeX 泄漏 | `\(` `\[` `\frac` `\displaystyle` `$` 全为 0 |
| 位图 | `images=0`（插图必须内联 SVG） |
| 文字描边 | `text_strokes=0` |
| 横向溢出 | `text_outside_page=0` |
| 黑白版彩色 | `color_pages=[]` |
| 目录页码 | 抽查前 5 条与页脚一致 |
| 例题 | 数量与讲稿一致，标注「课堂讲授 / 讲义例题」 |
| 时间戳 | `[录音]` ≥ 15 处，`[画面]` 覆盖每块板书 |

---

## 十一、常见事故

| 症状 | 根因 | 处置 |
|---|---|---|
| 底纹全白 | 没开 `printBackground` 或没写 `print-color-adjust: exact` | 两者都补上 |
| 公式空白 / 仍是 `\[...\]` | 没等 MathJax 渲染完，或行间写成了 `$...$` | 等 `startup.promise`；行间改 `\[...\]` |
| 公式空心、毛边 | 用了 `tex-svg.js`，或加了文字描边 | 换 CHTML，删 `text-stroke` / `text-shadow` |
| 每页重复页眉且错位 | 用 `position: fixed` 做页眉 | 改用 Playwright `headerTemplate` |
| 目录页码全错 | `offsetTop` 估算，遇封面/分页错位 | 改两遍法 + pymupdf 搜标题 |
| 黑白版有彩色 | 残留彩色变量、彩色 emoji、彩色 SVG | 跑 `--style html-bw` 看 `color_pages` |
| 内容被裁 / 右侧溢出 | `overflow:hidden`、固定高度、长公式不换行 | 删掉限制；长公式用 `aligned` 换行 |
| 章节标题孤零零留在页底 | 章节条后没有跟正文 | `.chap { break-after: avoid }` |

---

## 十二、落版自检（交付前逐条打勾）

- [ ] 与 `reference_lecture_style.html` 同款：深蓝封面 + 金色小标 + 五色盒子
- [ ] 封面小标的年份是本讲实际年份，不是样板里的占位年份
- [ ] 页数、例题、时间戳三项与讲稿对得上
- [ ] 所有公式是 MathJax TeX，PDF 里搜不到 `\frac`
- [ ] 插图全内联 SVG，数据与正文一致
- [ ] 目录页码与页脚一致
- [ ] `check_pdf.py` 全绿
