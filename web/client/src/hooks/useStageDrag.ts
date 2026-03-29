import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { Agent, DragState } from "../types";

type UseStageDragOptions = {
  storageKey?: string;
};

function readLayoutFromStorage(storageKey: string) {
  if (typeof window === "undefined") return null;
  if (!storageKey) return null;
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const positions = parsed?.positions && typeof parsed.positions === "object" ? parsed.positions : null;
    const viewport = parsed?.viewport && typeof parsed.viewport === "object" ? parsed.viewport : null;
    if (!positions || !viewport) return null;

    const cleanPositions: Record<string, { x: number; y: number }> = {};
    Object.entries(positions).forEach(([id, pos]) => {
      const x = Number((pos as any)?.x);
      const y = Number((pos as any)?.y);
      if (!id) return;
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      cleanPositions[id] = { x, y };
    });

    const vx = Number((viewport as any)?.x);
    const vy = Number((viewport as any)?.y);
    if (!Number.isFinite(vx) || !Number.isFinite(vy)) return null;

    return { positions: cleanPositions, viewport: { x: vx, y: vy } };
  } catch {
    return null;
  }
}

function writeLayoutToStorage(
  storageKey: string,
  layout: { positions: Record<string, { x: number; y: number }>; viewport: { x: number; y: number } },
) {
  if (typeof window === "undefined") return;
  if (!storageKey) return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(layout));
  } catch {
    // ignore quota / privacy mode errors
  }
}

export function useStageDrag(agents: Agent[] | undefined, options: UseStageDragOptions = {}) {
  const initialLayout =
    options.storageKey ? readLayoutFromStorage(options.storageKey) : null;
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>(
    () => initialLayout?.positions ?? {},
  );
  const [viewport, setViewport] = useState<{ x: number; y: number }>(
    () => initialLayout?.viewport ?? { x: 0, y: 0 },
  );
  const stageRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const viewportRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const panRef = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const storageKeyRef = useRef<string>(options.storageKey || "");

  useEffect(() => {
    const nextKey = options.storageKey || "";
    if (nextKey === storageKeyRef.current) return;
    storageKeyRef.current = nextKey;
    const stored = nextKey ? readLayoutFromStorage(nextKey) : null;
    if (stored) {
      setPositions(stored.positions);
      setViewport(stored.viewport);
    } else {
      setPositions({});
      setViewport({ x: 0, y: 0 });
    }
  }, [options.storageKey]);

  useEffect(() => {
    if (!agents?.length) return;
    setPositions((prev) => {
      const next = { ...prev };
      const cols = 3;
      const gapX = 180;
      const gapY = 150;
      const startX = 60;
      const startY = 60;

      agents.forEach((agent, index) => {
        if (!next[agent.id]) {
          const col = index % cols;
          const row = Math.floor(index / cols);
          next[agent.id] = { x: startX + col * gapX, y: startY + row * gapY };
        }
      });
      return next;
    });
  }, [agents]);

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => {
    const key = storageKeyRef.current;
    if (!key) return;
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      writeLayoutToStorage(key, { positions, viewport });
      saveTimerRef.current = null;
    }, 250);
  }, [positions, viewport]);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      if (dragRef.current && stageRef.current) {
        const { id, offsetX, offsetY } = dragRef.current;
        const rect = stageRef.current.getBoundingClientRect();
        const nextX = event.clientX - rect.left - offsetX - viewportRef.current.x;
        const nextY = event.clientY - rect.top - offsetY - viewportRef.current.y;
        const clampX = Math.max(20, Math.min(rect.width - 110, nextX));
        const clampY = Math.max(20, Math.min(rect.height - 110, nextY));
        setPositions((prev) => ({ ...prev, [id]: { x: clampX, y: clampY } }));
        return;
      }

      if (panRef.current) {
        const dx = event.clientX - panRef.current.startX;
        const dy = event.clientY - panRef.current.startY;
        setViewport({
          x: panRef.current.originX + dx,
          y: panRef.current.originY + dy,
        });
      }
    };

    const handlePointerUp = () => {
      dragRef.current = null;
      panRef.current = null;
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, []);

  const handlePointerDown = (agentId: string, event: ReactPointerEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    const rect = (event.currentTarget as HTMLButtonElement).getBoundingClientRect();
    dragRef.current = {
      id: agentId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top
    };
  };

  const handleStagePanStart = (event: ReactPointerEvent<HTMLDivElement>) => {
    panRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: viewportRef.current.x,
      originY: viewportRef.current.y,
    };
  };

  const setAgentPosition = (agentId: string, x: number, y: number) => {
    setPositions((prev) => ({ ...prev, [agentId]: { x, y } }));
  };

  return { stageRef, positions, viewport, handlePointerDown, handleStagePanStart, setAgentPosition };
}
