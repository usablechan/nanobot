export type Agent = {
  id: string;
  name: string;
  title: string;
  state:
    | "idle"
    | "running"
    | "done"
    | "blocked"
    | "thinking"
    | "tooling"
    | "waiting"
    | "error"
    | string;
  queue: number;
  inbox: number;
  retries: number;
  failures: number;
  lastAction: number | null;
  lastActionText: string;
  isCustom?: boolean;
};

export type AgentConfig = {
  avatarUrl?: string;
  model?: string;
  systemPrompt?: string;
  enabled?: boolean;
  temperature?: number | null;
};

export type AgentChatMessage = {
  id: string;
  agentId: string;
  role: string;
  text: string;
  ts: number;
};

export type FeedEvent = {
  id: string;
  ts: number;
  iso: string;
  runId?: string;
  type: string;
  from?: string;
  agentId?: string | null;
  to?: string;
  text?: string;
  tool?: string;
  toolTitle?: string;
  toolStatus?: string;
  toolInput?: string;
  toolOutput?: string;
  toolError?: string;
  attachmentCount?: number;
  sessionID?: string;
  messageID?: string;
  partID?: string;
};

export type ApprovalRequest = {
  id: string;
  agentId: string;
  taskId: string;
  text: string;
  kind?: "permission" | "question" | string;
  status: "pending" | "approved" | "rejected";
  createdAt: number;
  resolvedAt?: number | null;
  resolvedBy?: string | null;
  resolution?: "approved" | "rejected" | null;
  source?: string;
  permission?: string;
  patterns?: string[];
  questions?: Array<{
    question?: string;
    options?: Array<{ label?: string }>;
  }>;
  replyMode?: "once" | "always" | "reject" | string;
  answerText?: string;
};

export type AppState = {
  running: boolean;
  approvalGate: boolean;
  pendingApproval: { text?: string; agentId?: string; requestId?: string } | null;
  agents: Agent[];
  feed: FeedEvent[];
  agentConfigs: Record<string, AgentConfig>;
  agentChats: Record<string, AgentChatMessage[]>;
  agentArtifacts?: Record<string, AgentArtifact[]>;
  approvalRequests?: ApprovalRequest[];
  orchestrator?: {
    enabled: boolean;
    tickMs: number;
    maxConcurrentPerAgent: number;
    autoRetry: boolean;
    agents: Record<
      string,
      { activeTaskId: string | null; lastError: string | null; heartbeatAt: number | null }
    >;
  };
  seedText: string;
  mode: string;
  runId: string;
  runMission?: string;
  now: number;
};

export type TabKey =
  | "messages"
  | "agentList"
  | "runtime"
  | "mcp"
  | "skills"
  | "tasks"
  | "teamFiles";

export type AgentTemplate = {
  id: string;
  name: string;
  title: string;
  model: string;
  avatarUrl?: string;
  systemPrompt?: string;
  enabled?: boolean;
  temperature?: number | null;
};

export type DragState = {
  id: string;
  offsetX: number;
  offsetY: number;
};

export type PlaybackMode = "live" | "replay";

export type PlaybackState = {
  mode: PlaybackMode;
  cursorTime: number;
  speed: number;
  isPlaying: boolean;
};

export type ReplayState = {
  runId: string;
  runs: { runId: string; updatedAt: number }[];
  events: FeedEvent[];
  loading: boolean;
  error: string | null;
};

export type AgentFormState = {
  model: string;
  systemPrompt: string;
  avatarUrl: string;
  enabled: boolean;
  temperature: string;
};

export type TeamInfo = {
  id: string;
  name: string;
};

export type TaskItem = {
  id: string;
  title: string;
  description: string;
  status: "todo" | "doing" | "review" | "done" | "blocked";
  priority: string;
  assignee: string;
  createdAt: number;
  updatedAt: number;
  startedAt?: number;
  contextVersion?: number;
  retryCount: number;
  retryLimit: number;
  failureReason?: string;
  lastEvent?: string;
  lastEventAt?: number | null;
  executionMode?: "sim" | "nanobot" | "opencode" | string;
  dispatchedAt?: number;
  bridgeDispatchedAt?: number;
};

export type AgentArtifact = {
  id: string;
  agentId: string;
  kind: "tool_output" | "attachment" | string;
  title: string;
  tool?: string;
  status?: string;
  text?: string;
  mime?: string;
  filename?: string;
  url?: string;
  path?: string;
  sessionID?: string;
  messageID?: string;
  createdAt: number;
};
