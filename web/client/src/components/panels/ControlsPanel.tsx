import { useEffect, useMemo, useState } from "react";
import type { AppState, ApprovalRequest } from "../../types";
import { formatTime } from "../../utils";
import { MarkdownLite } from "../common/MarkdownLite";

type ControlsPanelProps = {
  title: string;
  subtitle: string;
  appState: AppState | null;
  approvalPendingText: string;
  sendWs: (payload: object) => void;
};

const btn = "rounded-lg border border-blue-500 bg-blue-600 px-3 py-2 text-sm font-semibold text-white";
const ghostBtn = "rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700";

export function ControlsPanel({ title, subtitle, appState, approvalPendingText, sendWs }: ControlsPanelProps) {
  const [orchestratorEnabled, setOrchestratorEnabled] = useState(false);
  const [orchestratorTickMs, setOrchestratorTickMs] = useState("2000");
  const [orchestratorAutoRetry, setOrchestratorAutoRetry] = useState(true);
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!appState?.orchestrator) return;
    setOrchestratorEnabled(!!appState.orchestrator.enabled);
    setOrchestratorTickMs(String(appState.orchestrator.tickMs ?? 2000));
    setOrchestratorAutoRetry(!!appState.orchestrator.autoRetry);
  }, [appState?.orchestrator]);

  const orchestratorSummary = useMemo(() => {
    if (!appState?.orchestrator) return "Autopilot 상태 없음";
    const agentStates = Object.values(appState.orchestrator.agents ?? {});
    const activeCount = agentStates.filter((agent) => agent.activeTaskId).length;
    return `상태 ${appState.orchestrator.enabled ? "ON" : "OFF"} · tick ${appState.orchestrator.tickMs}ms · autoRetry ${appState.orchestrator.autoRetry ? "ON" : "OFF"} · 작업중 ${activeCount}명`;
  }, [appState?.orchestrator]);

  const handleApprove = () => {
    const requestId = pendingRequests[0]?.id || appState?.pendingApproval?.requestId;
    if (requestId) {
      sendWs({
        type: "approval.resolve",
        payload: { requestId, resolution: "approved", replyMode: "once" },
      });
      return;
    }
    sendWs({ type: "approve" });
  };

  const pendingRequests = useMemo(
    () =>
      (appState?.approvalRequests ?? [])
        .filter((item) => item.status === "pending")
        .sort((a, b) => b.createdAt - a.createdAt),
    [appState?.approvalRequests],
  );

  const sendResolve = (
    request: ApprovalRequest,
    resolution: "approved" | "rejected",
    replyMode?: "once" | "always" | "reject",
  ) => {
    sendWs({
      type: "approval.resolve",
      payload: {
        requestId: request.id,
        resolution,
        replyMode,
        answerText: questionAnswers[request.id] || "",
      },
    });
    if (questionAnswers[request.id]) {
      setQuestionAnswers((prev) => {
        const next = { ...prev };
        delete next[request.id];
        return next;
      });
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">CONTROL</span>
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => sendWs({ type: "control", action: "start" })} className={btn}>시작</button>
          <button type="button" onClick={() => sendWs({ type: "control", action: "pause" })} className={btn}>일시정지</button>
          <button type="button" onClick={() => sendWs({ type: "control", action: "reset" })} className={ghostBtn}>리셋</button>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!appState?.approvalGate} onChange={(event) => sendWs({ type: "toggleApproval", enabled: event.target.checked })} />
          <span>승인 게이트 (배포/릴리스)</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span>모드</span>
          <select className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={appState?.mode ?? "sim"} onChange={(event) => sendWs({ type: "setMode", mode: event.target.value })}>
            <option value="sim">Simulation</option>
            <option value="nanobot">nanobot Runtime</option>
          </select>
        </label>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <h3 className="m-0 text-base font-semibold">Autopilot</h3>
        <p className="m-0 text-xs text-slate-500">{orchestratorSummary}</p>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={orchestratorEnabled} onChange={(e) => { setOrchestratorEnabled(e.target.checked); sendWs({ type: "orchestrator.toggle", enabled: e.target.checked }); }} />Autopilot 활성화</label>
        <label className="flex items-center gap-2 text-sm">
          <span>tick(ms)</span>
          <input className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm" type="number" min={250} value={orchestratorTickMs} onChange={(event) => setOrchestratorTickMs(event.target.value)} />
        </label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={orchestratorAutoRetry} onChange={(e) => setOrchestratorAutoRetry(e.target.checked)} />자동 재시도</label>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={ghostBtn} onClick={() => sendWs({ type: "orchestrator.config.set", tickMs: Number(orchestratorTickMs) || 2000, autoRetry: orchestratorAutoRetry })}>설정 적용</button>
          <button type="button" className={btn} onClick={() => sendWs({ type: "orchestrator.toggle", enabled: !appState?.orchestrator?.enabled })}>{appState?.orchestrator?.enabled ? "Quick OFF" : "Quick ON"}</button>
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <h3 className="m-0 text-base font-semibold">승인 게이트</h3>
        <p className="m-0 text-xs text-slate-500">배포/릴리스 승인 필요 시 표시</p>
        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-2 text-sm">{approvalPendingText}</div>
        <button type="button" onClick={handleApprove} disabled={!pendingRequests.length} className={`${btn} ${!pendingRequests.length ? "opacity-50" : ""}`}>최신 요청 Once 허용</button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        <h3 className="m-0 text-base font-semibold">승인 큐</h3>
        <p className="mt-1 text-xs text-slate-500">permission/question 요청을 여기서 바로 처리</p>
        {!pendingRequests.length ? (
          <div className="mt-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-2 text-sm text-slate-500">
            대기 중인 요청이 없습니다.
          </div>
        ) : (
          <ul className="mt-2 m-0 flex list-none flex-col gap-2 p-0">
            {pendingRequests.map((request) => {
              const kind = request.kind === "question" ? "질문" : "권한";
              const firstQuestion = request.questions?.[0]?.question || "";
              return (
                <li key={request.id} className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-800">
                      {request.agentId || "agent"} · {kind}
                    </div>
                    <div className="text-[11px] text-slate-500">{formatTime(request.createdAt)}</div>
                  </div>
                  <div className="text-xs text-slate-600">
                    <MarkdownLite text={request.text} className="space-y-1" />
                  </div>
                  {firstQuestion ? (
                    <div className="mt-1 rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-700">
                      Q. {firstQuestion}
                    </div>
                  ) : null}
                  {request.kind === "question" ? (
                    <textarea
                      className="mt-2 min-h-[72px] w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs"
                      placeholder="질문 응답(비우면 기본 옵션 자동 선택)"
                      value={questionAnswers[request.id] || ""}
                      onChange={(event) =>
                        setQuestionAnswers((prev) => ({
                          ...prev,
                          [request.id]: event.target.value,
                        }))
                      }
                    />
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {request.kind === "permission" ? (
                      <>
                        <button type="button" className={btn} onClick={() => sendResolve(request, "approved", "once")}>Once</button>
                        <button type="button" className={ghostBtn} onClick={() => sendResolve(request, "approved", "always")}>Always</button>
                        <button type="button" className="rounded-lg border border-rose-500 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700" onClick={() => sendResolve(request, "rejected", "reject")}>Reject</button>
                      </>
                    ) : (
                      <>
                        <button type="button" className={btn} onClick={() => sendResolve(request, "approved")}>응답</button>
                        <button type="button" className="rounded-lg border border-rose-500 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700" onClick={() => sendResolve(request, "rejected")}>거절</button>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
