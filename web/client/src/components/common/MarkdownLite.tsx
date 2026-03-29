import type { ReactNode } from "react";

type MarkdownLiteProps = {
  text: string;
  className?: string;
};

type Block =
  | { type: "text"; content: string }
  | { type: "code"; lang: string; content: string };

function parseBlocks(src: string): Block[] {
  const blocks: Block[] = [];
  const raw = String(src || "");
  let cursor = 0;

  while (cursor < raw.length) {
    const fenceStart = raw.indexOf("```", cursor);
    if (fenceStart < 0) {
      const tail = raw.slice(cursor);
      if (tail) blocks.push({ type: "text", content: tail });
      break;
    }

    const before = raw.slice(cursor, fenceStart);
    if (before) blocks.push({ type: "text", content: before });

    const afterTicks = fenceStart + 3;
    const lineEnd = raw.indexOf("\n", afterTicks);
    if (lineEnd < 0) {
      blocks.push({ type: "text", content: raw.slice(fenceStart) });
      break;
    }

    const lang = raw.slice(afterTicks, lineEnd).trim();
    const fenceEnd = raw.indexOf("```", lineEnd + 1);
    if (fenceEnd < 0) {
      blocks.push({ type: "text", content: raw.slice(fenceStart) });
      break;
    }

    const code = raw.slice(lineEnd + 1, fenceEnd).replace(/\n$/, "");
    blocks.push({ type: "code", lang, content: code });
    cursor = fenceEnd + 3;
  }

  return blocks;
}

function parseLinks(text: string, keySeed: { value: number }): ReactNode[] {
  const nodes: ReactNode[] = [];
  const raw = String(text || "");
  const regex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(raw))) {
    const [full, label, url] = match;
    const idx = match.index;
    if (idx > lastIndex) nodes.push(raw.slice(lastIndex, idx));
    nodes.push(
      <a
        key={`link-${keySeed.value++}`}
        href={url}
        target="_blank"
        rel="noreferrer"
        className="text-blue-700 underline"
      >
        {label}
      </a>,
    );
    lastIndex = idx + full.length;
  }

  if (lastIndex < raw.length) nodes.push(raw.slice(lastIndex));
  return nodes;
}

function parseBoldAndLinks(text: string, keySeed: { value: number }): ReactNode[] {
  const raw = String(text || "");
  const nodes: ReactNode[] = [];
  let cursor = 0;

  while (cursor < raw.length) {
    const start = raw.indexOf("**", cursor);
    if (start < 0) {
      nodes.push(...parseLinks(raw.slice(cursor), keySeed));
      break;
    }
    const end = raw.indexOf("**", start + 2);
    if (end < 0) {
      nodes.push(...parseLinks(raw.slice(cursor), keySeed));
      break;
    }
    if (start > cursor) nodes.push(...parseLinks(raw.slice(cursor, start), keySeed));
    const boldText = raw.slice(start + 2, end);
    nodes.push(
      <strong key={`bold-${keySeed.value++}`} className="font-semibold text-slate-900">
        {parseLinks(boldText, keySeed)}
      </strong>,
    );
    cursor = end + 2;
  }

  return nodes;
}

function parseInlineCode(text: string): Array<{ type: "text" | "code"; content: string }> {
  const parts: Array<{ type: "text" | "code"; content: string }> = [];
  const raw = String(text || "");
  let cursor = 0;

  while (cursor < raw.length) {
    const start = raw.indexOf("`", cursor);
    if (start < 0) {
      parts.push({ type: "text", content: raw.slice(cursor) });
      break;
    }
    const end = raw.indexOf("`", start + 1);
    if (end < 0) {
      parts.push({ type: "text", content: raw.slice(cursor) });
      break;
    }
    if (start > cursor) parts.push({ type: "text", content: raw.slice(cursor, start) });
    parts.push({ type: "code", content: raw.slice(start + 1, end) });
    cursor = end + 1;
  }

  return parts.filter((part) => part.content !== "");
}

function renderInline(text: string, keySeed: { value: number }): ReactNode[] {
  const parts = parseInlineCode(text);
  const nodes: ReactNode[] = [];
  parts.forEach((part) => {
    if (part.type === "code") {
      nodes.push(
        <code
          key={`icode-${keySeed.value++}`}
          className="rounded-md border border-slate-200 bg-slate-50 px-1 py-0.5 font-mono text-[0.85em] text-slate-800"
        >
          {part.content}
        </code>,
      );
      return;
    }
    nodes.push(...parseBoldAndLinks(part.content, keySeed));
  });
  return nodes;
}

export function MarkdownLite({ text, className }: MarkdownLiteProps) {
  const blocks = parseBlocks(text);
  const keySeed = { value: 0 };

  return (
    <div className={className || "space-y-2"}>
      {blocks.map((block, index) => {
        if (block.type === "code") {
          return (
            <pre
              key={`block-${index}`}
              className="max-h-80 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-800"
            >
              <code>{block.content}</code>
            </pre>
          );
        }

        const paragraphs = String(block.content || "").split(/\n{2,}/);
        return (
          <div key={`block-${index}`} className="space-y-2">
            {paragraphs.map((paragraph, pIndex) => (
              <p
                key={`p-${index}-${pIndex}`}
                className="whitespace-pre-wrap break-words text-sm text-slate-800"
              >
                {renderInline(paragraph, keySeed)}
              </p>
            ))}
          </div>
        );
      })}
    </div>
  );
}

