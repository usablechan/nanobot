import type { Dispatch, SetStateAction } from "react";
import type { PlaybackState, ReplayState } from "../../types";

type ReplayPanelProps = {
  title: string;
  subtitle: string;
  playback: PlaybackState;
  replay: ReplayState;
  replayWindow: { start: number; end: number };
  replayDuration: number;
  replayCursorLabel: string;
  replayTotalLabel: string;
  replayStateLabel: string;
  setPlayback: Dispatch<SetStateAction<PlaybackState>>;
  setReplay: Dispatch<SetStateAction<ReplayState>>;
  refreshRuns: () => Promise<void>;
  loadReplay: (runId: string) => Promise<void>;
};

const btn = "rounded-lg border border-blue-500 bg-blue-600 px-3 py-2 text-sm font-semibold text-white";
const ghost = "rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700";

export function ReplayPanel({ title, subtitle, playback, replay, replayWindow, replayDuration, replayCursorLabel, replayTotalLabel, replayStateLabel, setPlayback, setReplay, refreshRuns, loadReplay }: ReplayPanelProps) {
  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div><h2 className="m-0 text-lg font-semibold">{title}</h2><p className="m-0 text-xs text-slate-500">{subtitle}</p></div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">REPLAY</span>
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2">
          <button type="button" className={ghost} onClick={() => replay.events.length && setPlayback((p) => ({ ...p, mode: "replay", isPlaying: false, cursorTime: replayWindow.start }))}>처음</button>
          <button type="button" className={btn} onClick={() => replay.events.length && setPlayback((p) => ({ ...p, mode: "replay", isPlaying: !p.isPlaying }))}>{playback.isPlaying ? "일시정지" : "재생"}</button>
          <button type="button" className={ghost} onClick={() => replay.events.length && setPlayback((p) => ({ ...p, mode: "replay", isPlaying: false, cursorTime: replayWindow.end }))}>끝</button>
          <button type="button" className={ghost} onClick={() => setPlayback((p) => ({ ...p, mode: "live", isPlaying: false }))}>라이브로</button>
        </div>

        <div className="flex items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-sm">
            <span>속도</span>
            <select className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={String(playback.speed)} onChange={(e) => setPlayback((p) => ({ ...p, speed: Number(e.target.value) || 1 }))}>
              <option value="0.5">0.5x</option><option value="1">1x</option><option value="1.5">1.5x</option><option value="2">2x</option><option value="3">3x</option>
            </select>
          </label>
          <div className="text-sm text-slate-500">{replayCursorLabel} / {replayTotalLabel}</div>
        </div>

        <input type="range" min={0} max={replayDuration} value={replayDuration ? playback.cursorTime - replayWindow.start : 0} onChange={(e) => setPlayback((p) => ({ ...p, mode: "replay", isPlaying: false, cursorTime: replayWindow.start + Number(e.target.value || 0) }))} disabled={!replay.events.length} className="w-full" />
        <div className={`rounded-lg border border-dashed p-2 text-sm ${replay.error ? "border-rose-300 text-rose-600" : "border-slate-300 text-slate-500"}`}>{replayStateLabel}</div>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <h3 className="m-0 text-base font-semibold">Run Replay</h3>
        <p className="m-0 text-xs text-slate-500">이전 실행 로그 선택</p>
        <div className="flex flex-wrap gap-2">
          <select className="min-w-[220px] rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm" value={replay.runId} onChange={(event) => setReplay((prev) => ({ ...prev, runId: event.target.value }))}>
            <option value="">리플레이 선택</option>
            {replay.runs.map((run) => (<option key={run.runId} value={run.runId}>{run.runId} ({new Date(run.updatedAt).toLocaleString("ko-KR")})</option>))}
          </select>
          <button type="button" className={ghost} onClick={() => refreshRuns().catch(() => undefined)}>새로고침</button>
          <button type="button" className={btn} onClick={() => loadReplay(replay.runId)}>선택 run 불러오기</button>
        </div>
      </div>
    </section>
  );
}
