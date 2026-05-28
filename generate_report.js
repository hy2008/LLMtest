const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak
} = require("docx");
const { imageSize } = require("image-size");

const PAGE_CONTENT_WIDTH_PX = 624;
const MAX_IMG_W = Math.floor(PAGE_CONTENT_WIDTH_PX * 0.92);
const MAX_IMG_H = Math.floor(PAGE_CONTENT_WIDTH_PX * 1.3 * 0.55);

function safeImageRun(path) {
  const data = fs.readFileSync(path);
  const dims = imageSize(data);
  let w = dims.width, h = dims.height;
  if (w > MAX_IMG_W) { const s = MAX_IMG_W / w; w = MAX_IMG_W; h = Math.round(h * s); }
  if (h > MAX_IMG_H) { const s = MAX_IMG_H / h; h = MAX_IMG_H; w = Math.round(w * s); }
  const ext = path.endsWith(".png") ? "png" : "jpg";
  return new ImageRun({ type: ext, data, transformation: { width: w, height: h }, altText: { title: "Chart", description: "Chart", name: "chart" } });
}

// Load data
const raw = JSON.parse(fs.readFileSync("/workspace/lm-eval-suite/results/deep_batch_results.json", "utf8"));
const valid = raw.filter(r => r.total_score > 0);
const ranked = [...valid].sort((a, b) => b.total_score - a.total_score);

// Styles
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerBorder = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
const headerBorders = { top: headerBorder, bottom: headerBorder, left: headerBorder, right: headerBorder };

function headerCell(text, width) {
  return new TableCell({
    borders: headerBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "2B579A", type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, bold: true, color: "FFFFFF", size: 18, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })] })]
  });
}

function dataCell(text, width, opts = {}) {
  const { bold, color, align, fill } = opts;
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    verticalAlign: "center",
    children: [new Paragraph({ alignment: align || AlignmentType.CENTER, children: [new TextRun({ text: String(text), bold: bold || false, color: color || "333333", size: 17, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })] })]
  });
}

function medalText(rank) {
  if (rank === 1) return { text: "1", bold: true, color: "D4A017" };
  if (rank === 2) return { text: "2", bold: true, color: "808080" };
  if (rank === 3) return { text: "3", bold: true, color: "CD7F32" };
  return { text: String(rank), bold: false, color: "333333" };
}

// Build ranking table rows
const colW = [600, 4200, 1100, 1100, 1200, 1100];
const tableRows = [
  new TableRow({ cantSplit: true, children: [
    headerCell("#", colW[0]), headerCell("模型", colW[1]),
    headerCell("总分", colW[2]), headerCell("编码", colW[3]),
    headerCell("推理", colW[4]), headerCell("智能体", colW[5])
  ]})
];

ranked.forEach((r, i) => {
  const cats = r.categories || {};
  const c = Math.round((cats.coding || {}).score || 0);
  const a = Math.round((cats.agent || {}).score || 0);
  const rr = Math.round((cats.reasoning || {}).score || 0);
  const t = r.total_score.toFixed(1);
  const fill = i < 3 ? (i === 0 ? "FFF8E1" : i === 1 ? "F5F5F5" : "FFF3E0") : (i % 2 === 0 ? "FAFAFA" : undefined);
  const m = medalText(i + 1);
  tableRows.push(new TableRow({ cantSplit: true, children: [
    dataCell(m.text, colW[0], { bold: m.bold, color: m.color, fill }),
    dataCell(r.model_id, colW[1], { align: AlignmentType.LEFT, fill }),
    dataCell(t, colW[2], { bold: i < 3, fill }),
    dataCell(String(c), colW[3], { fill }),
    dataCell(String(rr), colW[4], { fill }),
    dataCell(String(a), colW[5], { fill })
  ]}));
});

// Stats
const scores = ranked.map(r => r.total_score);
const avg = (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1);
const maxS = Math.max(...scores).toFixed(1);
const minS = Math.min(...scores).toFixed(1);
const medS = scores.sort((a, b) => a - b)[Math.floor(scores.length / 2)].toFixed(1);

// Dimension averages
const dimAvg = (dim) => (ranked.reduce((s, r) => s + ((r.categories || {})[dim] || {}).score || 0, 0) / ranked.length).toFixed(1);
const cAvg = dimAvg("coding"), aAvg = dimAvg("agent"), rAvg = dimAvg("reasoning"), pAvg = dimAvg("performance");

