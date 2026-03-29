import { useCallback, useEffect, useMemo, useState } from "react";
import type { Agent } from "../../types";
import { getBackendHttpBase } from "../../utils";

type RuntimePanelProps = {
  title: string;
  subtitle: string;
  agents: Agent[];
  selectedTeamId: string;
};

type WorkerInfo = {
  botId: string;
  running: boolean;
  pid?: number | null;
  recentEvents?: Array<{ type?: string; line?: string; ts?: number }>;
};

type RuntimeSnapshot = {
  workers: WorkerInfo[];
  links: Record<string, string[]>;
};

export function RuntimePanel({ title, subtitle, agents, selectedTeamId }: RuntimePanelProps) {
  const base = getBackendHttpBase();
  const [snapshot, setSnapshot] = useState<RuntimeSnapshot>({ workers: [], links: {} });
  const [loading, setLoading] = useState(false);
  const [actioningBotId, setActioningBotId] = useState<string | null>(null);
  const [chatBotId, setChatBotId] = useState("");
  const [chatSessionId, setChatSessionId] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatResult, setChatResult] = useState("");
  const [autoChainEnabled, setAutoChainEnabled] = useState(false);
  const [linkFrom, setLinkFrom] = useState("");
  const [linkTo, setLinkTo] = useState("");
  const [relayFrom, setRelayFrom] = useState("");
  const [relayTo, setRelayTo] = useState("");
  const [relayMessage, setRelayMessage] = useState("");
  const [relayResult, setRelayResult] = useState("");
  const [teamMemory, setTeamMemory] = useState("");
  const [savingMemory, setSavingMemory] = useState(false);
  const [error, setError] = useState("");

  const agentIds = useMemo(() => agents.map((a) => a.id).filter(Boolean), [agents]);

  useEffect(() => {
    if (!chatBotId && agentIds.length) setChatBotId(agentIds[0]);
    if (!linkFrom && agentIds.length) setLinkFrom(agentIds[0]);
    if (!linkTo && agentIds.length > 1) setLinkTo(agentIds[1]);
    if (!relayFrom && agentIds.length) setRelayFrom(agentIds[0]);
    if (!relayTo && agentIds.length > 1) setRelayTo(agentIds[1]);
  }, [agentIds, chatBotId, linkFrom, linkTo, relayFrom, relayTo]);

  useEffect(() => {
    if (!chatBotId) return;
    setChatSessionId(`team:${selectedTeamId}:bot:${chatBotId}`);
  }, [chatBotId, selectedTeamId]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${base}/api/runtime/bots`);
      const data = await res.json();
      if (!res.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      setSnapshot({
        workers: Array.isArray(data?.workers) ? data.workers : [],
        links: data?.links && typeof data.links === "object" ? data.links : {},
      });
      const memRes = await fetch(
        `${base}/api/runtime/memory?teamId=${encodeURIComponent(selectedTeamId)}`,
      );
      const memData = await memRes.json();
      if (memRes.ok) setTeamMemory(String(memData?.memory || ""));
      setError("");
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`런타임 상태 조회 실패 (${reason})`);
    } finally {
      setLoading(false);
    }
  }, [base, selectedTeamId]);

  useEffect(() => {
    load().catch(() => undefined);
    const timer = setInterval(() => load().catch(() => undefined), 3000);
    return () => clearInterval(timer);
  }, [load]);

  const workersByBotId = useMemo(() => {
    const rows: Record<string, WorkerInfo> = {};
    for (const w of snapshot.workers) rows[w.botId] = w;
    return rows;
  }, [snapshot.workers]);

  const startBot = async (botId: string) => {
    setActioningBotId(botId);
    try {
      const res = await fetch(`${base}/api/runtime/bots/${encodeURIComponent(botId)}/start`, { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`봇 시작 실패 (${botId}): ${reason}`);
    } finally {
      setActioningBotId(null);
    }
  };

  const stopBot = async (botId: string) => {
    setActioningBotId(botId);
    try {
      const res = await fetch(`${base}/api/runtime/bots/${encodeURIComponent(botId)}/stop`, { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`봇 중지 실패 (${botId}): ${reason}`);
    } finally {
      setActioningBotId(null);
    }
  };

  const submitChat = async () => {
    const botId = chatBotId.trim();
    const message = chatInput.trim();
    if (!botId || !message) return;
    setChatResult("처리 중...");
    try {
      const res = await fetch(`${base}/api/runtime/bots/${encodeURIComponent(botId)}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          sessionId: chatSessionId.trim() || undefined,
          teamId: selectedTeamId,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      const content = String(data?.reply?.content || "");
      const baseText = content || "(empty response)";
      if (autoChainEnabled) {
        const chainLog = await runAutoChain(botId, baseText);
        setChatResult(chainLog ? `${baseText}\n\n---\n${chainLog}` : baseText);
      } else {
        setChatResult(baseText);
      }
      setChatInput("");
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setChatResult(`오류: ${reason}`);
    }
  };

  const saveTeamMemory = async (mode: "replace" | "append") => {
    setSavingMemory(true);
    try {
      const res = await fetch(`${base}/api/runtime/memory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          teamId: selectedTeamId,
          mode,
          text: teamMemory,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      if (typeof data.memory === "string") setTeamMemory(data.memory);
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`팀 메모리 저장 실패: ${reason}`);
    } finally {
      setSavingMemory(false);
    }
  };

  const clearTeamMemory = async () => {
    setSavingMemory(true);
    try {
      const res = await fetch(
        `${base}/api/runtime/memory?teamId=${encodeURIComponent(selectedTeamId)}`,
        { method: "DELETE" },
      );
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      setTeamMemory("");
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`팀 메모리 초기화 실패: ${reason}`);
    } finally {
      setSavingMemory(false);
    }
  };

  const runAutoChain = async (sourceBotId: string, sourceMessage: string) => {
    const maxHops = 8;
    const queue: Array<{ from: string; message: string; hop: number }> = [
      { from: sourceBotId, message: sourceMessage, hop: 0 },
    ];
    const visitedEdges = new Set<string>();
    const logs: string[] = [];

    while (queue.length) {
      const current = queue.shift();
      if (!current) break;
      if (current.hop >= maxHops) {
        logs.push(`자동 체인 중단: max hop(${maxHops}) 도달`);
        break;
      }
      const targets = snapshot.links[current.from] || [];
      for (const to of targets) {
        const edgeKey = `${current.from}->${to}`;
        if (visitedEdges.has(edgeKey)) continue;
        visitedEdges.add(edgeKey);
        try {
          const res = await fetch(`${base}/api/runtime/relay`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              fromBotId: current.from,
              toBotId: to,
              message: current.message,
            }),
          });
          const data = await res.json();
          if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
          const nextContent = String(data?.reply?.content || "");
          logs.push(`${current.from} -> ${to}\n${nextContent || "(empty response)"}`);
          queue.push({ from: to, message: nextContent, hop: current.hop + 1 });
        } catch (err) {
          const reason = err instanceof Error ? err.message : "network";
          logs.push(`${current.from} -> ${to} 실패: ${reason}`);
        }
      }
    }

    return logs.join("\n\n");
  };

  const createLink = async () => {
    if (!linkFrom || !linkTo) return;
    try {
      const res = await fetch(`${base}/api/runtime/links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fromBotId: linkFrom, toBotId: linkTo }),
      });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`링크 추가 실패: ${reason}`);
    }
  };

  const removeLink = async (fromBotId: string, toBotId: string) => {
    try {
      const params = new URLSearchParams({ fromBotId, toBotId });
      const res = await fetch(`${base}/api/runtime/links?${params.toString()}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`링크 삭제 실패: ${reason}`);
    }
  };

  const submitRelay = async () => {
    if (!relayFrom || !relayTo || !relayMessage.trim()) return;
    setRelayResult("릴레이 중...");
    try {
      const res = await fetch(`${base}/api/runtime/relay`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fromBotId: relayFrom, toBotId: relayTo, message: relayMessage.trim() }),
      });
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      setRelayResult(String(data?.reply?.content || "(empty response)"));
      setRelayMessage("");
      await load();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setRelayResult(`오류: ${reason}`);
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
        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 text-sm font-semibold text-slate-800">
            Team Shared Memory ({selectedTeamId})
          </div>
          <textarea
            className="min-h-[92px] w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={teamMemory}
            onChange={(e) => setTeamMemory(e.target.value)}
            placeholder="팀 공통 컨텍스트/규칙/진행상황 메모"
          />
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              className="rounded-md border border-blue-500 bg-blue-600 px-2.5 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
              onClick={() => saveTeamMemory("replace").catch(() => undefined)}
              disabled={savingMemory}
            >
              Replace
            </button>
            <button
              type="button"
              className="rounded-md border border-indigo-400 bg-indigo-50 px-2.5 py-1.5 text-xs font-semibold text-indigo-700 disabled:opacity-60"
              onClick={() => saveTeamMemory("append").catch(() => undefined)}
              disabled={savingMemory}
            >
              Append
            </button>
            <button
              type="button"
              className="rounded-md border border-rose-300 bg-rose-50 px-2.5 py-1.5 text-xs font-semibold text-rose-700 disabled:opacity-60"
              onClick={() => clearTeamMemory().catch(() => undefined)}
              disabled={savingMemory}
            >
              Clear
            </button>
          </div>
        </div>

        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 text-sm font-semibold text-slate-800">Workers</div>
          <div className="grid gap-2">
            {agentIds.map((botId) => {
              const worker = workersByBotId[botId];
              const running = worker?.running === true;
              return (
                <div key={botId} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-2 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-slate-800">{botId}</div>
                    <div className="text-xs text-slate-500">
                      {running ? `running${worker?.pid ? ` (pid ${worker.pid})` : ""}` : "stopped"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {running ? (
                      <button
                        type="button"
                        className="rounded-md border border-rose-300 bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700"
                        onClick={() => stopBot(botId)}
                        disabled={actioningBotId === botId}
                      >
                        Stop
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="rounded-md border border-emerald-300 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700"
                        onClick={() => startBot(botId)}
                        disabled={actioningBotId === botId}
                      >
                        Start
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
            {!agentIds.length ? <div className="text-xs text-slate-500">에이전트 목록이 비어있어요.</div> : null}
          </div>
        </div>

        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 text-sm font-semibold text-slate-800">Direct Chat</div>
          <div className="flex flex-col gap-2">
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={autoChainEnabled}
                onChange={(e) => setAutoChainEnabled(e.target.checked)}
              />
              Auto Chain (링크된 다음 봇으로 자동 전달)
            </label>
            <select
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs"
              value={chatBotId}
              onChange={(e) => setChatBotId(e.target.value)}
            >
              {agentIds.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
            <textarea
              className="min-h-[68px] rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="메시지 입력"
            />
            <input
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs"
              value={chatSessionId}
              onChange={(e) => setChatSessionId(e.target.value)}
              placeholder="session id (이어쓰기 키)"
            />
            <button
              type="button"
              className="w-fit rounded-md border border-blue-500 bg-blue-600 px-2.5 py-1.5 text-xs font-semibold text-white"
              onClick={() => submitChat().catch(() => undefined)}
            >
              보내기
            </button>
            {chatResult ? (
              <pre className="max-h-[180px] overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-700 whitespace-pre-wrap">{chatResult}</pre>
            ) : null}
          </div>
        </div>

        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 text-sm font-semibold text-slate-800">Links</div>
          <div className="mb-2 grid gap-2 md:grid-cols-2">
            <select className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs" value={linkFrom} onChange={(e) => setLinkFrom(e.target.value)}>
              {agentIds.map((id) => (<option key={id} value={id}>{id}</option>))}
            </select>
            <select className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs" value={linkTo} onChange={(e) => setLinkTo(e.target.value)}>
              {agentIds.map((id) => (<option key={id} value={id}>{id}</option>))}
            </select>
          </div>
          <button
            type="button"
            className="mb-2 rounded-md border border-blue-500 bg-blue-600 px-2.5 py-1.5 text-xs font-semibold text-white"
            onClick={() => createLink().catch(() => undefined)}
          >
            링크 추가
          </button>
          <div className="flex flex-col gap-1">
            {Object.entries(snapshot.links).length === 0 ? <div className="text-xs text-slate-500">링크가 없습니다.</div> : null}
            {Object.entries(snapshot.links).map(([from, targets]) =>
              targets.map((to) => (
                <div key={`${from}-${to}`} className="flex items-center justify-between rounded-md border border-slate-200 bg-white px-2 py-1">
                  <span className="text-xs text-slate-700">{from} → {to}</span>
                  <button
                    type="button"
                    className="rounded border border-slate-300 px-2 py-0.5 text-[11px] text-slate-600"
                    onClick={() => removeLink(from, to).catch(() => undefined)}
                  >
                    삭제
                  </button>
                </div>
              )),
            )}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 text-sm font-semibold text-slate-800">Relay Message</div>
          <div className="mb-2 grid gap-2 md:grid-cols-2">
            <select className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs" value={relayFrom} onChange={(e) => setRelayFrom(e.target.value)}>
              {agentIds.map((id) => (<option key={id} value={id}>{id}</option>))}
            </select>
            <select className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs" value={relayTo} onChange={(e) => setRelayTo(e.target.value)}>
              {agentIds.map((id) => (<option key={id} value={id}>{id}</option>))}
            </select>
          </div>
          <textarea
            className="mb-2 min-h-[68px] w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={relayMessage}
            onChange={(e) => setRelayMessage(e.target.value)}
            placeholder="from 봇 메시지를 to 봇으로 릴레이"
          />
          <button
            type="button"
            className="rounded-md border border-indigo-500 bg-indigo-600 px-2.5 py-1.5 text-xs font-semibold text-white"
            onClick={() => submitRelay().catch(() => undefined)}
          >
            릴레이 실행
          </button>
          {relayResult ? (
            <pre className="mt-2 max-h-[180px] overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-700 whitespace-pre-wrap">{relayResult}</pre>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
    </section>
  );
}
