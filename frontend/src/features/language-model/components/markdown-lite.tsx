import { Fragment, type ReactNode } from "react";

/**
 * Zero-dependency Markdown renderer for AI advisory answers.
 *
 * The model returns GitHub-flavoured Markdown — headings, `**bold**`, ordered /
 * bulleted lists, `---` rules, inline `code`, and the occasional `$$ … $$` LaTeX
 * formula. Rendering it as raw text (asterisks, hashes, backslashes on screen)
 * reads badly, so this turns the common constructs into real elements. It is
 * deliberately small: it covers what our prompts actually produce, not the whole
 * CommonMark spec.
 */

interface MarkdownLiteProps {
  content: string;
  className?: string;
}

// ── Inline formatting: **bold**, *italic*, `code` ───────────────────────────────
const INLINE_RE = /(\*\*[^*]+\*\*|(?<!\*)\*[^*\n]+\*(?!\*)|`[^`]+`)/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(INLINE_RE).filter((p) => p !== "" && p !== undefined);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={key} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={key} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return (
        <em key={key} className="italic">
          {part.slice(1, -1)}
        </em>
      );
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

// ── LaTeX → readable plain text (we don't ship KaTeX) ──────────────────────────
function deLatex(raw: string): string {
  return raw
    .replace(/\$\$?/g, "")
    .replace(/\\text\{([^}]*)\}/g, "$1")
    .replace(/\\mathrm\{([^}]*)\}/g, "$1")
    .replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, "($1) / ($2)")
    .replace(/\\min/g, "min")
    .replace(/\\max/g, "max")
    .replace(/\\times/g, "×")
    .replace(/\\cdot/g, "·")
    .replace(/\\leq/g, "≤")
    .replace(/\\geq/g, "≥")
    .replace(/\\left|\\right/g, "")
    .replace(/\\[,;:]/g, " ")
    .replace(/[{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// ── Block-level parsing ───────────────────────────────────────────────────────
type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: { marker: string; text: string }[] }
  | { type: "hr" }
  | { type: "math"; text: string }
  | { type: "p"; text: string };

const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const OL_RE = /^\s*(\d+)[.)]\s+(.*)$/;
const UL_RE = /^\s*[-*+]\s+(.*)$/;
const HR_RE = /^\s*([-*_])\1{2,}\s*$/;

function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Fenced-ish LaTeX block: a line containing $$ … possibly spanning lines.
    if (line.includes("$$")) {
      const collected: string[] = [line];
      let closed = (line.match(/\$\$/g) ?? []).length >= 2;
      i += 1;
      while (!closed && i < lines.length) {
        collected.push(lines[i]);
        if (lines[i].includes("$$")) closed = true;
        i += 1;
      }
      blocks.push({ type: "math", text: deLatex(collected.join(" ")) });
      continue;
    }

    if (HR_RE.test(line)) {
      blocks.push({ type: "hr" });
      i += 1;
      continue;
    }

    const heading = HEADING_RE.exec(line);
    if (heading) {
      blocks.push({
        type: "heading",
        level: heading[1].length,
        text: heading[2].replace(/\s*#+\s*$/, ""),
      });
      i += 1;
      continue;
    }

    if (OL_RE.test(line)) {
      const items: { marker: string; text: string }[] = [];
      while (i < lines.length) {
        if (lines[i].trim() === "" && OL_RE.test(lines[i + 1] ?? "")) {
          i += 1; // tolerate one blank line between list items
          continue;
        }
        if (!OL_RE.test(lines[i])) break;
        const m = OL_RE.exec(lines[i])!;
        items.push({ marker: m[1], text: m[2] });
        i += 1;
        // fold indented continuation / sub-bullet lines into the item text
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !OL_RE.test(lines[i])) {
          items[items.length - 1].text += `\n${lines[i].trim()}`;
          i += 1;
        }
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    if (UL_RE.test(line)) {
      const items: string[] = [];
      while (i < lines.length) {
        if (lines[i].trim() === "" && UL_RE.test(lines[i + 1] ?? "")) {
          i += 1;
          continue;
        }
        if (!UL_RE.test(lines[i])) break;
        items.push(UL_RE.exec(lines[i])![1]);
        i += 1;
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !UL_RE.test(lines[i])) {
          items[items.length - 1] += ` ${lines[i].trim()}`;
          i += 1;
        }
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // Paragraph: gather consecutive plain lines.
    const para: string[] = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !HEADING_RE.test(lines[i]) &&
      !OL_RE.test(lines[i]) &&
      !UL_RE.test(lines[i]) &&
      !HR_RE.test(lines[i]) &&
      !lines[i].includes("$$")
    ) {
      para.push(lines[i]);
      i += 1;
    }
    blocks.push({ type: "p", text: para.join(" ") });
  }

  return blocks;
}

/** Render an item that may carry folded sub-lines (nested bullets / formulae). */
function ItemBody({ text, keyPrefix }: { text: string; keyPrefix: string }): ReactNode {
  const [head, ...rest] = text.split("\n");
  const subBullets = rest.filter((r) => /^[-*+]\s+/.test(r));
  const mathLines = rest.filter((r) => !/^[-*+]\s+/.test(r) && (r.includes("$$") || /\\[a-z]+/i.test(r)));
  const plainRest = rest.filter(
    (r) => !/^[-*+]\s+/.test(r) && !(r.includes("$$") || /\\[a-z]+/i.test(r)),
  );
  return (
    <>
      {renderInline([head, ...plainRest].join(" "), keyPrefix)}
      {mathLines.map((m, i) => (
        <pre
          key={`${keyPrefix}-math-${i}`}
          className="mt-1 overflow-x-auto rounded-md bg-muted/60 px-2.5 py-1.5 font-mono text-xs"
        >
          {deLatex(m)}
        </pre>
      ))}
      {subBullets.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-5">
          {subBullets.map((b, i) => (
            <li key={`${keyPrefix}-sub-${i}`}>
              {renderInline(b.replace(/^[-*+]\s+/, ""), `${keyPrefix}-sub-${i}`)}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function MarkdownLite({ content, className }: MarkdownLiteProps) {
  const blocks = parseBlocks(content.trim());

  return (
    <div className={`space-y-2.5 leading-relaxed ${className ?? ""}`}>
      {blocks.map((block, bi) => {
        const key = `b-${bi}`;
        switch (block.type) {
          case "hr":
            return <hr key={key} className="border-border/60" />;
          case "heading": {
            const cls =
              block.level <= 3
                ? "text-sm font-semibold text-foreground"
                : "text-[0.8rem] font-semibold uppercase tracking-wide text-muted-foreground";
            return (
              <p key={key} className={`${cls} mt-1`}>
                {renderInline(block.text, key)}
              </p>
            );
          }
          case "math":
            return (
              <pre
                key={key}
                className="overflow-x-auto rounded-md bg-muted/60 px-3 py-2 font-mono text-xs text-foreground"
              >
                {block.text}
              </pre>
            );
          case "ul":
            return (
              <ul key={key} className="list-disc space-y-1 pl-5">
                {block.items.map((it, ii) => (
                  <li key={`${key}-${ii}`}>
                    <ItemBody text={it} keyPrefix={`${key}-${ii}`} />
                  </li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={key} className="list-decimal space-y-1 pl-5">
                {block.items.map((it, ii) => (
                  <li key={`${key}-${ii}`}>
                    <ItemBody text={it.text} keyPrefix={`${key}-${ii}`} />
                  </li>
                ))}
              </ol>
            );
          default:
            return (
              <p key={key} className="whitespace-pre-wrap">
                {renderInline(block.text, key)}
              </p>
            );
        }
      })}
    </div>
  );
}
