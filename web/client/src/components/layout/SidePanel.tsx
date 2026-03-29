import type { ReactNode } from "react";
import type { TabKey } from "../../types";

type SidePanelProps = {
  activeTab: TabKey | null;
  children: ReactNode;
  onResizeStart: (event: React.PointerEvent<HTMLButtonElement>) => void;
};

export function SidePanel({ activeTab, children, onResizeStart }: SidePanelProps) {
  if (!activeTab) return null;
  return (
    <aside className="relative flex min-h-0 flex-col border-r border-slate-300/70 bg-slate-50 p-3">
      <button
        type="button"
        onPointerDown={onResizeStart}
        className="absolute right-0 top-0 h-full w-1.5 translate-x-1/2 cursor-col-resize bg-transparent max-[900px]:hidden"
        aria-label="사이드 패널 너비 조절"
      />
      {children}
    </aside>
  );
}
