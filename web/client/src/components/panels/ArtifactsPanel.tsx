import { useEffect, useMemo, useState } from "react";
import type { Agent, AgentArtifact } from "../../types";
import { formatTime } from "../../utils";
import { MarkdownLite } from "../common/MarkdownLite";

type ArtifactsPanelProps = {
  title: string;
  subtitle: string;
  agents: Agent[];
  selectedAgentId: string | null;
  artifactsByAgent?: Record<string, AgentArtifact[]>;
};

type KindFilter = "all" | "tool_output" | "attachment" | "diff" | "snapshot";
type ArtifactTypeFilter = "all" | "code" | "doc" | "image";
type TimeFilter = "all" | "1h" | "24h" | "7d";

const CODE_EXTENSIONS = new Set([
  "js",
  "jsx",
  "ts",
  "tsx",
  "py",
  "go",
  "rs",
  "java",
  "kt",
  "c",
  "cc",
  "cpp",
  "h",
  "hpp",
  "cs",
  "php",
  "rb",
  "swift",
  "scala",
  "sql",
  "sh",
  "yaml",
  "yml",
  "toml",
  "json",
  "xml",
  "css",
  "scss",
  "less",
  "html",
]);

const DOC_EXTENSIONS = new Set(["md", "mdx", "txt", "pdf", "rtf", "doc", "docx"]);
const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "gif", "webp", "svg"]);

function getExtension(value?: string) {
  if (!value) return "";
  const cleaned = value.split("?")[0];
  const index = cleaned.lastIndexOf(".");
  if (index < 0 || index === cleaned.length - 1) return "";
  return cleaned.slice(index + 1).toLowerCase();
}

