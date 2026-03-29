import { useCallback, useEffect, useRef, useState } from "react";
import { PANEL_LABELS, TABS } from "./constants";
import { useDashboardSocket } from "./hooks/useDashboardSocket";
import { useStageDrag } from "./hooks/useStageDrag";
import type { TabKey, TeamInfo } from "./types";
import { AgentStage } from "./components/stage/AgentStage";
import { RailTabs } from "./components/layout/RailTabs";
import { SidePanel } from "./components/layout/SidePanel";
import { TopBar } from "./components/layout/TopBar";
import { TeamCreateModal } from "./components/layout/TeamCreateModal";
import { AgentListPanel } from "./components/panels/AgentListPanel";
import { MessagesPanel } from "./components/panels/MessagesPanel";
import { TasksPanel } from "./components/panels/TasksPanel";
import { TeamFilesPanel } from "./components/panels/TeamFilesPanel";
import { McpPanel } from "./components/panels/McpPanel";
import { SkillsPanel } from "./components/panels/SkillsPanel";
import { RuntimePanel } from "./components/panels/RuntimePanel";
import { FileWorkspaceStage } from "./components/stage/FileWorkspaceStage";
import { getBackendHttpBase } from "./utils";

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [sidePanelWidth, setSidePanelWidth] = useState(360);
  const sideResizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [selectedTeamFile, setSelectedTeamFile] = useState("");
  const [teams, setTeams] = useState<TeamInfo[]>([
    { id: "default", name: "Default Team" },
  ]);
  const [selectedTeamId, setSelectedTeamId] = useState("default");
  const [teamCreateModalOpen, setTeamCreateModalOpen] = useState(false);
  const [runMissionInput, setRunMissionInput] = useState("");
  const [runOptions, setRunOptions] = useState<
    Array<{ runId: string; mission?: string; updatedAt: number }>
  >([]);

  const clearSelectedAgent = useCallback(() => setSelectedAgentId(null), []);
  const handleTeamFileUpdated = useCallback(
    (_payload: { name: string; updatedAt: number; updatedBy: string; teamId?: string }) => {
      // TeamFilesPanel에서 필요 시 자체적으로 새로고침한다.
    },
    [],
  );

  const { appState, feed, connectionState, sendWs } = useDashboardSocket({
    selectedAgentId,
    onSelectedAgentCleared: clearSelectedAgent,
    onTeamFileUpdated: handleTeamFileUpdated,
  });

  const orderedFeed = feed.slice(-80);

  const { stageRef, positions, viewport, handlePointerDown, handleStagePanStart } =
    useStageDrag(appState?.agents, { storageKey: `atd.stage.${selectedTeamId}` });

  const refreshTeams = useCallback(async () => {
    try {
      const response = await fetch("/api/teams");
      const data = await response.json();
      if (!response.ok || !Array.isArray(data?.teams)) return;
      const nextTeams = data.teams.length
        ? data.teams
        : [{ id: "default", name: "Default Team" }];
      setTeams(nextTeams);
      if (!nextTeams.some((team: TeamInfo) => team.id === selectedTeamId)) {
        setSelectedTeamId(nextTeams[0].id);
      }
    } catch {
      // noop
    }
  }, [selectedTeamId]);

  const refreshRuns = useCallback(async (teamId: string) => {
    try {
      const base = getBackendHttpBase();
      const response = await fetch(
        `${base}/api/runs?teamId=${encodeURIComponent(teamId)}`,
      );
      if (!response.ok) return;
      const data = await response.json();
      const rows = Array.isArray(data?.runs) ? data.runs : [];
      setRunOptions(rows);
    } catch {
      // noop
    }
  }, []);

  useEffect(() => {
    if (connectionState !== "connected") return;
    refreshTeams().catch(() => undefined);
  }, [connectionState, refreshTeams]);

  useEffect(() => {
    if (connectionState !== "connected") return;
    refreshRuns(selectedTeamId).catch(() => undefined);
  }, [connectionState, selectedTeamId, refreshRuns]);

  useEffect(() => {
    if (connectionState !== "connected") return;
    if (!appState?.runId) return;
    refreshRuns(selectedTeamId).catch(() => undefined);
  }, [connectionState, appState?.runId, selectedTeamId, refreshRuns]);

  useEffect(() => {
    if (connectionState !== "connected") return;
    sendWs({ type: "team.select", teamId: selectedTeamId });
  }, [connectionState, selectedTeamId, sendWs]);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      if (!sideResizeRef.current) return;
      const delta = event.clientX - sideResizeRef.current.startX;
      const next = Math.max(
        280,
        Math.min(620, sideResizeRef.current.startWidth + delta),
      );
      setSidePanelWidth(next);
    };
    const handlePointerUp = () => {
      sideResizeRef.current = null;
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, []);

  useEffect(() => {
    setSelectedTeamFile("");
  }, [selectedTeamId]);

  const runStateLabel = appState?.running ? "RUNNING" : "PAUSED";

  const handleCreateRun = useCallback(() => {
    sendWs({
      type: "run.create",
      teamId: selectedTeamId,
      mission: runMissionInput.trim(),
    });
    if (runMissionInput.trim()) setRunMissionInput("");
    window.setTimeout(() => {
      refreshRuns(selectedTeamId).catch(() => undefined);
    }, 300);
  }, [sendWs, selectedTeamId, runMissionInput, refreshRuns]);

  const handleSelectRun = useCallback(
    (runId: string) => {
      if (!runId) return;
      sendWs({ type: "run.select", teamId: selectedTeamId, runId });
      window.setTimeout(() => {
        refreshRuns(selectedTeamId).catch(() => undefined);
      }, 250);
    },
    [sendWs, selectedTeamId, refreshRuns],
  );

  const streamStateLabel =
    connectionState === "connected"
      ? "연결됨"
      : connectionState === "connecting"
        ? "연결 대기 중..."
        : "연결 끊김";

  const streamStateMode =
    connectionState === "connected"
      ? "ready"
      : connectionState === "connecting"
        ? "loading"
        : "error";

  const gridClass = activeTab
    ? railCollapsed
      ? "grid-cols-[72px_var(--side-panel-width)_minmax(420px,1fr)]"
      : "grid-cols-[220px_var(--side-panel-width)_minmax(420px,1fr)]"
    : railCollapsed
      ? "grid-cols-[72px_minmax(420px,1fr)]"
      : "grid-cols-[220px_minmax(420px,1fr)]";

  return (
    <div className="flex h-screen min-h-screen flex-col overflow-hidden">
      <TopBar
        runStateLabel={runStateLabel}
        appState={appState}
        selectedTeamId={selectedTeamId}
        runMissionInput={runMissionInput}
        onRunMissionInputChange={setRunMissionInput}
        onCreateRun={handleCreateRun}
        runOptions={runOptions}
        onSelectRun={handleSelectRun}
      />

      <div
        className={`grid min-h-0 flex-1 gap-0 overflow-hidden max-[900px]:grid-cols-1 ${gridClass}`}
        style={{ ["--side-panel-width" as string]: `${sidePanelWidth}px` }}
      >
        <RailTabs
          tabs={TABS}
          activeTab={activeTab}
          collapsed={railCollapsed}
          teams={teams}
          selectedTeamId={selectedTeamId}
          onSelectTeam={setSelectedTeamId}
          onOpenCreateTeam={() => setTeamCreateModalOpen(true)}
          onToggleCollapsed={() => setRailCollapsed((v) => !v)}
          onToggleTab={(tab) =>
            setActiveTab((prev) => (prev === tab ? null : tab))
          }
        />

        <SidePanel
          activeTab={activeTab}
          onResizeStart={(event) => {
            sideResizeRef.current = {
              startX: event.clientX,
              startWidth: sidePanelWidth,
            };
          }}
        >
          {activeTab === "messages" && (
            <MessagesPanel
              title={PANEL_LABELS[activeTab].title}
              subtitle={PANEL_LABELS[activeTab].subtitle}
              playbackMode="live"
              orderedFeed={orderedFeed}
              streamStateLabel={streamStateLabel}
              streamStateMode={streamStateMode}
            />
          )}

          {activeTab === "agentList" && (
            <AgentListPanel
              title={PANEL_LABELS[activeTab].title}
              subtitle={PANEL_LABELS[activeTab].subtitle}
              selectedAgentId={selectedAgentId}
              onSelectAgent={setSelectedAgentId}
            />
          )}

          {activeTab === "mcp" && (
            <McpPanel
              title={PANEL_LABELS[activeTab].title}
              subtitle={PANEL_LABELS[activeTab].subtitle}
            />
          )}

          {activeTab === "runtime" && (
            <RuntimePanel
              title={PANEL_LABELS[activeTab].title}
              subtitle={PANEL_LABELS[activeTab].subtitle}
              agents={appState?.agents ?? []}
              selectedTeamId={selectedTeamId}
            />
          )}

          {activeTab === "skills" && (
            <SkillsPanel
              title={PANEL_LABELS[activeTab].title}
              subtitle={PANEL_LABELS[activeTab].subtitle}
            />
          )}

          {activeTab === "tasks" && (
            <TasksPanel
              title={PANEL_LABELS[activeTab].title}
              subtitle={PANEL_LABELS[activeTab].subtitle}
              agents={appState?.agents ?? []}
              selectedTeamId={selectedTeamId}
            />
          )}

          {activeTab === "teamFiles" && (
            <TeamFilesPanel
              title={PANEL_LABELS[activeTab].title}
              subtitle={PANEL_LABELS[activeTab].subtitle}
              selectedTeamId={selectedTeamId}
              selectedFile={selectedTeamFile}
              onSelectFile={setSelectedTeamFile}
            />
          )}
        </SidePanel>

        <main className="relative flex min-h-0">
          {activeTab === "teamFiles" ? (
            <FileWorkspaceStage
              teamId={selectedTeamId}
              openFileName={selectedTeamFile || null}
            />
          ) : (
            <AgentStage
              agents={appState?.agents ?? []}
              agentConfigs={appState?.agentConfigs}
              positions={positions}
              viewport={viewport}
              selectedAgentId={selectedAgentId}
              stageRef={stageRef}
              onSelectAgent={setSelectedAgentId}
              onDragStart={handlePointerDown}
              onStagePanStart={handleStagePanStart}
              onTemplateDrop={() => undefined}
              quickAddOpen={false}
              quickAddName=""
              quickAddTitle=""
              onQuickAddNameChange={() => undefined}
              onQuickAddTitleChange={() => undefined}
              onToggleQuickAdd={() => undefined}
              onCloseQuickAdd={() => undefined}
              onCreateAgent={() => undefined}
              showQuickAdd={false}
            />
          )}
        </main>
      </div>

      <TeamCreateModal
        open={teamCreateModalOpen}
        onClose={() => setTeamCreateModalOpen(false)}
        onCreated={() => {
          refreshTeams().catch(() => undefined);
        }}
      />
    </div>
  );
}
