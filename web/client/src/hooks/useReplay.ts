import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FeedEvent, PlaybackState, ReplayState } from "../types";
import { clamp, formatDuration, getReplayWindow, normalizeEvent } from "../utils";

export function useReplay(feed: FeedEvent[]) {
  const [playback, setPlayback] = useState<PlaybackState>({
    mode: "live",
    cursorTime: 0,
    speed: 1,
    isPlaying: false
  });
  const [replay, setReplay] = useState<ReplayState>({
    runId: "",
    runs: [],
    events: [],
    loading: false,
    error: null
  });

  const playbackRafRef = useRef<number | null>(null);
  const playbackFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (playback.mode !== "replay" || !playback.isPlaying) {
      if (playbackRafRef.current) cancelAnimationFrame(playbackRafRef.current);
      playbackRafRef.current = null;
      playbackFrameRef.current = null;
      return;
    }

    const step = (timestamp: number) => {
      if (playback.mode !== "replay" || !playback.isPlaying) return;
      const window = getReplayWindow(replay.events);
      if (!playbackFrameRef.current) playbackFrameRef.current = timestamp;
      const delta = timestamp - playbackFrameRef.current;
      playbackFrameRef.current = timestamp;
      const nextCursor = playback.cursorTime + delta * playback.speed;
      if (nextCursor >= window.end) {
        setPlayback((prev) => ({ ...prev, cursorTime: window.end, isPlaying: false }));
        return;
      }
      setPlayback((prev) => ({ ...prev, cursorTime: nextCursor }));
      playbackRafRef.current = requestAnimationFrame(step);
    };

    playbackRafRef.current = requestAnimationFrame(step);

    return () => {
      if (playbackRafRef.current) cancelAnimationFrame(playbackRafRef.current);
      playbackRafRef.current = null;
      playbackFrameRef.current = null;
    };
  }, [playback.mode, playback.isPlaying, playback.speed, playback.cursorTime, replay.events]);

  const activeTimeline = useMemo(() => {
    if (playback.mode === "replay") return replay.events;
    return feed;
  }, [feed, playback.mode, replay.events]);

  const filteredTimeline = useMemo(() => {
    if (playback.mode !== "replay") return activeTimeline;
    return activeTimeline.filter((event) => event.ts <= playback.cursorTime);
  }, [activeTimeline, playback.cursorTime, playback.mode]);

  const orderedFeed = useMemo(() => {
    if (!filteredTimeline.length) return [];
    return filteredTimeline.slice(-80);
  }, [filteredTimeline]);

  const replayWindow = useMemo(() => getReplayWindow(replay.events), [replay.events]);
  const replayDuration = Math.max(replayWindow.end - replayWindow.start, 0);
  const replayCursor = clamp(
    playback.cursorTime || replayWindow.start,
    replayWindow.start,
    replayWindow.end || replayWindow.start
  );

  const replayCursorLabel = formatDuration(replayCursor - replayWindow.start);
  const replayTotalLabel = formatDuration(replayDuration);

  const replayStateLabel = replay.loading
    ? "리플레이 로딩 중..."
    : replay.error
      ? "리플레이 로딩 실패"
      : replay.events.length
        ? `${replay.runId} (${replay.events.length} events)`
        : "리플레이를 선택하세요.";

  const refreshRuns = useCallback(async () => {
    try {
      const res = await fetch("/api/runs");
      if (!res.ok) throw new Error("load_failed");
      const data = (await res.json()) as { runs?: { runId: string; updatedAt: number }[] };
      setReplay((prev) => ({ ...prev, runs: data.runs || [] }));
    } catch {
      setReplay((prev) => ({ ...prev, runs: [] }));
    }
  }, []);

  const loadReplay = useCallback(async (runId: string) => {
    if (!runId) return;
    setReplay((prev) => ({ ...prev, loading: true, error: null, runId }));
    try {
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/events`);
      if (!res.ok) throw new Error("load_failed");
      const data = (await res.json()) as { runId: string; events?: FeedEvent[] };
      const events = (data.events || [])
        .map((item) => normalizeEvent(item))
        .filter(Boolean) as FeedEvent[];
      events.sort((a, b) => a.ts - b.ts);
      const firstTs = events[0]?.ts || 0;
      const lastTs = events[events.length - 1]?.ts || firstTs;
      setReplay((prev) => ({
        ...prev,
        runId: data.runId,
        events,
        loading: false,
        error: null
      }));
      setPlayback((prev) => ({
        ...prev,
        mode: "replay",
        isPlaying: false,
        cursorTime: lastTs || firstTs
      }));
    } catch {
      setReplay((prev) => ({ ...prev, loading: false, error: "load_failed", events: [] }));
    }
  }, []);

  return {
    playback,
    setPlayback,
    replay,
    setReplay,
    orderedFeed,
    replayWindow,
    replayDuration,
    replayCursorLabel,
    replayTotalLabel,
    replayStateLabel,
    refreshRuns,
    loadReplay
  };
}
