import { useMemo, useState } from "react";
import {
  LuChevronDown,
  LuChevronRight,
  LuCirclePlay,
  LuFolderKanban,
  LuListTodo,
  LuMessageSquare,
  LuPanelLeftClose,
  LuPanelLeftOpen,
  LuPlus,
  LuPlug,
  LuSparkles,
  LuUsers,
} from "react-icons/lu";
import type { TabKey, TeamInfo } from "../../types";

type RailTab = { key: TabKey; label: string };

type RailTabsProps = {
  tabs: RailTab[];
  activeTab: TabKey | null;
  collapsed: boolean;
  teams: TeamInfo[];
  selectedTeamId: string;
  onSelectTeam: (teamId: string) => void;
  onOpenCreateTeam: () => void;
  onToggleCollapsed: () => void;
  onToggleTab: (tab: TabKey) => void;
};

const TAB_ICONS: Record<TabKey, JSX.Element> = {
  messages: <LuMessageSquare size={18} />,
  agentList: <LuUsers size={18} />,
  runtime: <LuCirclePlay size={18} />,
  mcp: <LuPlug size={18} />,
  skills: <LuSparkles size={18} />,
  tasks: <LuListTodo size={18} />,
  teamFiles: <LuFolderKanban size={18} />,
};

export function RailTabs({
  tabs,
  activeTab,
  collapsed,
  teams,
  selectedTeamId,
  onSelectTeam,
  onOpenCreateTeam,
  onToggleCollapsed,
  onToggleTab,
}: RailTabsProps) {
  const [teamMenuOpen, setTeamMenuOpen] = useState(false);

  const selectedTeam = teams.find((team) => team.id === selectedTeamId) ?? teams[0];

  const currentTeamShort = useMemo(
    () => (selectedTeam?.name || "Team").replace(/\s*team/i, "").trim() || "Team",
    [selectedTeam],
  );

  return (
    <nav
      className={`relative flex min-h-0 flex-col gap-3 border-r border-slate-300/70 bg-gray-100 p-2.5 ${collapsed ? "items-center" : ""}`}
      aria-label="탭 선택"
    >
      <div className="relative w-full">
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-slate-800 hover:bg-slate-200 cursor-pointer"
          onClick={() => setTeamMenuOpen((v) => !v)}
          title={selectedTeam?.name || "팀 선택"}
        >
          <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-slate-200">
            <LuUsers size={18} />
          </span>
          {!collapsed && (
            <>
              <span className="flex-1 truncate text-left text-sm font-bold">
                {selectedTeam?.name || "팀 선택"}
              </span>
              <LuChevronDown size={14} />
            </>
          )}
        </button>

        {teamMenuOpen && (
          <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-20 flex flex-col gap-1 rounded-xl border border-slate-300/80 bg-white p-1.5">
            {teams.map((team) => (
              <button
                key={team.id}
                type="button"
                className={`rounded-lg px-2 py-1.5 text-left text-xs font-semibold text-gray-700 shadow-none ${
                  team.id === selectedTeamId
                    ? "bg-blue-50"
                    : "bg-transparent hover:bg-slate-50"
                }`}
                onClick={() => {
                  onSelectTeam(team.id);
                  setTeamMenuOpen(false);
                }}
              >
                {team.name}
              </button>
            ))}

            <div className="my-1 h-px bg-slate-200" />
            <button
              type="button"
              className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-left text-xs font-semibold text-blue-700 hover:bg-blue-50"
              onClick={() => {
                setTeamMenuOpen(false);
                onOpenCreateTeam();
              }}
            >
              <LuPlus size={14} />
              + 팀 생성하기
            </button>
          </div>
        )}

        {collapsed ? (
          <div className="mt-1 text-center text-[11px] text-gray-500">
            {currentTeamShort.slice(0, 2)}
          </div>
        ) : null}
      </div>

      <div className="flex min-h-0 w-full flex-col gap-2">
        {tabs.map((tab) => {
          const isActive = tab.key === activeTab;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onToggleTab(tab.key)}
              aria-pressed={isActive}
              title={tab.label}
              className={`flex w-full items-center gap-1 rounded-lg px-1  text-sm font-light transition-colors cursor-pointer hover:bg-slate-200 ${
                collapsed ? "justify-center" : "justify-start"
              } ${isActive ? "bg-gray-200 text-gray-800" : " text-gray-500"}`}
            >
              <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg`}>
                {TAB_ICONS[tab.key]}
              </span>
              {!collapsed && <span className="font-bold">{tab.label}</span>}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        className="mt-auto flex w-full items-center justify-center gap-1 rounded-lg border border-slate-300/80 bg-white px-2 py-2 text-slate-700 shadow-none"
        onClick={onToggleCollapsed}
        title={collapsed ? "레일 펼치기" : "레일 접기"}
      >
        {collapsed ? <LuPanelLeftOpen size={18} /> : <LuPanelLeftClose size={18} />}
        {!collapsed && <span className="text-xs font-semibold">접기</span>}
        {collapsed && <LuChevronRight size={12} />}
      </button>
    </nav>
  );
}
