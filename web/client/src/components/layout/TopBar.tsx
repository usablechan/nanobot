import type { AppState } from "../../types";

type TopBarProps = {
  runStateLabel: string;
  appState: AppState | null;
  selectedTeamId: string;
  runMissionInput: string;
  onRunMissionInputChange: (value: string) => void;
  onCreateRun: () => void;
  runOptions: Array<{ runId: string; mission?: string; updatedAt: number }>;
  onSelectRun: (runId: string) => void;
};

export function TopBar({
  runStateLabel,
  appState,
  selectedTeamId,
  runMissionInput,
  onRunMissionInputChange,
  onCreateRun,
  runOptions,
  onSelectRun,
}: TopBarProps) {
  const modeLabel = appState?.mode === "nanobot" ? "NANOBOT" : "SIMULATION";
  const currentRunId = appState?.runId || "";

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-2">
      <div className="flex min-w-[240px] flex-col gap-1">
        <p className="m-0 text-[11px] uppercase tracking-[0.24em] text-blue-600">Agent Orchestrator</p>
        <h1 className="m-0 text-xl font-semibold text-slate-800">자비스 오케스트레이션 캔버스</h1>
        <p className="m-0 text-xs text-slate-500">Team: {selectedTeamId} · Run: {currentRunId || "-"}</p>
      </div>

      <div className="flex min-w-[360px] flex-1 flex-wrap items-center justify-end gap-2">
        <input
          type="text"
          value={runMissionInput}
          onChange={(event) => onRunMissionInputChange(event.target.value)}
          className="min-w-[180px] rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700"
          placeholder="새 Run 미션(선택)"
        />
        <button
          type="button"
          onClick={onCreateRun}
          className="rounded-lg border border-blue-500 bg-blue-600 px-2.5 py-1.5 text-xs font-semibold text-white"
        >
          Run 생성
        </button>
        <select
          value={currentRunId}
          onChange={(event) => onSelectRun(event.target.value)}
          className="min-w-[180px] rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700"
        >
          <option value="">Run 선택</option>
          {runOptions.map((run) => (
            <option key={run.runId} value={run.runId}>
              {run.runId}
              {run.mission ? ` · ${run.mission}` : ""}
            </option>
          ))}
        </select>
        <div
          className={`rounded-full border px-3 py-1 text-[11px] font-bold tracking-wider ${
            appState?.running
              ? "border-emerald-300 bg-emerald-50 text-emerald-700"
              : "border-slate-300 bg-slate-50 text-slate-700"
          }`}
        >
          {runStateLabel}
        </div>
        <div className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-[11px] font-bold tracking-wider text-slate-700">
          {modeLabel}
        </div>
        <div className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-[11px] font-bold tracking-wider text-blue-700">
          TEAM {selectedTeamId}
        </div>
      </div>
    </header>
  );
}
