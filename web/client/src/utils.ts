import type { FeedEvent } from "./types";

export function buildWsUrl() {
  const envUrl = import.meta.env.VITE_WS_URL as string | undefined;
  if (envUrl) {
    // normalize loopback host mismatch (localhost vs 127.0.0.1)
    if (window.location.hostname === "localhost") {
      return envUrl.replace("127.0.0.1", "localhost");
    }
    return envUrl;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.hostname}:3001`;
}

export function getBackendHttpBase() {
  // In Vite dev (5173), always use relative path + proxy to avoid CORS issues.
  if (window.location.port === "5173") return "";

  const apiUrl = import.meta.env.VITE_API_URL as string | undefined;
  if (apiUrl) return apiUrl.replace(/\/$/, "");

  const envUrl = import.meta.env.VITE_WS_URL as string | undefined;
  if (envUrl) {
    const httpUrl = envUrl.replace(/^ws:/, "http:").replace(/^wss:/, "https:");
    return httpUrl.replace(/\/$/, "");
  }

  const protocol = window.location.protocol === "https:" ? "https" : "http";
  return `${protocol}://${window.location.hostname}:3001`;
}

export function resolveAssetUrl(src?: string | null) {
  if (!src) return "";
  let normalized = src;
  if (/^\/avatars\/notion-avatar-\d+\.svg$/i.test(normalized)) {
    normalized = normalized.replace(/\.svg$/i, ".png");
  }
  if (/^https?:\/\//i.test(normalized) || /^data:/i.test(normalized)) return normalized;
  if (normalized.startsWith("/")) return `${getBackendHttpBase()}${normalized}`;
  return normalized;
}

export function formatTime(ts: number) {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, "0")}:${d
    .getMinutes()
    .toString()
    .padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}

export function formatDuration(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "00:00";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function normalizeEvent(raw: Partial<FeedEvent> & Record<string, unknown>): FeedEvent | null {
  if (!raw) return null;
  const ts = typeof raw.ts === "number" ? raw.ts : raw.iso ? Date.parse(String(raw.iso)) : Date.now();
  const id = typeof raw.id === "string" && raw.id ? raw.id : `${ts}-${Math.floor(Math.random() * 100000)}`;
  const type = typeof raw.type === "string" ? raw.type : "status";
  const from = typeof raw.from === "string" ? raw.from : undefined;
  const to = typeof raw.to === "string" ? raw.to : undefined;
  const text = typeof raw.text === "string" ? raw.text : undefined;
  const runId = typeof raw.runId === "string" ? raw.runId : undefined;
  const agentId = typeof raw.agentId === "string" ? raw.agentId : null;
  const tool = typeof raw.tool === "string" ? raw.tool : undefined;
  const toolTitle = typeof raw.toolTitle === "string" ? raw.toolTitle : undefined;
  const toolStatus = typeof raw.toolStatus === "string" ? raw.toolStatus : undefined;
  const toolInput = typeof raw.toolInput === "string" ? raw.toolInput : undefined;
  const toolOutput = typeof raw.toolOutput === "string" ? raw.toolOutput : undefined;
  const toolError = typeof raw.toolError === "string" ? raw.toolError : undefined;
  const attachmentCount = Number.isFinite(Number(raw.attachmentCount))
    ? Number(raw.attachmentCount)
    : undefined;
  const sessionID = typeof raw.sessionID === "string" ? raw.sessionID : undefined;
  const messageID = typeof raw.messageID === "string" ? raw.messageID : undefined;
  const partID = typeof raw.partID === "string" ? raw.partID : undefined;
  return {
    id,
    ts,
    iso: raw.iso ? String(raw.iso) : new Date(ts).toISOString(),
    runId,
    type,
    from,
    to,
    text,
    agentId,
    tool,
    toolTitle,
    toolStatus,
    toolInput,
    toolOutput,
    toolError,
    attachmentCount,
    sessionID,
    messageID,
    partID
  };
}

export function getReplayWindow(events: FeedEvent[]) {
  if (!events.length) return { start: 0, end: 0 };
  return { start: events[0].ts, end: events[events.length - 1].ts };
}
