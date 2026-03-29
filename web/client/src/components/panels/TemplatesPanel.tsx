import { useMemo, useState } from "react";
import type { AgentTemplate } from "../../types";

type TemplatesPanelProps = {
  title: string;
  subtitle: string;
  templates: AgentTemplate[];
};

export function TemplatesPanel({ title, subtitle, templates }: TemplatesPanelProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter((item) =>
      [item.name, item.title, item.model, item.id].join(" ").toLowerCase().includes(q),
    );
  }, [templates, query]);

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div>
        <h2 className="m-0 text-lg font-semibold">{title}</h2>
        <p className="m-0 text-xs text-slate-500">{subtitle}</p>
      </div>

      <input
        className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm"
        placeholder="템플릿 검색 (이름/역할/모델)"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-500">
            검색 결과가 없습니다.
          </div>
        ) : (
          filtered.map((template) => (
            <div
              key={template.id}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.setData("application/x-agent-template", JSON.stringify(template));
                event.dataTransfer.effectAllowed = "copy";
              }}
              className="cursor-grab rounded-lg border border-slate-200 bg-white p-3 active:cursor-grabbing"
              title="스테이지로 드래그해서 추가"
            >
              <div className="text-sm font-semibold text-slate-800">{template.name}</div>
              <div className="text-xs text-slate-500">{template.title}</div>
              <div className="mt-1 text-[11px] text-slate-500">model: {template.model}</div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
