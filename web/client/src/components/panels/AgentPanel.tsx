import { useEffect, useRef } from "react";
import type { Agent, AgentChatMessage, AgentConfig, AgentFormState, ApprovalRequest } from "../../types";
import { formatTime } from "../../utils";
import { MarkdownLite } from "../common/MarkdownLite";

type AgentPanelProps = {
  title: string;
  subtitle: string;
  selectedAgent: Agent | null;
  selectedConfig?: AgentConfig;
  selectedChat: AgentChatMessage[];
  agentForm: AgentFormState;
  agentSaveState: "idle" | "saving" | "saved" | "error";
  agentChatInput: string;
  onAgentFormChange: (next: Partial<AgentFormState>) => void;
  onSaveAgentConfig: () => void;
  onAbortAgent: () => void;
  onRemoveAgent: () => void;
  agentActionError?: string;
  approvalRequests?: ApprovalRequest[];
  onApprovalResolve: (
    requestId: string,
    resolution: "approved" | "rejected",
    replyMode?: "once" | "always" | "reject",
    answerText?: string,
  ) => void;
  onChatInputChange: (value: string) => void;
  onSendChat: () => void;
};

export function AgentPanel({ title, subtitle, selectedAgent, selectedConfig, selectedChat, agentForm, agentSaveState, agentChatInput, onAgentFormChange, onSaveAgentConfig, onAbortAgent, onRemoveAgent, agentActionError, approvalRequests, onApprovalResolve, onChatInputChange, onSendChat }: AgentPanelProps) {
  const chatListRef = useRef<HTMLDivElement | null>(null);
  const isComposingRef = useRef(false);
  const sendAfterComposeRef = useRef(false);

  useEffect(() => {
    const chatList = chatListRef.current;
    if (!chatList) return;
    chatList.scrollTop = chatList.scrollHeight;
  }, [selectedAgent?.id, selectedChat]);

  const pendingApprovals = (approvalRequests ?? [])
    .filter((item) => item.status === "pending")
    .filter((item) => {
      if (!selectedAgent) return false;
      if (selectedAgent.id === "lead") return true;
      return item.agentId === selectedAgent.id;
    })
    .slice(-8);

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">AGENT</span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
          <div>
            <h3 className="m-0 text-base font-semibold">{selectedAgent ? selectedAgent.name : "에이전트를 선택하세요"}</h3>
            <p className="m-0 text-xs text-slate-500">{selectedAgent ? selectedAgent.title : "캐릭터에서 에이전트를 선택해주세요."}</p>
          </div>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold">{selectedAgent?.state ?? "대기"}</span>
        </div>

        {selectedAgent && (
          <>
            {pendingApprovals.length ? (
              <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
                <div className="text-xs font-semibold text-amber-800">승인 필요</div>
                {pendingApprovals.map((request) => (
                  <div key={request.id} className="rounded-lg border border-amber-300 bg-white p-2 text-xs">
                    <div className="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                      <span>{request.kind || "approval"} · {request.agentId || "agent"}</span>
                      <span>{formatTime(request.createdAt)}</span>
                    </div>
                    <div className="text-slate-800">
                      <MarkdownLite text={request.text} className="space-y-1" />
                    </div>
                    <div className="mt-2 flex gap-2">
                      {request.kind === "permission" ? (
                        <>
                          <button
                            type="button"
                            onClick={() => onApprovalResolve(request.id, "approved", "once")}
                            className="rounded-md border border-emerald-500 bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700"
                          >
                            Once
                          </button>
                          <button
                            type="button"
                            onClick={() => onApprovalResolve(request.id, "approved", "always")}
                            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                          >
                            Always
                          </button>
                          <button
                            type="button"
                            onClick={() => onApprovalResolve(request.id, "rejected", "reject")}
                            className="rounded-md border border-rose-500 bg-rose-50 px-2 py-1 text-[11px] font-semibold text-rose-700"
                          >
                            Reject
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => onApprovalResolve(request.id, "approved")}
                            className="rounded-md border border-emerald-500 bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700"
                          >
                            Accept
                          </button>
                          <button
                            type="button"
                            onClick={() => onApprovalResolve(request.id, "rejected")}
                            className="rounded-md border border-rose-500 bg-rose-50 px-2 py-1 text-[11px] font-semibold text-rose-700"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3">
              <label className="flex flex-col gap-1 text-xs text-slate-500"><span>모델</span><select className="rounded-lg border border-slate-300 px-2 py-2 text-sm" value={agentForm.model} onChange={(event) => onAgentFormChange({ model: event.target.value })}><option value="gpt-5.3-codex">gpt-5.3-codex</option><option value="gpt-5.2-codex">gpt-5.2-codex</option><option value="gpt-4.1">gpt-4.1</option><option value="gpt-4.1-mini">gpt-4.1-mini</option><option value="gpt-4o">gpt-4o</option><option value="gpt-4o-mini">gpt-4o-mini</option><option value="o3">o3</option><option value="o4-mini">o4-mini</option><option value="claude-sonnet-4">claude-sonnet-4</option></select></label>
              <label className="flex flex-col gap-1 text-xs text-slate-500"><span>시스템 프롬프트</span><textarea className="min-h-[96px] rounded-lg border border-slate-300 px-2 py-2 text-sm" value={agentForm.systemPrompt} onChange={(event) => onAgentFormChange({ systemPrompt: event.target.value })} rows={4} /></label>
              <label className="flex flex-col gap-1 text-xs text-slate-500"><span>아바타 URL</span><input className="rounded-lg border border-slate-300 px-2 py-2 text-sm" type="text" value={agentForm.avatarUrl} onChange={(event) => onAgentFormChange({ avatarUrl: event.target.value })} /></label>
              <label className="flex flex-col gap-1 text-xs text-slate-500"><span>온도</span><input className="rounded-lg border border-slate-300 px-2 py-2 text-sm" type="number" value={agentForm.temperature} onChange={(event) => onAgentFormChange({ temperature: event.target.value })} /></label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={agentForm.enabled} onChange={(event) => onAgentFormChange({ enabled: event.target.checked })} />활성화</label>
              <div className="text-xs text-slate-500">{agentSaveState === "saving" ? "저장 중..." : agentSaveState === "saved" ? "저장 완료" : ""}</div>
              {agentActionError ? <div className="text-xs text-rose-600">{agentActionError}</div> : null}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={onSaveAgentConfig} className="rounded-lg border border-blue-500 bg-blue-600 px-3 py-2 text-sm font-semibold text-white">설정 저장</button>
                <button type="button" onClick={onAbortAgent} className="rounded-lg border border-amber-500 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">중단(Abort)</button>
                {selectedAgent?.isCustom ? (
                  <button type="button" onClick={onRemoveAgent} className="rounded-lg border border-rose-500 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700">에이전트 삭제</button>
                ) : null}
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3">
              <div className="flex min-h-[120px] max-h-[260px] flex-col gap-2 overflow-y-auto" ref={chatListRef}>
                {selectedConfig?.enabled === false && <div className="text-xs text-slate-500">현재 비활성화된 에이전트입니다. 설정에서 활성화하세요.</div>}
                {selectedConfig?.enabled !== false && selectedChat.length === 0 && <div className="text-xs text-slate-500">대화가 아직 없습니다.</div>}
                {selectedConfig?.enabled !== false && selectedChat.map((message) => (
                  <div key={message.id} className={`rounded-xl border p-2 text-sm ${message.role === "user" ? "border-amber-300" : "border-cyan-300"}`}>
                    <div className="mb-1 flex justify-between text-[11px] text-slate-500"><span>{message.role === "user" ? "나" : selectedAgent.name}</span><span>{formatTime(message.ts)}</span></div>
                    <div className="overflow-x-hidden">
                      <MarkdownLite text={message.text} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-lg border border-slate-300 px-2 py-2 text-sm"
                  type="text"
                  value={agentChatInput}
                  onChange={(event) => onChatInputChange(event.target.value)}
                  onCompositionStart={() => {
                    isComposingRef.current = true;
                  }}
                  onCompositionEnd={() => {
                    isComposingRef.current = false;
                    if (!sendAfterComposeRef.current) return;
                    sendAfterComposeRef.current = false;
                    window.setTimeout(() => onSendChat(), 0);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      const nativeEvent = event.nativeEvent as unknown as { isComposing?: boolean };
                      const isComposing =
                        isComposingRef.current ||
                        nativeEvent?.isComposing === true ||
                        (event as unknown as { keyCode?: number }).keyCode === 229;
                      event.preventDefault();
                      if (isComposing) {
                        sendAfterComposeRef.current = true;
                        return;
                      }
                      onSendChat();
                    }
                  }}
                  disabled={selectedConfig?.enabled === false}
                  placeholder="메시지를 입력하세요."
                />
                <button type="button" onClick={onSendChat} disabled={selectedConfig?.enabled === false} className={`rounded-lg border border-blue-500 bg-blue-600 px-3 py-2 text-sm font-semibold text-white ${selectedConfig?.enabled === false ? "opacity-50" : ""}`}>전송</button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
