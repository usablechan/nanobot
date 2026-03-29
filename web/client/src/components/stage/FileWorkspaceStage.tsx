import { useEffect, useState } from "react";
import { getBackendHttpBase } from "../../utils";

type OpenFile = {
  name: string;
  content: string;
  updatedAt: number | null;
  dirty: boolean;
  loading: boolean;
};

type FileWorkspaceStageProps = {
  teamId: string;
  openFileName: string | null;
};

export function FileWorkspaceStage({ teamId, openFileName }: FileWorkspaceStageProps) {
  const base = getBackendHttpBase();
  const [tabs, setTabs] = useState<OpenFile[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setTabs([]);
    setActiveTab(null);
  }, [teamId]);

  const saveCurrent = async () => {
    const current = tabs.find((tab) => tab.name === activeTab) || null;
    if (!current) return;
    try {
      const res = await fetch(`${base}/api/team/file?teamId=${encodeURIComponent(teamId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: current.name, content: current.content, updatedBy: "user" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error("save_failed");
      setTabs((prev) =>
        prev.map((tab) =>
          tab.name === current.name
            ? { ...tab, dirty: false, updatedAt: Number(data.updatedAt) || Date.now() }
            : tab,
        ),
      );
      setError("");
    } catch {
      setError("저장 실패");
    }
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveCurrent().catch(() => undefined);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [tabs, activeTab, teamId]);

  useEffect(() => {
    if (!openFileName) return;
    if (tabs.some((tab) => tab.name === openFileName)) {
      setActiveTab(openFileName);
      return;
    }

    setTabs((prev) => [
      ...prev,
      { name: openFileName, content: "", updatedAt: null, dirty: false, loading: true },
    ]);
    setActiveTab(openFileName);

    const load = async () => {
      try {
        const res = await fetch(
          `${base}/api/team/file?teamId=${encodeURIComponent(teamId)}&path=${encodeURIComponent(openFileName)}`,
        );
        const data = await res.json();
        if (!res.ok) throw new Error(`HTTP_${res.status}`);
        setTabs((prev) =>
          prev.map((tab) =>
            tab.name === openFileName
              ? {
                  ...tab,
                  content: String(data.content || ""),
                  updatedAt: Number(data.updatedAt) || Date.now(),
                  loading: false,
                }
              : tab,
          ),
        );
      } catch (err) {
        const reason = err instanceof Error ? err.message : "network";
        setError(`파일 로딩 실패 (${reason})`);
        setTabs((prev) => prev.filter((tab) => tab.name !== openFileName));
      }
    };

    load().catch(() => undefined);
  }, [base, openFileName, tabs, teamId]);

  const current = tabs.find((tab) => tab.name === activeTab) || null;

  const closeTab = (name: string) => {
    setTabs((prev) => {
      const next = prev.filter((tab) => tab.name !== name);
      if (activeTab === name) setActiveTab(next[next.length - 1]?.name || null);
      return next;
    });
  };

  return (
    <section className="relative flex min-h-0 flex-1 flex-col border-slate-300/70 bg-slate-50">
      <div className="flex items-center gap-1 border-b border-slate-200 bg-white px-2 py-1">
        {tabs.map((tab) => (
          <div
            key={tab.name}
            className={`flex items-center gap-2 rounded-t-lg border px-3 py-1 text-xs ${activeTab === tab.name ? "border-slate-300 bg-slate-100" : "border-transparent bg-slate-50 text-slate-500"}`}
          >
            <button type="button" onClick={() => setActiveTab(tab.name)}>
              {tab.name}
              {tab.dirty ? " *" : ""}
            </button>
            <button type="button" className="text-slate-400" onClick={() => closeTab(tab.name)}>
              ✕
            </button>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-slate-500">team: {teamId}</span>
          <button
            type="button"
            className="rounded-md border border-blue-400 bg-blue-500 px-2 py-1 text-xs font-semibold text-white disabled:opacity-40"
            onClick={() => saveCurrent()}
            disabled={!current || current.loading}
          >
            저장
          </button>
        </div>
      </div>

      {!current ? (
        <div className="grid min-h-0 flex-1 place-items-center text-sm text-slate-500">왼쪽 파일 탐색기에서 파일을 선택해줘.</div>
      ) : (
        <textarea
          className="min-h-0 flex-1 resize-none border-0 bg-white p-4 font-mono text-xs outline-none"
          value={current.content}
          onChange={(event) => {
            const value = event.target.value;
            setTabs((prev) =>
              prev.map((tab) =>
                tab.name === current.name ? { ...tab, content: value, dirty: true } : tab,
              ),
            );
          }}
        />
      )}

      {error ? <div className="absolute bottom-3 left-3 rounded-md bg-rose-100 px-3 py-1 text-xs text-rose-700">{error}</div> : null}
    </section>
  );
}
