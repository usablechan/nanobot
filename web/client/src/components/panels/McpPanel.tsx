import { useCallback, useEffect, useMemo, useState } from "react";
import { getBackendHttpBase } from "../../utils";

type McpPanelProps = {
  title: string;
  subtitle: string;
};

type McpStatusItem = {
  status?: string;
  error?: string;
};

function statusChip(status: string) {
  const value = status.toLowerCase();
  if (value === "connected") return "border-emerald-300 bg-emerald-50 text-emerald-700";
  if (value === "disabled") return "border-slate-300 bg-slate-100 text-slate-700";
  if (value === "failed") return "border-rose-300 bg-rose-50 text-rose-700";
  if (value === "needs_auth" || value === "needs_client_registration") {
    return "border-amber-300 bg-amber-50 text-amber-800";
  }
  return "border-slate-300 bg-white text-slate-700";
}

export function McpPanel({ title, subtitle }: McpPanelProps) {
  const base = getBackendHttpBase();
  const [status, setStatus] = useState<Record<string, McpStatusItem>>({});
  const [loading, setLoading] = useState(false);
  const [actionName, setActionName] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${base}/api/nanobot/mcp`);
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      const next = data?.status && typeof data.status === "object" ? data.status : {};
      setStatus(next);
      setError("");
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`MCP 상태 로딩 실패 (${reason})`);
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  const rows = useMemo(() => {
    return Object.entries(status)
      .map(([name, info]) => ({ name, info }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [status]);

  const connect = async (name: string) => {
    setActionName(name);
    try {
      const res = await fetch(`${base}/api/nanobot/mcp/${encodeURIComponent(name)}/connect`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`연결 실패 (${name}): ${reason}`);
    } finally {
      setActionName(null);
    }
  };

  const disconnect = async (name: string) => {
    setActionName(name);
    try {
      const res = await fetch(`${base}/api/nanobot/mcp/${encodeURIComponent(name)}/disconnect`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`해제 실패 (${name}): ${reason}`);
    } finally {
      setActionName(null);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 disabled:opacity-50"
          onClick={() => load()}
          disabled={loading}
        >
          새로고침
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        {loading && !rows.length ? (
          <div className="text-sm text-slate-500">불러오는 중...</div>
        ) : null}
        {!loading && !rows.length ? (
          <div className="text-sm text-slate-500">
            MCP 서버가 없습니다. `~/.nanobot/config.json`의 `tools.mcpServers`를 확인해줘.
          </div>
        ) : null}

        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {rows.map(({ name, info }) => {
            const st = String(info?.status || "unknown");
            const isConnected = st === "connected";
            const canAct = actionName === null || actionName === name;
            return (
              <li key={name} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-800">{name}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusChip(st)}`}>
                        {st}
                      </span>
                      {info?.error ? (
                        <span className="truncate text-xs text-rose-700">error: {info.error}</span>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    {isConnected ? (
                      <button
                        type="button"
                        className="rounded-md border border-rose-400 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 disabled:opacity-50"
                        onClick={() => disconnect(name)}
                        disabled={!canAct || actionName === name}
                      >
                        Disconnect
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="rounded-md border border-emerald-400 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 disabled:opacity-50"
                        onClick={() => connect(name)}
                        disabled={!canAct || actionName === name}
                      >
                        Connect
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
    </section>
  );
}
