import { useEffect, useMemo, useState } from "react";
import { getBackendHttpBase } from "../../utils";

type TeamFilesPanelProps = {
  title: string;
  subtitle: string;
  selectedTeamId: string;
  selectedFile: string;
  onSelectFile: (name: string) => void;
};

type TreeNode = { name: string; path: string; isFile: boolean; children: TreeNode[] };

function buildTree(filePaths: string[], dirPaths: string[]): TreeNode[] {
  const root: TreeNode[] = [];
  const upsert = (nodes: TreeNode[], name: string, path: string, isFile: boolean) => {
    let found = nodes.find((n) => n.name === name);
    if (!found) {
      found = { name, path, isFile, children: [] };
      nodes.push(found);
    }
    if (isFile) found.isFile = true;
    return found;
  };

  for (const p of dirPaths) {
    const parts = p.split("/").filter(Boolean);
    let nodes = root;
    let acc = "";
    parts.forEach((part) => {
      acc = acc ? `${acc}/${part}` : part;
      const node = upsert(nodes, part, acc, false);
      nodes = node.children;
    });
  }

  for (const p of filePaths) {
    const parts = p.split("/").filter(Boolean);
    let nodes = root;
    let acc = "";
    parts.forEach((part, idx) => {
      acc = acc ? `${acc}/${part}` : part;
      const isFile = idx === parts.length - 1;
      const node = upsert(nodes, part, acc, isFile);
      nodes = node.children;
    });
  }

  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => Number(a.isFile) - Number(b.isFile) || a.name.localeCompare(b.name));
    nodes.forEach((n) => sort(n.children));
  };
  sort(root);
  return root;
}

function pickDefaultFile(filePaths: string[]) {
  if (!filePaths.length) return "";
  const priority = [
    "docs/PROJECT.md",
    "docs/AGENTS.md",
    "docs/RULES.md",
    "docs/DOMAIN.md",
    "docs/TASKS.md",
  ];
  for (const path of priority) {
    if (filePaths.includes(path)) return path;
  }
  const markdownFirst = filePaths.find((item) => item.toLowerCase().endsWith(".md"));
  return markdownFirst || filePaths[0];
}

export function TeamFilesPanel({ title, subtitle, selectedTeamId, selectedFile, onSelectFile }: TeamFilesPanelProps) {
  const base = getBackendHttpBase();
  const [files, setFiles] = useState<string[]>([]);
  const [dirs, setDirs] = useState<string[]>([]);
  const [openDirs, setOpenDirs] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");

  const loadFiles = async () => {
    try {
      const res = await fetch(`${base}/api/team/files?teamId=${encodeURIComponent(selectedTeamId)}`);
      if (!res.ok) throw new Error(`HTTP_${res.status}`);
      const data = await res.json();
      const list = Array.isArray(data.files) ? data.files : [];
      const dirList = Array.isArray(data.dirs) ? data.dirs : [];
      const defaultFile = pickDefaultFile(list);
      setFiles(list);
      setDirs(dirList);
      if (!selectedFile && defaultFile) onSelectFile(defaultFile);
      if (selectedFile && !list.includes(selectedFile)) onSelectFile(defaultFile || "");
      setError("");
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`파일 목록 로딩 실패 (${reason})`);
    }
  };

  useEffect(() => {
    loadFiles().catch(() => undefined);
  }, [selectedTeamId]);

  const tree = useMemo(() => buildTree(files, dirs), [files, dirs]);

  const createFile = async () => {
    const path = window.prompt("새 파일 경로 (예: docs/NOTES.md 또는 src/app.ts)");
    if (!path) return;
    const res = await fetch(`${base}/api/team/file?teamId=${encodeURIComponent(selectedTeamId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path.trim(), content: "" }),
    });
    if (!res.ok) return setError(`파일 생성 실패 (HTTP_${res.status})`);
    await loadFiles();
    onSelectFile(path.trim());
  };

  const renameFile = async () => {
    if (!selectedFile) return;
    const newPath = window.prompt("새 경로", selectedFile);
    if (!newPath || newPath === selectedFile) return;
    const res = await fetch(`${base}/api/team/file/rename?teamId=${encodeURIComponent(selectedTeamId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ oldPath: selectedFile, newPath: newPath.trim() }),
    });
    if (!res.ok) return setError(`이름 변경 실패 (HTTP_${res.status})`);
    await loadFiles();
    onSelectFile(newPath.trim());
  };

  const deleteFile = async () => {
    if (!selectedFile) return;
    if (!window.confirm(`${selectedFile} 파일을 삭제할까?`)) return;
    const res = await fetch(`${base}/api/team/file?teamId=${encodeURIComponent(selectedTeamId)}&path=${encodeURIComponent(selectedFile)}`, {
      method: "DELETE",
    });
    if (!res.ok) return setError(`파일 삭제 실패 (HTTP_${res.status})`);
    await loadFiles();
  };

  const renderNode = (node: TreeNode, depth: number): JSX.Element => {
    if (node.isFile) {
      return (
        <button
          key={node.path}
          type="button"
          className={`block w-full rounded-md px-2 py-1.5 text-left text-sm ${selectedFile === node.path ? "bg-blue-50 font-semibold text-blue-700" : "hover:bg-slate-50"}`}
          style={{ paddingLeft: `${8 + depth * 14}px` }}
          onClick={() => onSelectFile(node.path)}
        >
          📄 {node.name}
        </button>
      );
    }

    const opened = openDirs[node.path] ?? true;
    return (
      <div key={node.path}>
        <button
          type="button"
          className="block w-full rounded-md px-2 py-1.5 text-left text-sm font-semibold hover:bg-slate-50"
          style={{ paddingLeft: `${8 + depth * 14}px` }}
          onClick={() => setOpenDirs((prev) => ({ ...prev, [node.path]: !opened }))}
        >
          {opened ? "📂" : "📁"} {node.name}
        </button>
        {opened ? node.children.map((child) => renderNode(child, depth + 1)) : null}
      </div>
    );
  };

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">EXPLORER</span>
      </div>

      <div className="flex gap-2">
        <button className="rounded-md border px-2 py-1 text-xs" onClick={createFile}>+ 파일</button>
        <button
          className="rounded-md border px-2 py-1 text-xs"
          onClick={async () => {
            const dirPath = window.prompt("새 폴더 경로 (예: docs/specs)");
            if (!dirPath) return;
            const res = await fetch(`${base}/api/team/dir?teamId=${encodeURIComponent(selectedTeamId)}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: dirPath.trim() }),
            });
            if (!res.ok) return setError(`폴더 생성 실패 (HTTP_${res.status})`);
            await loadFiles();
            setOpenDirs((prev) => ({ ...prev, [dirPath.trim()]: true }));
          }}
        >
          + 폴더
        </button>
        <button className="rounded-md border px-2 py-1 text-xs" onClick={renameFile} disabled={!selectedFile}>이름변경</button>
        <button className="rounded-md border px-2 py-1 text-xs" onClick={deleteFile} disabled={!selectedFile}>삭제</button>
      </div>

      <div className="rounded-xl border border-slate-300 bg-white p-2">
        <p className="m-0 mb-2 px-1 text-xs font-semibold text-slate-500">
          {selectedTeamId} / workspace 파일 탐색기
        </p>
        <div className="flex max-h-[60vh] flex-col gap-0.5 overflow-auto">
          {tree.map((node) => renderNode(node, 0))}
          {!tree.length ? <div className="px-2 py-4 text-xs text-slate-500">파일이 없어.</div> : null}
        </div>
      </div>

      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">{error}</div> : null}
    </section>
  );
}
