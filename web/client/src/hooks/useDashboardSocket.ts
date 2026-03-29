import { useCallback, useEffect, useRef, useState } from "react";
import type { AppState, AgentChatMessage, FeedEvent } from "../types";
import { MAX_FEED_ITEMS } from "../constants";
import { buildWsUrl, getBackendHttpBase, normalizeEvent } from "../utils";

const SAVED_STATES = {
  idle: "idle",
  saved: "saved"
} as const;

type SaveState = (typeof SAVED_STATES)[keyof typeof SAVED_STATES];

type UseDashboardSocketArgs = {
  selectedAgentId: string | null;
  onSelectedAgentCleared: () => void;
  onAgentSaveState?: (state: SaveState) => void;
  onConnected?: () => void;
  onTeamFileUpdated?: (payload: { name: string; updatedAt: number; updatedBy: string }) => void;
  onAgentError?: (payload: { action?: string; message: string }) => void;
};

export function useDashboardSocket({
  selectedAgentId,
  onSelectedAgentCleared,
  onAgentSaveState,
  onConnected,
  onTeamFileUpdated,
  onAgentError
}: UseDashboardSocketArgs) {
  const [appState, setAppState] = useState<AppState | null>(null);
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [connectionState, setConnectionState] = useState("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const fallbackPollRef = useRef<number | null>(null);
  const fallbackModeRef = useRef(false);
  const selectedAgentIdRef = useRef<string | null>(null);

  useEffect(() => {
    selectedAgentIdRef.current = selectedAgentId;
  }, [selectedAgentId]);

  useEffect(() => {
    const base = getBackendHttpBase();
    const toState = (bots: any[]): AppState => {
      const now = Date.now();
      const agents = (bots || []).map((bot) => ({
        id: String(bot.id || ""),
        name: String(bot.name || bot.id || "bot"),
        title: String(bot.role || ""),
        state: "idle",
        queue: 0,
        inbox: 0,
        retries: 0,
        failures: 0,
        lastAction: now,
        lastActionText: "standby",
      }));
      const agentConfigs = Object.fromEntries(
        (bots || []).map((bot) => [
          String(bot.id || ""),
          {
            model: String(bot.model || ""),
            systemPrompt: "",
            avatarUrl: "",
            enabled: true,
            temperature: null,
          },
        ]),
      );
      return {
        running: false,
        approvalGate: false,
        pendingApproval: null,
        agents,
        feed: [],
        agentConfigs,
        agentChats: {},
        seedText: "",
        mode: "nanobot",
        runId: "",
        now,
      };
    };
    const fetchFallbackState = async () => {
      try {
        const res = await fetch(`${base}/api/bots`);
        if (!res.ok) return;
        const data = await res.json();
        const next = toState(Array.isArray(data?.bots) ? data.bots : []);
        setAppState(next);
        setFeed([]);
      } catch {
        // noop
      }
    };
    const enableFallback = () => {
      if (fallbackModeRef.current) return;
      fallbackModeRef.current = true;
      setConnectionState("connected");
      fetchFallbackState().catch(() => undefined);
      fallbackPollRef.current = window.setInterval(() => {
        fetchFallbackState().catch(() => undefined);
      }, 3000);
    };

    const ws = new WebSocket(buildWsUrl());
    wsRef.current = ws;
    setConnectionState("connecting");

    const wsOpenGuard = window.setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) enableFallback();
    }, 1200);

    ws.onopen = () => {
      window.clearTimeout(wsOpenGuard);
      if (fallbackPollRef.current) {
        window.clearInterval(fallbackPollRef.current);
        fallbackPollRef.current = null;
      }
      fallbackModeRef.current = false;
      setConnectionState("connected");
      onConnected?.();
    };
    ws.onclose = () => {
      window.clearTimeout(wsOpenGuard);
      enableFallback();
    };
    ws.onerror = () => {
      window.clearTimeout(wsOpenGuard);
      enableFallback();
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data as string);
        if (message.type === "state") {
          const nextState = message.payload as AppState;
          const normalizedFeed = (nextState.feed || [])
            .map((item) => normalizeEvent(item))
            .filter(Boolean) as FeedEvent[];
          normalizedFeed.sort((a, b) => a.ts - b.ts);
          setAppState(nextState);
          setFeed(normalizedFeed);
          if (nextState.agents && nextState.agents.length) {
            const currentSelected = selectedAgentIdRef.current;
            const selectedStillExists = currentSelected
              ? nextState.agents.some((agent) => agent.id === currentSelected)
              : false;
            if (!selectedStillExists) onSelectedAgentCleared();
          }
          return;
        }
        if (message.type === "event") {
          const item = normalizeEvent(message.payload) as FeedEvent | null;
          if (!item) return;
          setFeed((prev) => {
            if (prev.find((existing) => existing.id === item.id)) return prev;
            const next = [...prev, item].sort((a, b) => a.ts - b.ts);
            if (next.length > MAX_FEED_ITEMS * 2) {
              return next.slice(next.length - MAX_FEED_ITEMS * 2);
            }
            return next;
          });
          return;
        }
        if (message.type === "agentConfig.current" || message.type === "agentConfig.updated") {
          if (message.payload?.agentId && message.payload?.config) {
            setAppState((prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                agentConfigs: {
                  ...prev.agentConfigs,
                  [message.payload.agentId]: message.payload.config
                }
              };
            });
            if (message.payload.agentId === selectedAgentIdRef.current) {
              onAgentSaveState?.(message.type === "agentConfig.updated" ? SAVED_STATES.saved : SAVED_STATES.idle);
            }
          }
          return;
        }
        if (message.type === "agentChat.append") {
          if (message.payload?.agentId && message.payload?.message) {
            setAppState((prev) => {
              if (!prev) return prev;
              const agentId = message.payload.agentId as string;
              const messageItem = message.payload.message as AgentChatMessage;
              const existing = prev.agentChats?.[agentId] ? prev.agentChats[agentId].slice() : [];
              if (!existing.find((item) => item.id === messageItem.id)) existing.push(messageItem);
              return {
                ...prev,
                agentChats: {
                  ...prev.agentChats,
                  [agentId]: existing
                }
              };
            });
          }
        }
        if (message.type === "team.file.updated") {
          const fileName = String(message.payload?.name || message.payload?.path || "");
          if (fileName) {
            onTeamFileUpdated?.({
              name: fileName,
              updatedAt: Number(message.payload.updatedAt) || Date.now(),
              updatedBy: String(message.payload.updatedBy || "")
            });
          }
          return;
        }
        if (message.type === "agent.error") {
          const errorMessage =
            typeof message.payload?.message === "string" && message.payload.message.trim()
              ? message.payload.message.trim()
              : "에이전트 작업 중 오류가 발생했습니다.";
          onAgentError?.({
            action: typeof message.payload?.action === "string" ? message.payload.action : undefined,
            message: errorMessage
          });
        }
      } catch {
        // ignore malformed payloads
      }
    };

    return () => {
      window.clearTimeout(wsOpenGuard);
      if (fallbackPollRef.current) {
        window.clearInterval(fallbackPollRef.current);
        fallbackPollRef.current = null;
      }
      ws.close();
    };
  }, [onAgentSaveState, onConnected, onSelectedAgentCleared, onTeamFileUpdated, onAgentError]);

  const sendWs = useCallback((payload: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
      return true;
    }
    const message = payload as Record<string, unknown>;
    const type = String(message.type || "");
    const base = getBackendHttpBase();
    if (type === "run.create") {
      const teamId = String(message.teamId || "");
      const mission = String(message.mission || "").trim() || "Run mission";
      if (teamId) {
        fetch(`${base}/api/teams/${encodeURIComponent(teamId)}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: mission }),
        }).catch(() => undefined);
      }
      return true;
    }
    if (type === "agentConfig.save") {
      const agentId = String(message.agentId || "");
      const config = (message.config || {}) as Record<string, unknown>;
      if (agentId) {
        fetch(`${base}/api/bots/${encodeURIComponent(agentId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: config.model || "",
          }),
        }).catch(() => undefined);
      }
      return true;
    }
    if (type === "team.select" || type === "run.select" || type === "agentConfig.get") {
      return true;
    }
    return false;
  }, []);

  return { appState, setAppState, feed, connectionState, sendWs };
}
