import type { RefObject } from "react";
import type { Agent, AgentConfig } from "../../types";

type AgentStageProps = {
  agents: Agent[];
  agentConfigs: Record<string, AgentConfig> | undefined;
  positions: Record<string, { x: number; y: number }>;
  viewport: { x: number; y: number };
  selectedAgentId: string | null;
  stageRef: RefObject<HTMLDivElement>;
  onSelectAgent: (agentId: string | null) => void;
  onDragStart: (
    agentId: string,
    event: React.PointerEvent<HTMLButtonElement>,
  ) => void;
  onStagePanStart: (event: React.PointerEvent<HTMLDivElement>) => void;
  onTemplateDrop: (payload: {
    templateJson: string;
    stageX: number;
    stageY: number;
  }) => void;
  quickAddOpen: boolean;
  quickAddName: string;
  quickAddTitle: string;
  onQuickAddNameChange: (value: string) => void;
  onQuickAddTitleChange: (value: string) => void;
  quickAddError?: string;
  onToggleQuickAdd: () => void;
  onCloseQuickAdd: () => void;
  onCreateAgent: () => void;
  showQuickAdd?: boolean;
};

export function AgentStage({
  agents,
  agentConfigs,
  positions,
  viewport,
  selectedAgentId,
  stageRef,
  onSelectAgent,
  onDragStart,
  onStagePanStart,
  onTemplateDrop,
  quickAddOpen,
  quickAddName,
  quickAddTitle,
  onQuickAddNameChange,
  onQuickAddTitleChange,
  quickAddError,
  onToggleQuickAdd,
  onCloseQuickAdd,
  onCreateAgent,
  showQuickAdd = true,
}: AgentStageProps) {
  const getStateMeta = (state: string) => {
    if (state === "thinking") {
      return {
        dot: "bg-blue-400",
        chip: "border-blue-300 bg-blue-50 text-blue-700",
        label: "Thinking",
      };
    }
    if (state === "tooling") {
      return {
        dot: "bg-violet-400",
        chip: "border-violet-300 bg-violet-50 text-violet-700",
        label: "Tooling",
      };
    }
    if (state === "waiting") {
      return {
        dot: "bg-amber-400",
        chip: "border-amber-300 bg-amber-50 text-amber-700",
        label: "Waiting",
      };
    }
    if (state === "error" || state === "blocked") {
      return {
        dot: "bg-rose-400",
        chip: "border-rose-300 bg-rose-50 text-rose-700",
        label: "Error",
      };
    }
    if (state === "running") {
      return {
        dot: "bg-emerald-400",
        chip: "border-emerald-300 bg-emerald-50 text-emerald-700",
        label: "Running",
      };
    }
    if (state === "done") {
      return {
        dot: "bg-emerald-400",
        chip: "border-emerald-300 bg-emerald-50 text-emerald-700",
        label: "Done",
      };
    }
    return {
      dot: "bg-slate-400",
      chip: "border-slate-300 bg-slate-100 text-slate-600",
      label: "Idle",
    };
  };

  const gridBackground = {
    backgroundColor: "#f8fafc",
    backgroundImage:
      "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.45) 1px, transparent 0)",
    backgroundSize: "22px 22px",
  };

  return (
    <section className="relative flex min-h-0 flex-1 flex-col border-slate-300/70 bg-slate-50">
      <div
        ref={stageRef}
        className="relative min-h-0 flex-1 overflow-hidden"
        style={gridBackground}
        onDragOver={(event) => {
          if (
            event.dataTransfer.types.includes("application/x-agent-template")
          ) {
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
          }
        }}
        onDrop={(event) => {
          const templateJson = event.dataTransfer.getData(
            "application/x-agent-template",
          );
          if (!templateJson) return;
          const rect = event.currentTarget.getBoundingClientRect();
          const stageX = event.clientX - rect.left;
          const stageY = event.clientY - rect.top;
          onTemplateDrop({ templateJson, stageX, stageY });
        }}
        onPointerDown={(event) => {
          const target = event.target as HTMLElement;
          if (target?.closest('[data-agent-node="1"]')) return;
          onSelectAgent(null);
          onStagePanStart(event);
        }}
      >
        <div
          className="absolute inset-0"
          style={{ transform: `translate(${viewport.x}px, ${viewport.y}px)` }}
        >
          {agents.map((agent) => {
            const pos = positions[agent.id] ?? { x: 40, y: 40 };
            const isSelected = agent.id === selectedAgentId;
            const stateMeta = getStateMeta(agent.state);
            const model = agentConfigs?.[agent.id]?.model || "-";
            return (
              <button
                key={agent.id}
                type="button"
                data-agent-node="1"
                onClick={() => onSelectAgent(agent.id)}
                onPointerDown={(event) => onDragStart(agent.id, event)}
                className={`absolute w-[280px] select-none rounded-2xl border border-slate-300 bg-white p-3 text-left text-slate-800 shadow-[0_6px_20px_rgba(15,23,42,0.12)] ${
                  isSelected ? "ring-2 ring-blue-400" : ""
                }`}
                style={{ left: pos.x, top: pos.y }}
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Agent
                  </div>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${stateMeta.chip}`}
                  >
                    {stateMeta.label}
                  </span>
                </div>

                <div className="mb-2 flex items-center gap-2">
                  <span
                    className={`flex h-2.5 w-2.5 items-center justify-center rounded-full text-xs font-bold ${stateMeta.dot}`}
                  />
                  <div className="text-base font-semibold">{agent.name}</div>
                </div>

                <div className="mb-2 text-sm text-slate-600">{agent.title || "-"}</div>

                <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-600">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1">
                    Queue {agent.queue}
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1">
                    Inbox {agent.inbox}
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1">
                    Retry {agent.retries}
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1">
                    Fail {agent.failures}
                  </div>
                </div>

                <div className="mt-2 truncate rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600">
                  {agent.lastActionText || "No recent action"}
                </div>

                <div className="mt-2 truncate text-[11px] text-slate-500">
                  Model: {model}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {showQuickAdd ? (
        <div className="absolute bottom-4 right-4 z-20 flex flex-col items-end gap-2">
          {quickAddOpen && (
            <div className="flex w-60 flex-col gap-2 rounded-xl border border-slate-300 bg-white p-2.5 shadow-lg">
              <input
                className="rounded-lg border border-slate-300 px-2 py-2 text-sm"
                type="text"
                placeholder="에이전트 이름"
                value={quickAddName}
                onChange={(e) => onQuickAddNameChange(e.target.value)}
              />
              <input
                className="rounded-lg border border-slate-300 px-2 py-2 text-sm"
                type="text"
                placeholder="타이틀(선택)"
                value={quickAddTitle}
                onChange={(e) => onQuickAddTitleChange(e.target.value)}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 rounded-lg border border-slate-300 bg-slate-100 px-2 py-2 text-sm font-semibold"
                  onClick={onCloseQuickAdd}
                >
                  취소
                </button>
                <button
                  type="button"
                  className="flex-1 rounded-lg border border-blue-500 bg-blue-600 px-2 py-2 text-sm font-semibold text-white"
                  onClick={onCreateAgent}
                >
                  추가
                </button>
              </div>
              {quickAddError ? (
                <div className="text-xs text-rose-600">{quickAddError}</div>
              ) : null}
            </div>
          )}
          <button
            type="button"
            className="grid h-12 w-12 place-items-center rounded-full border border-blue-500 bg-blue-600 text-2xl text-white"
            onClick={onToggleQuickAdd}
            aria-label="에이전트 추가"
          >
            +
          </button>
        </div>
      ) : null}
    </section>
  );
}
