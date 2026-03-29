import type { FeedEvent, PlaybackMode } from "../../types";
import { formatTime } from "../../utils";
import { MarkdownLite } from "../common/MarkdownLite";

type MessagesPanelProps = {
  title: string;
  subtitle: string;
  playbackMode: PlaybackMode;
  orderedFeed: FeedEvent[];
  streamStateLabel: string;
  streamStateMode: string;
};

export function MessagesPanel({
  title,
  subtitle,
  playbackMode,
  orderedFeed,
  streamStateLabel,
  streamStateMode,
}: MessagesPanelProps) {
  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">
          {playbackMode === "replay" ? "REPLAY" : "LIVE"}
        </span>
      </div>

      <div className="relative flex min-h-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-white/80 p-3">
        {!orderedFeed.length ? (
          <div
            className={`absolute inset-0 grid place-items-center rounded-2xl text-sm ${
              streamStateMode === "error" ? "text-rose-600" : streamStateMode === "loading" ? "text-blue-600" : "text-slate-500"
            }`}
          >
            {streamStateLabel}
          </div>
        ) : null}

        <ul className="m-0 flex min-h-0 list-none flex-col gap-2 overflow-y-auto p-0">
          {orderedFeed.map((item) => (
            <li key={item.id} className="rounded-xl border border-slate-200 bg-white p-2.5 text-sm">
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>{item.from ?? "System"}</span>
                <span>{formatTime(item.ts)}</span>
              </div>
              <div className="text-slate-700">
                {item.text ? <MarkdownLite text={item.text} className="space-y-1" /> : item.type}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
