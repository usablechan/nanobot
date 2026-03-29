import { useEffect, useMemo, useState } from "react";
import type { Agent, FeedEvent } from "../../types";
import { formatTime } from "../../utils";

type ToolsPanelProps = {
  title: string;
  subtitle: string;
  agents: Agent[];
  selectedAgentId: string | null;
  orderedFeed: FeedEvent[];
};

type StatusFilter = "all" | "pending" | "running" | "completed" | "error" | "unknown";

export function ToolsPanel({
  title,
  subtitle,
  agents,
  selectedAgentId,
  orderedFeed,
}: ToolsPanelProps) {
  const [agentFilter, setAgentFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (selectedAgentId) setAgentFilter(selectedAgentId);
  }, [selectedAgentId]);

  const toolEvents = useMemo(
    () => orderedFeed.filter((item) => item.type === "tool").slice().reverse(),
    [orderedFeed],
  );

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return toolEvents.filter((event) => {
      const status = (event.toolStatus || "unknown").toLowerCase() as StatusFilter;
      if (agentFilter !== "all" && event.agentId !== agentFilter) return false;
      if (statusFilter !== "all" && status !== statusFilter) return false;
      if (!normalizedQuery) return true;
      const target = [
        event.text,
        event.tool,
        event.toolTitle,
        event.toolInput,
        event.toolOutput,
        event.toolError,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return target.includes(normalizedQuery);
    });
  }, [toolEvents, agentFilter, statusFilter, query]);

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">
          TOOLS
        </span>
      </div>

      <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <select
          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          value={agentFilter}
          onChange={(event) => setAgentFilter(event.target.value)}
        >
          <option value="all">전체 에이전트</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
        >
          <option value="all">전체 상태</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="completed">completed</option>
          <option value="error">error</option>
          <option value="unknown">unknown</option>
        </select>
        <input
          className="min-w-[220px] flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          placeholder="툴명/입력/출력 검색"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        {!filtered.length ? (
          <div className="text-sm text-slate-500">표시할 툴 이벤트가 없습니다.</div>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {filtered.map((event) => {
              const agentName =
                agents.find((agent) => agent.id === event.agentId)?.name ||
                event.from ||
                event.agentId ||
                "agent";
              const status = event.toolStatus || "unknown";
              return (
                <li key={event.id} className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-800">
                      {event.toolTitle || event.tool || "tool"}
                    </div>
                    <div className="text-[11px] text-slate-500">{formatTime(event.ts)}</div>
                  </div>
                  <div className="mb-2 text-xs text-slate-500">
                    {agentName} · {status}
                    {event.tool ? ` · ${event.tool}` : ""}
                    {typeof event.attachmentCount === "number"
                      ? ` · attachments ${event.attachmentCount}`
                      : ""}
                  </div>
                  {event.toolInput ? (
                    <details className="mb-1">
                      <summary className="cursor-pointer text-xs font-semibold text-slate-600">Input</summary>
                      <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-700">{event.toolInput}</pre>
                    </details>
                  ) : null}
                  {event.toolOutput ? (
                    <details className="mb-1" open={status === "error"}>
                      <summary className="cursor-pointer text-xs font-semibold text-slate-600">Output</summary>
                      <pre className="mt-1 max-h-44 overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-700">{event.toolOutput}</pre>
                    </details>
                  ) : null}
                  {event.toolError ? (
                    <details open>
                      <summary className="cursor-pointer text-xs font-semibold text-rose-700">Error</summary>
                      <pre className="mt-1 max-h-44 overflow-auto whitespace-pre-wrap rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">{event.toolError}</pre>
                    </details>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