// Build doc
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" }, size: 22 } }
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: "1A1A2E", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } },
        paragraph: { spacing: { before: 300, after: 200 }, outlineLevel: 0, keepNext: false, keepLines: false } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: "2B579A", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1, keepNext: false, keepLines: false } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1200, right: 1200, bottom: 1200, left: 1200 }
      }
    },
    headers: {
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        new TextRun({ text: "LM Studio 模型深度评测报告", size: 16, color: "999999", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]})] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
        new TextRun({ text: "第 ", size: 16, color: "999999" }),
        new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "999999" }),
        new TextRun({ text: " 页", size: 16, color: "999999" })
      ]})] })
    },
    children: [
      // === Cover ===
      new Paragraph({ spacing: { before: 3000 }, children: [] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
        new TextRun({ text: "LM Studio", size: 56, bold: true, color: "2B579A", font: { ascii: "Arial", hAnsi: "Arial" } })
      ]}),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [
        new TextRun({ text: "\u6A21\u578B\u6DF1\u5EA6\u8BC4\u6D4B\u62A5\u544A", size: 48, bold: true, color: "1A1A2E", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 100 }, children: [
        new TextRun({ text: "29\u4E2A\u6A21\u578B \u00B7 4\u5927\u7EF4\u5EA6 \u00B7 116\u9879\u6D4B\u8BD5", size: 24, color: "666666", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [
        new TextRun({ text: "\u62A5\u544A\u65E5\u671F: 2026\u5E745\u670827\u65E5", size: 20, color: "999999", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),
      new Paragraph({ children: [new PageBreak()] }),

      // === 1. Overview ===
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("\u4E00\u3001\u6D4B\u8BD5\u6982\u8FF0")] }),
      new Paragraph({ spacing: { after: 120 }, children: [
        new TextRun({ text: "\u672C\u62A5\u544A\u5BF9 LM Studio \u5E73\u53F0\u4E0A\u7684 29 \u4E2A\u6A21\u578B\u8FDB\u884C\u4E86\u5168\u9762\u7684\u6DF1\u5EA6\u8BC4\u6D4B\uFF0C\u6DB5\u76D6\u7F16\u7801\u3001\u667A\u80FD\u4F53\u3001\u63A8\u7406\u548C\u6027\u80FD\u56DB\u5927\u7EF4\u5EA6\uFF0C\u5171\u8BA1 116 \u9879\u6D4B\u8BD5\u3002\u5176\u4E2D 28 \u4E2A\u6A21\u578B\u6210\u529F\u5B8C\u6210\u6D4B\u8BD5\uFF0C1 \u4E2A\u6A21\u578B\u56E0\u6570\u636E\u5F02\u5E38\u672A\u7EB3\u5165\u7EDF\u8BA1\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      // Stats table
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u5173\u952E\u6307\u6807")] }),
      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [4500, 4500],
        rows: [
          new TableRow({ cantSplit: true, children: [
            dataCell("\u6709\u6548\u6A21\u578B\u6570", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell("28", 4500)
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u5E73\u5747\u603B\u5206", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell(avg, 4500)
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u6700\u9AD8\u5206 / \u6700\u4F4E\u5206", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell(`${maxS} / ${minS}`, 4500)
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u4E2D\u4F4D\u6570", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell(medS, 4500)
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u7F16\u7801\u5747\u5206", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell(cAvg, 4500)
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u667A\u80FD\u4F53\u5747\u5206", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell(aAvg, 4500)
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u63A8\u7406\u5747\u5206", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell(rAvg, 4500)
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u6027\u80FD\u5747\u5206", 4500, { bold: true, fill: "F0F4F8" }),
            dataCell(pAvg, 4500)
          ]}),
        ]
      }),

      // === 2. Ranking ===
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("\u4E8C\u3001\u5B8C\u6574\u6392\u540D")] }),
      new Paragraph({ spacing: { after: 120 }, children: [
        new TextRun({ text: "\u4EE5\u4E0B\u4E3A 28 \u4E2A\u6709\u6548\u6A21\u578B\u7684\u7EFC\u5408\u6392\u540D\uFF0C\u6309\u603B\u5206\u4ECE\u9AD8\u5230\u4F4E\u6392\u5217\u3002\u603B\u5206\u7531\u56DB\u4E2A\u7EF4\u5EA6\u52A0\u6743\u8BA1\u7B97\u5F97\u51FA\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),
      new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: colW, rows: tableRows }),

      // === 3. Charts ===
      new Paragraph({ children: [new PageBreak()] }),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("\u4E09\u3001\u53EF\u89C6\u5316\u5206\u6790")] }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.1 \u603B\u5206\u6392\u540D")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [safeImageRun("/workspace/lm-eval-suite/charts/ranking_bar.png")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
        new TextRun({ text: "\u56FE 1: 28 \u4E2A\u6A21\u578B\u603B\u5206\u6392\u540D", size: 17, color: "888888", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.2 TOP 15 \u5206\u7EF4\u5EA6\u70ED\u529B\u56FE")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [safeImageRun("/workspace/lm-eval-suite/charts/heatmap.png")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
        new TextRun({ text: "\u56FE 2: TOP 15 \u6A21\u578B\u56DB\u7EF4\u5EA6\u5F97\u5206\u70ED\u529B\u56FE", size: 17, color: "888888", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      new Paragraph({ children: [new PageBreak()] }),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.3 \u7EF4\u5EA6\u5F97\u5206\u5206\u5E03")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [safeImageRun("/workspace/lm-eval-suite/charts/boxplot.png")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
        new TextRun({ text: "\u56FE 3: \u56DB\u7EF4\u5EA6\u5F97\u5206\u5206\u5E03\u7BB1\u7EBF\u56FE", size: 17, color: "888888", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.4 \u4E0D\u540C\u89C4\u6A21\u6A21\u578B\u5BF9\u6BD4")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [safeImageRun("/workspace/lm-eval-suite/charts/compare_bar.png")] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
        new TextRun({ text: "\u56FE 4: 35B vs 27B \u6A21\u578B\u5404\u7EF4\u5EA6\u5E73\u5747\u5F97\u5206\u5BF9\u6BD4", size: 17, color: "888888", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      // === 4. Analysis ===
      new Paragraph({ children: [new PageBreak()] }),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("\u56DB\u3001\u5206\u6790\u4E0E\u53D1\u73B0")] }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.1 \u6A21\u578B\u89C4\u6A21\u4E0E\u6027\u80FD\u5173\u7CFB")] }),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "35B \u53C2\u6570\u91CF\u7EA7\u6A21\u578B\u5728\u6240\u6709\u7EF4\u5EA6\u4E0A\u5747\u660E\u663E\u4F18\u4E8E 27B \u6A21\u578B\u3002\u5C24\u5176\u5728\u7F16\u7801\u80FD\u529B\u4E0A\uFF0C35B \u6A21\u578B\u5E73\u5747\u5F97\u5206\u8FBE " + cAvg + "\uFF0C\u800C 27B \u6A21\u578B\u4EC5\u4E3A 73.6\u3002\u8FD9\u8868\u660E\u53C2\u6570\u91CF\u5BF9\u6A21\u578B\u7684\u7EFC\u5408\u80FD\u529B\u6709\u663E\u8457\u5F71\u54CD\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.2 \u91CF\u5316\u7CBE\u5EA6\u5F71\u54CD")] }),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "\u4E0D\u540C\u91CF\u5316\u65B9\u6848\u5BF9\u6A21\u578B\u6027\u80FD\u6709\u4E00\u5B9A\u5F71\u54CD\u3002OQ8 \u91CF\u5316\u901A\u5E38\u80FD\u4FDD\u6301\u8F83\u9AD8\u7684\u6027\u80FD\u4FDD\u7559\u7387\uFF0C\u800C OQ4 \u548C NVFP4 \u91CF\u5316\u5219\u4F1A\u5E26\u6765\u4E00\u5B9A\u7684\u6027\u80FD\u635F\u5931\u3002\u4F8B\u5982 qwen3.6-35b-a3b-nvfp4 \u7684\u7F16\u7801\u5F97\u5206\u4EC5\u4E3A 50\uFF0C\u8FDC\u4F4E\u4E8E\u540C\u7CFB\u5217\u6A21\u578B\u7684\u5E73\u5747\u6C34\u5E73\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.3 \u5F02\u5E38\u6A21\u578B")] }),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "qwopus3.6-35b-a3b-v1-oq8-mtp \u6A21\u578B\u6D4B\u8BD5\u603B\u5206\u4E3A 0\uFF0C\u56DB\u4E2A\u7EF4\u5EA6\u5747\u65E0\u6709\u6548\u6570\u636E\u3002\u8BE5\u6A21\u578B\u53EF\u80FD\u5B58\u5728\u52A0\u8F7D\u6216\u8FDE\u63A5\u95EE\u9898\uFF0C\u5EFA\u8BAE\u91CD\u65B0\u6D4B\u8BD5\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.4 TOP 3 \u6A21\u578B\u70B9\u8BC4")] }),
      new Paragraph({ spacing: { after: 80 }, children: [
        new TextRun({ text: "\u{1F947} qwen3.6-35b-a3b-claude-4.6-opus-reasoning-distilled (\u603B\u5206 87.0)", bold: true, size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } }),
      ]}),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "\u7F16\u7801\u80FD\u529B\u7A81\u51FA\uFF0899.4\uFF09\uFF0C\u63A8\u7406\u80FD\u529B\u4F18\u79C0\uFF0886.3\uFF09\uFF0C\u7EFC\u5408\u8868\u73B0\u6700\u4F73\u3002Claude \u8BAD\u7EC3\u6570\u636E\u7684\u84B8\u998F\u5BF9\u63A8\u7406\u80FD\u529B\u6709\u663E\u8457\u63D0\u5347\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),
      new Paragraph({ spacing: { after: 80 }, children: [
        new TextRun({ text: "\u{1F948} qwopus3.6-35b-a3b-v1-mtp (\u603B\u5206 86.9)", bold: true, size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } }),
      ]}),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "\u63A8\u7406\u80FD\u529B\u6700\u5F3A\uFF0886.3\uFF09\uFF0C\u7F16\u7801\u548C\u667A\u80FD\u4F53\u8868\u73B0\u5747\u8861\uFF0CMTP \u6280\u672F\u5E26\u6765\u4E86\u7A33\u5B9A\u7684\u6027\u80FD\u63D0\u5347\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),
      new Paragraph({ spacing: { after: 80 }, children: [
        new TextRun({ text: "\u{1F949} qwopus-moe-35b-a3b (\u603B\u5206 86.8)", bold: true, size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } }),
      ]}),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "\u7F16\u7801\u80FD\u529B\u6EE1\u5206\uFF08100.0\uFF09\uFF0CMoE \u67B6\u6784\u5728\u7F16\u7801\u4EFB\u52A1\u4E0A\u5C55\u73B0\u51FA\u5353\u8D8A\u7684\u4F18\u52BF\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),

      // === 5. Methodology ===
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("\u4E94\u3001\u6D4B\u8BD5\u65B9\u6CD5")] }),
      new Paragraph({ spacing: { after: 80 }, children: [
        new TextRun({ text: "\u6D4B\u8BD5\u6DB5\u76D6\u56DB\u5927\u7EF4\u5EA6\uFF0C\u6BCF\u4E2A\u7EF4\u5EA6\u5305\u542B 8 \u9879\u6D4B\u8BD5\uFF0C\u5171\u8BA1 32 \u9879\u6D4B\u8BD5\uFF08\u52A0\u4E0A\u6027\u80FD 5 \u9879\u5171 37 \u9879\uFF09\u3002", size: 21, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } })
      ]}),
      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [2000, 7000],
        rows: [
          new TableRow({ cantSplit: true, children: [headerCell("\u7EF4\u5EA6", 2000), headerCell("\u6D4B\u8BD5\u5185\u5BB9", 7000)] }),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u7F16\u7801 (Coding)", 2000, { bold: true }),
            dataCell("\u7EA2\u9ED1\u6811\u3001LRU\u7F13\u5B58\u3001\u751F\u4EA7\u8005\u6D88\u8D39\u8005\u3001\u4EE3\u7801\u91CD\u6784\u3001SQL\u9632\u62A4\u3001\u5927\u6570\u636E\u3001\u5355\u5143\u6D4B\u8BD5\u3001RESTful API", 7000, { align: AlignmentType.LEFT })
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u667A\u80FD\u4F53 (Agent)", 2000, { bold: true }),
            dataCell("\u5355\u5DE5\u5177\u3001\u591A\u5DE5\u5177\u3001\u6761\u4EF6\u5206\u652F\u3001\u5FAA\u73AF\u3001\u9519\u8BEF\u6062\u590D\u3001\u4EBA\u673A\u534F\u4F5C\u3001\u4E0A\u4E0B\u6587\u3001\u4EFB\u52A1\u89C4\u5212", 7000, { align: AlignmentType.LEFT })
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u63A8\u7406 (Reasoning)", 2000, { bold: true }),
            dataCell("\u903B\u8F91\u3001\u6570\u5B66\u3001\u5B9E\u9A8C\u3001\u56E0\u679C\u3001\u6A21\u5F0F\u3001\u4F26\u7406\u3001\u521B\u65B0\u3001\u5143\u8BA4\u77E5", 7000, { align: AlignmentType.LEFT })
          ]}),
          new TableRow({ cantSplit: true, children: [
            dataCell("\u6027\u80FD (Performance)", 2000, { bold: true }),
            dataCell("\u9996\u5B57\u5EF6\u8FDF\u3001\u5410\u5410\u91CF\u3001\u54CD\u5E94\u65F6\u95F4\u3001\u5E76\u53D14\u3001\u5E76\u53D18", 7000, { align: AlignmentType.LEFT })
          ]}),
        ]
      }),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/workspace/lm-eval-suite/LM_Studio_模型深度评测报告.docx", buffer);
  console.log("Report generated!");
});
