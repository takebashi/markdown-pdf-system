const emptyPreviewMessage = "Markdownを入力すると、ここにプレビューが表示されます。";

const state = {
  meta: {},
  blocks: [],
};

const allowedThemes = new Set(["business", "teal-gray"]);

const elements = {
  input: document.querySelector("#markdownInput"),
  preview: document.querySelector("#preview"),
  title: document.querySelector("#documentTitle"),
  theme: document.querySelector("#themeSelect"),
  file: document.querySelector("#fileInput"),
  print: document.querySelector("#printButton"),
};

const printMargins = { top: "16mm", right: "14mm", bottom: "16mm", left: "14mm" };

function normalizeTheme(value) {
  return allowedThemes.has(value) ? value : "business";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function inlineMarkdown(value) {
  let text = escapeHtml(value);
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    const safeHref = escapeHtml(href);
    return `<a href="${safeHref}" target="_blank" rel="noreferrer">${label}</a>`;
  });
  return text;
}

function stripInline(value) {
  return value
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

function parseFrontMatter(markdown) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  if (lines[0]?.trim() !== "---") {
    return { meta: {}, lines };
  }
  const meta = {};
  let end = -1;
  for (let index = 1; index < lines.length; index += 1) {
    if (lines[index].trim() === "---") {
      end = index;
      break;
    }
    const separator = lines[index].indexOf(":");
    if (separator > -1) {
      const key = lines[index].slice(0, separator).trim().toLowerCase();
      const value = lines[index].slice(separator + 1).trim().replace(/^["']|["']$/g, "");
      meta[key] = value;
    }
  }
  return end > -1 ? { meta, lines: lines.slice(end + 1) } : { meta: {}, lines };
}

function splitTableRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function isTableStart(lines, index) {
  if (!lines[index]?.includes("|") || !lines[index + 1]?.includes("|")) return false;
  const cells = splitTableRow(lines[index + 1]);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function parseMarkdown(markdown) {
  const { meta, lines } = parseFrontMatter(markdown);
  const blocks = [];
  let paragraph = [];
  let index = 0;

  function flushParagraph() {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", text: paragraph.map((line) => line.trim()).join(" ") });
      paragraph = [];
    }
  }

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      index += 1;
      continue;
    }

    const fence = trimmed.match(/^```(\w+)?\s*$/);
    if (fence) {
      flushParagraph();
      const language = fence[1] || "";
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ type: "code", language, text: code.join("\n") });
      continue;
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2].trim() });
      index += 1;
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushParagraph();
      blocks.push({ type: "hr" });
      index += 1;
      continue;
    }

    const image = trimmed.match(/^!\[(.*?)\]\((.*?)\)$/);
    if (image) {
      flushParagraph();
      blocks.push({ type: "image", alt: image[1], src: image[2] });
      index += 1;
      continue;
    }

    if (isTableStart(lines, index)) {
      flushParagraph();
      const rows = [splitTableRow(lines[index])];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }
      blocks.push({ type: "table", rows });
      continue;
    }

    if (trimmed.startsWith(">")) {
      flushParagraph();
      const quote = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quote.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push({ type: "quote", text: quote.join(" ") });
      continue;
    }

    const listItem = line.match(/^\s*([-*+]|\d+\.)\s+(.+)$/);
    if (listItem) {
      flushParagraph();
      const ordered = /^\d+\.$/.test(listItem[1]);
      const items = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*([-*+]|\d+\.)\s+(.+)$/);
        if (!item || /^\d+\.$/.test(item[1]) !== ordered) break;
        items.push(item[2].trim());
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    paragraph.push(line);
    index += 1;
  }

  flushParagraph();
  return { meta, blocks };
}

function inferTitle(meta, blocks) {
  if (meta.title) return meta.title;
  const h1 = blocks.find((block) => block.type === "heading" && block.level === 1);
  return h1 ? stripInline(h1.text) : "Markdown PDF";
}

function inferLead(meta, blocks, title) {
  if (meta.subtitle) return { text: meta.subtitle, blockIndex: -1 };
  const titleIndex = blocks.findIndex(
    (block) => block.type === "heading" && block.level === 1 && stripInline(block.text) === title,
  );
  if (titleIndex > -1 && blocks[titleIndex + 1]?.type === "paragraph") {
    return { text: blocks[titleIndex + 1].text, blockIndex: titleIndex + 1 };
  }
  return { text: "", blockIndex: -1 };
}

function classifyCallout(text) {
  const normalized = stripInline(text).trim();
  const rules = [
    ["callout-conclusion", /^(結論|推奨)\s*[：:]/],
    ["callout-warning", /^(注意|重要)\s*[：:]/],
    ["callout-risk", /^リスク\s*[：:]/],
    ["callout-info", /^(補足|ポイント)\s*[：:]/],
    ["callout-action", /^次のアクション\s*[：:]/],
  ];
  return rules.find(([, pattern]) => pattern.test(normalized))?.[0] || "callout-info";
}

function calloutLabel(className) {
  return {
    "callout-conclusion": "CONCLUSION",
    "callout-warning": "NOTE",
    "callout-risk": "RISK",
    "callout-info": "INFO",
    "callout-action": "ACTION",
  }[className] || "INFO";
}

function isNumericLike(value) {
  return /^[\s¥$€£+\-]?\d[\d,]*(\.\d+)?\s*(%|円|件|台|GB|MB|TB|時間|分|日|ヶ月|年)?\s*$/.test(stripInline(value));
}

function renderListItem(item) {
  const task = item.match(/^\[( |x|X)\]\s+(.+)$/);
  if (!task) return inlineMarkdown(item);
  const checked = task[1].toLowerCase() === "x";
  return `<span class="task-box${checked ? " is-checked" : ""}" aria-hidden="true"></span><span>${inlineMarkdown(task[2])}</span>`;
}

function listClasses(block, previousHeading) {
  const classes = [];
  if (block.items.every((item) => /^\[( |x|X)\]\s+/.test(item))) classes.push("task-list");
  if (block.ordered && /^(手順|ステップ|進め方|流れ)$/.test(previousHeading)) classes.push("steps-list");
  if (/^(次のアクション|対応事項|確認事項|TODO)$/.test(previousHeading)) classes.push("action-list");
  return classes.join(" ");
}

function renderBlocks(meta, blocks) {
  const title = inferTitle(meta, blocks);
  const lead = inferLead(meta, blocks, title);
  const metaLine = [meta.author, meta.date].filter(Boolean).join(" / ");
  let skippedFirstTitle = false;
  let previousHeading = "";
  const body = [];

  body.push(`
    <section class="doc-cover">
      <h1>${inlineMarkdown(title)}</h1>
      ${lead.text ? `<p>${inlineMarkdown(lead.text)}</p>` : ""}
      ${metaLine ? `<div class="doc-meta">${inlineMarkdown(metaLine)}</div>` : ""}
    </section>
  `);

  blocks.forEach((block, blockIndex) => {
    if (!skippedFirstTitle && block.type === "heading" && block.level === 1 && stripInline(block.text) === title) {
      skippedFirstTitle = true;
      previousHeading = stripInline(block.text);
      return;
    }

    if (blockIndex === lead.blockIndex) {
      return;
    }

    if (block.type === "heading") {
      const level = Math.min(Math.max(block.level, 1), 4);
      body.push(`<h${level}>${inlineMarkdown(block.text)}</h${level}>`);
      previousHeading = stripInline(block.text);
    } else if (block.type === "paragraph") {
      body.push(`<p>${inlineMarkdown(block.text)}</p>`);
    } else if (block.type === "quote") {
      const className = classifyCallout(block.text);
      body.push(`<blockquote class="callout ${className}" data-label="${calloutLabel(className)}">${inlineMarkdown(block.text)}</blockquote>`);
    } else if (block.type === "list") {
      const tag = block.ordered ? "ol" : "ul";
      const className = listClasses(block, previousHeading);
      const renderedItems = block.items.map((item) => `<li>${renderListItem(item)}</li>`).join("");
      body.push(`<${tag}${className ? ` class="${className}"` : ""}>${renderedItems}</${tag}>`);
    } else if (block.type === "code") {
      const codeClass = block.language === "text" ? " class=\"prompt-block\"" : "";
      const label = block.language === "text" ? "PROMPT" : "CODE";
      body.push(`<pre${codeClass} data-label="${label}"><code>${escapeHtml(block.text)}</code></pre>`);
    } else if (block.type === "table") {
      const [header = [], ...rows] = block.rows;
      const tableClass = header.length >= 5 ? " class=\"table-wide\"" : "";
      const head = header.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join("");
      const tableRows = rows
        .map((row) => `<tr>${row.map((cell) => `<td${isNumericLike(cell) ? ' class="numeric-cell"' : ""}>${inlineMarkdown(cell)}</td>`).join("")}</tr>`)
        .join("");
      body.push(`<table${tableClass}><thead><tr>${head}</tr></thead><tbody>${tableRows}</tbody></table>`);
    } else if (block.type === "image") {
      body.push(`<figure><img src="${escapeHtml(block.src)}" alt="${escapeHtml(block.alt)}">${block.alt ? `<figcaption>${inlineMarkdown(block.alt)}</figcaption>` : ""}</figure>`);
    } else if (block.type === "hr") {
      body.push("<hr>");
    }
  });

  body.push(`<footer class="doc-footer"><span>${inlineMarkdown(title)}</span><span>Markdown to PDF</span></footer>`);

  elements.title.textContent = title;
  elements.preview.innerHTML = body.join("\n");
}

function updatePrintPageMargins() {
  let style = document.querySelector("#printPageMargins");

  if (!style) {
    style = document.createElement("style");
    style.id = "printPageMargins";
    document.head.appendChild(style);
  }

  style.textContent = `
:root {
  --print-margin-top: ${printMargins.top};
  --print-margin-right: ${printMargins.right};
  --print-margin-bottom: ${printMargins.bottom};
  --print-margin-left: ${printMargins.left};
}

@page {
  size: A4;
  margin: 0;
}
`;
}

function updatePreview() {
  const isEmpty = !elements.input.value.trim();
  const theme = normalizeTheme(elements.theme.value);
  if (elements.theme.value !== theme) {
    elements.theme.value = theme;
  }
  elements.preview.className = `paper theme-${theme}${isEmpty ? " is-empty" : ""}`;
  updatePrintPageMargins();

  if (isEmpty) {
    state.meta = {};
    state.blocks = [];
    elements.title.textContent = "Preview";
    elements.preview.innerHTML = `<div class="empty-preview">${emptyPreviewMessage}</div>`;
    return;
  }

  const parsed = parseMarkdown(elements.input.value);
  state.meta = parsed.meta;
  state.blocks = parsed.blocks;
  renderBlocks(state.meta, state.blocks);
}

function readFile(file) {
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    elements.input.value = String(reader.result || "");
    updatePreview();
  });
  reader.readAsText(file, "utf-8");
}

elements.input.value = "";
elements.input.addEventListener("input", updatePreview);
elements.theme.addEventListener("change", updatePreview);
elements.print.addEventListener("click", () => window.print());
elements.file.addEventListener("change", (event) => {
  const [file] = event.target.files || [];
  if (file) readFile(file);
});

updatePreview();
