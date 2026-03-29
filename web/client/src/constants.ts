import type { AgentFormState, TabKey } from "./types";

export const DEFAULT_AGENT_FORM: AgentFormState = {
  model: "",
  systemPrompt: "",
  avatarUrl: "",
  enabled: true,
  temperature: ""
};

export const TABS: { key: TabKey; label: string }[] = [
  { key: "messages", label: "메시지" },
  { key: "agentList", label: "에이전트 리스트" },
  { key: "runtime", label: "런타임" },
  { key: "mcp", label: "MCP" },
  { key: "skills", label: "스킬" },
  { key: "tasks", label: "태스크" },
  { key: "teamFiles", label: "파일" }
];

export const PANEL_LABELS: Record<TabKey, { title: string; subtitle: string }> = {
  messages: { title: "Message Center", subtitle: "실시간 팀 메시지와 알림" },
  agentList: { title: "Agent List", subtitle: "이름/상태/실시간 작업내용" },
  runtime: { title: "Runtime", subtitle: "봇 프로세스 실행/채팅/연결" },
  mcp: { title: "MCP", subtitle: "MCP 서버 상태/연결 관리" },
  skills: { title: "Skills", subtitle: "Nanobot 스킬 목록" },
  tasks: { title: "태스크 보드", subtitle: "팀 작업을 상태별로 관리" },
  teamFiles: { title: "파일", subtitle: "팀 폴더 파일 탐색기" }
};

export const MAX_FEED_ITEMS = 200;
