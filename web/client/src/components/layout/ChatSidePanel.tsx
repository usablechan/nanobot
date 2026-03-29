import { useEffect, useRef } from "react";
import type { Agent, AgentChatMessage, AgentConfig, ApprovalRequest } from "../../types";
import { formatTime } from "../../utils";
import { MarkdownLite } from "../common/MarkdownLite";

type ChatSidePanelProps = {
  agent: Agent | null;
  config?: AgentConfig;
  chat: AgentChatMessage[];
  approvalRequests: ApprovalRequest[];
  onApprovalResolve: (
    requestId: string,
    resolution: "approved" | "rejected",
    replyMode?: "once" | "always" | "reject",
    answerText?: string,
  ) => void;
  chatInput: string;
  onChatInputChange: (value: string) => void;
  onSendChat: () => void;
  onFocusLeader: () => void;
  onClose: () => void;
  onResizeStart: (event: React.PointerEvent<HTMLButtonElement>) => void;
};

export function ChatSidePanel({
  agent,
  config,
  chat,
  approvalRequests,
  onApprovalResolve,
  chatInput,
  onChatInputChange,
  onSendChat,
  onFocusLeader,
  onClose,
  onResizeStart,
}: ChatSidePanelProps) {
  const chatListRef = useRef<HTMLDivElement | null>(null);
  const isComposingRef = useRef(false);
  const sendAfterComposeRef = useRef(false);
  const activeAgentId = agent?.id || "lead";
  const pendingApprovals = (approvalRequests || [])
    .filter((item) => item.status === "pending")
    .filter((item) => (activeAgentId === "lead" ? true : item.agentId === activeAgentId))
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 5);

  useEffect(() => {
    const node = chatListRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [chat, agent?.id]);

  return (
    <aside className="relative hidden min-h-0 flex-col border-l border-slate-300/70 bg-slate-50 text-slate-800 xl:flex">
      <button
        type="button"
        onPointerDown={onResizeStart}
        className="absolute left-0 top-0 h-full w-1.5 -translate-x-1/2 cursor-col-resize bg-transparent"
        aria-label="채팅 패널 너비 조절"
      />

      <div className="flex items-center justify-between border-b border-slate-300 px-3 py-2">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-slate-500">Chat</div>
          <div className="text-sm font-semibold">{agent?.name || "Leader"}</div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700"
            onClick={onFocusLeader}
          >
            Leader
          </button>
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700"
            onClick={onClose}
          >
            닫기
          </button>
        </div>
      </div>

      <div ref={chatListRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {config?.enabled === false ? (
          <div className="text-xs text-slate-500">비활성화된 에이전트입니다.</div>
        ) : null}
        {pendingApprovals.length ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-2.5">
            <div className="mb-2 text-xs font-semibold text-amber-800">승인 필요</div>
            <div className="flex flex-col gap-2">
              {pendingApprovals.map((request) => (
                <div key={request.id} className="rounded-lg border border-amber-200 bg-white p-2">
                  <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
                    <span>{request.kind || "approval"} · {request.agentId}</span>
                    <span>{formatTime(request.createdAt)}</span>
                  </div>
                  <div className="text-sm text-slate-800">
                    <MarkdownLite text={request.text} className="space-y-1" />
                  </div>
                  <div className="mt-2 flex gap-2">
                    {request.kind === "permission" ? (
                      <>
                        <button
                          type="button"
                          className="rounded-md border border-emerald-500 bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700"
                          onClick={() => onApprovalResolve(request.id, "approved", "once")}
                        >
                          Once
                        </button>
                        <button
                          type="button"
                          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                          onClick={() => onApprovalResolve(request.id, "approved", "always")}
                        >
                          Always
                        </button>
                        <button
                          type="button"
                          className="rounded-md border border-rose-500 bg-rose-50 px-2 py-1 text-[11px] font-semibold text-rose-700"
                          onClick={() => onApprovalResolve(request.id, "rejected", "reject")}
                        >
                          Reject
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="rounded-md border border-emerald-500 bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700"
                          onClick={() => onApprovalResolve(request.id, "approved")}
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          className="rounded-md border border-rose-500 bg-rose-50 px-2 py-1 text-[11px] font-semibold text-rose-700"
                          onClick={() => onApprovalResolve(request.id, "rejected")}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {chat.length === 0 ? (
          <div className="text-xs text-slate-500">대화가 아직 없습니다.</div>
        ) : null}
        {chat.map((message) => (
          <div
            key={message.id}
            className={`rounded-lg border px-2.5 py-2 text-sm ${message.role === "user" ? "border-blue-300 bg-blue-50" : "border-slate-300 bg-white"}`}
          >
            <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
              <span>{message.role === "user" ? "나" : agent?.name || "Agent"}</span>
              <span>{formatTime(message.ts)}</span>
            </div>
            <MarkdownLite text={message.text} />
          </div>
        ))}
      </div>

      <div className="border-t border-slate-300 p-3">
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-800"
            type="text"
            value={chatInput}
            onChange={(event) => onChatInputChange(event.target.value)}
            onCompositionStart={() => {
              isComposingRef.current = true;
            }}
            onCompositionEnd={() => {
              isComposingRef.current = false;
              if (!sendAfterComposeRef.current) return;
              sendAfterComposeRef.current = false;
              // Defer so the final composed character is reflected in state.
              window.setTimeout(() => onSendChat(), 0);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                const nativeEvent = event.nativeEvent as unknown as { isComposing?: boolean };
                const isComposing =
                  isComposingRef.current ||
                  nativeEvent?.isComposing === true ||
                  // keyCode 229 is a common IME composing signal
                  (event as unknown as { keyCode?: number }).keyCode === 229;
                event.preventDefault();
                if (isComposing) {
                  sendAfterComposeRef.current = true;
                  return;
                }
                onSendChat();
              }
            }}
            disabled={config?.enabled === false}
            placeholder="메시지 보내기"
          />
          <button
            type="button"
            className={`rounded-lg border border-blue-500 bg-blue-600 px-3 py-2 text-sm font-semibold text-white ${config?.enabled === false ? "opacity-50" : ""}`}
            onClick={onSendChat}
            disabled={config?.enabled === false}
          >
            전송
          </button>
        </div>
      </div>
    </aside>
  );
}