function getArtifactType(item: AgentArtifact): "code" | "doc" | "image" {
  const mime = String(item.mime || "").toLowerCase();
  if (mime.startsWith("image/")) return "image";
  if (mime.includes("markdown") || mime.includes("pdf") || mime.includes("text/html")) return "doc";
  if (mime.includes("json") || mime.includes("xml")) return "code";

  const ext = getExtension(item.filename || item.path || item.url);
  if (IMAGE_EXTENSIONS.has(ext)) return "image";
  if (CODE_EXTENSIONS.has(ext)) return "code";
  if (DOC_EXTENSIONS.has(ext)) return "doc";

  const text = String(item.text || "");
  if (/diff --git|^@@|```|function\s+\w+|class\s+\w+/m.test(text)) return "code";
  return "doc";
}

export function ArtifactsPanel({
  title,
  subtitle,
  agents,
  selectedAgentId,
  artifactsByAgent,
}: ArtifactsPanelProps) {
  const [agentFilter, setAgentFilter] = useState<string>("all");
  const [kindFilter, setKindFilter] = useState<KindFilter>("all");
  const [artifactTypeFilter, setArtifactTypeFilter] =
    useState<ArtifactTypeFilter>("all");
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [query, setQuery] = useState("");

  const handleDownload = (item: AgentArtifact) => {
    const fallbackName = item.filename || item.title.replace(/\s+/g, "_").toLowerCase() || "artifact.txt";
    if (item.url) {
      window.open(item.url, "_blank", "noopener,noreferrer");
      return;
    }
    if (!item.text) return;
    const mime = item.mime || "text/plain;charset=utf-8";
    const blob = new Blob([item.text], { type: mime });
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = fallbackName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  };

  useEffect(() => {
    if (selectedAgentId) {
      setAgentFilter(selectedAgentId);
    }
  }, [selectedAgentId]);

  const artifactRows = useMemo(() => {
    const source = artifactsByAgent || {};
    const rows: AgentArtifact[] = [];
    Object.entries(source).forEach(([agentId, artifacts]) => {
      (artifacts || []).forEach((artifact) => {
        rows.push({
          ...artifact,
          agentId,
          createdAt: Number(artifact.createdAt) || Date.now(),
        });
      });
    });
    rows.sort((a, b) => b.createdAt - a.createdAt);
    return rows;
  }, [artifactsByAgent]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const now = Date.now();
    const minTs =
      timeFilter === "1h"
        ? now - 60 * 60 * 1000
        : timeFilter === "24h"
          ? now - 24 * 60 * 60 * 1000
          : timeFilter === "7d"
            ? now - 7 * 24 * 60 * 60 * 1000
            : 0;
    return artifactRows.filter((item) => {
      if (agentFilter !== "all" && item.agentId !== agentFilter) return false;
      if (kindFilter !== "all" && item.kind !== kindFilter) return false;
      if (artifactTypeFilter !== "all" && getArtifactType(item) !== artifactTypeFilter) return false;
      if (minTs > 0 && item.createdAt < minTs) return false;
      if (normalizedQuery) {
        const searchTarget = [
          item.title,
          item.tool,
          item.filename,
          item.path,
          item.mime,
          item.text,
          item.status,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!searchTarget.includes(normalizedQuery)) return false;
      }
      return true;
    });
  }, [artifactRows, agentFilter, kindFilter, artifactTypeFilter, timeFilter, query]);

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">
          ARTIFACTS
        </span>
      </div>

      <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <select
          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          value={agentFilter}
          onChange={(event) => setAgentFilter(event.target.value)}
        >
          <option value="all">전체 에이전트</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          value={kindFilter}
          onChange={(event) => setKindFilter(event.target.value as KindFilter)}
        >
          <option value="all">전체 타입</option>
          <option value="tool_output">툴 출력</option>
          <option value="attachment">첨부 파일</option>
          <option value="diff">Diff</option>
          <option value="snapshot">Snapshot</option>
        </select>
        <select
          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          value={artifactTypeFilter}
          onChange={(event) =>
            setArtifactTypeFilter(event.target.value as ArtifactTypeFilter)
          }
        >
          <option value="all">전체 뷰 타입</option>
          <option value="code">Code</option>
          <option value="doc">Doc</option>
          <option value="image">Image</option>
        </select>
        <input
          className="min-w-[200px] flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          placeholder="검색(제목/툴/파일/내용)"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select
          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          value={timeFilter}
          onChange={(event) => setTimeFilter(event.target.value as TimeFilter)}
        >
          <option value="all">전체 기간</option>
          <option value="1h">최근 1시간</option>
          <option value="24h">최근 24시간</option>
          <option value="7d">최근 7일</option>
        </select>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        {filtered.length === 0 ? (
          <div className="text-sm text-slate-500">표시할 아티팩트가 없습니다.</div>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {filtered.map((item) => {
              const agentName = agents.find((agent) => agent.id === item.agentId)?.name || item.agentId;
              const artifactType = getArtifactType(item);
              return (
                <li key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-800">{item.title}</div>
                    <div className="text-[11px] text-slate-500">{formatTime(item.createdAt)}</div>
                  </div>
                  <div className="mb-1 text-xs text-slate-500">
                    {agentName} · {item.kind}
                    {item.status ? ` · ${item.status}` : ""}
                    {item.tool ? ` · ${item.tool}` : ""}
                    {` · ${artifactType.toUpperCase()}`}
                  </div>
                  <div className="mb-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                      onClick={() => handleDownload(item)}
                      disabled={!item.url && !item.text}
                    >
                      다운로드
                    </button>
                  </div>
                  {artifactType === "image" && item.url ? (
                    <div className="mb-2">
                      <img
                        src={item.url}
                        alt={item.filename || item.title}
                        className="max-h-64 rounded-md border border-slate-200 bg-white object-contain"
                      />
                    </div>
                  ) : null}
                  {item.text ? (
                    artifactType === "code" ? (
                      <pre className="m-0 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-2 font-mono text-xs text-slate-800">
                        {item.text}
                      </pre>
                    ) : (
                      <div className="max-h-56 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-700">
                        <MarkdownLite text={item.text} className="space-y-1" />
                      </div>
                    )
                  ) : null}
                  {item.kind === "attachment" ? (
                    <div className="mt-1 text-xs text-slate-600">
                      {item.filename ? <div>파일: {item.filename}</div> : null}
                      {item.path ? <div>경로: {item.path}</div> : null}
                      {item.url ? (
                        <a
                          className="text-blue-700 underline"
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          첨부 열기
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
