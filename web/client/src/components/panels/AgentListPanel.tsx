import { useCallback, useEffect, useMemo, useState } from "react";
import { getBackendHttpBase } from "../../utils";

type AgentListPanelProps = {
  title: string;
  subtitle: string;
  selectedAgentId: string | null;
  onSelectAgent: (agentId: string | null) => void;
};

type BotRecord = {
  id: string;
  name: string;
  role: string;
  description?: string;
  model?: string;
  provider?: string;
  tags?: string[];
  skills?: string[];
  custom_skills?: string[];
  workspace?: string;
  config_path?: string;
};

type BotForm = {
  name: string;
  role: string;
  model: string;
  provider: string;
  description: string;
  tags: string;
  skills: string;
  customSkills: string;
  memorySeed: string;
};

const EMPTY_FORM: BotForm = {
  name: "",
  role: "",
  model: "",
  provider: "",
  description: "",
  tags: "",
  skills: "",
  customSkills: "",
  memorySeed: "",
};

function parseCsv(value: string) {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

function csv(value?: string[]) {
  return Array.isArray(value) ? value.join(", ") : "";
}

function toEditForm(bot: BotRecord): BotForm {
  return {
    name: bot.name || "",
    role: bot.role || "",
    model: bot.model || "",
    provider: bot.provider || "",
    description: bot.description || "",
    tags: csv(bot.tags),
    skills: csv(bot.skills),
    customSkills: csv(bot.custom_skills),
    memorySeed: "",
  };
}

export function AgentListPanel({
  title,
  subtitle,
  selectedAgentId,
  onSelectAgent,
}: AgentListPanelProps) {
  const base = getBackendHttpBase();
  const [bots, setBots] = useState<BotRecord[]>([]);
  const [query, setQuery] = useState("");
  const [createForm, setCreateForm] = useState<BotForm>(EMPTY_FORM);
  const [editForm, setEditForm] = useState<BotForm>(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [submittingCreate, setSubmittingCreate] = useState(false);
  const [submittingEdit, setSubmittingEdit] = useState(false);
  const [error, setError] = useState("");

  const selectedBot = useMemo(
    () => bots.find((b) => b.id === selectedAgentId) || null,
    [bots, selectedAgentId],
  );

  const loadBots = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${base}/api/bots`);
      const data = await res.json();
      if (!res.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      const rows = Array.isArray(data?.bots) ? data.bots : [];
      setBots(rows);
      setError("");
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`봇 목록 조회 실패 (${reason})`);
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    loadBots().catch(() => undefined);
    const timer = setInterval(() => loadBots().catch(() => undefined), 5000);
    return () => clearInterval(timer);
  }, [loadBots]);

  useEffect(() => {
    if (!selectedBot) {
      setEditForm(EMPTY_FORM);
      return;
    }
    setEditForm(toEditForm(selectedBot));
  }, [selectedBot]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = bots
      .filter((bot) => {
        if (!q) return true;
        const target = `${bot.id} ${bot.name} ${bot.role} ${bot.description || ""} ${(bot.tags || []).join(" ")}`.toLowerCase();
        return target.includes(q);
      })
      .sort((a, b) => a.name.localeCompare(b.name));
    return rows;
  }, [bots, query]);

  const createBot = async () => {
    const name = createForm.name.trim();
    const role = createForm.role.trim();
    if (!name || !role || submittingCreate) return;

    setSubmittingCreate(true);
    setError("");
    try {
      const res = await fetch(`${base}/api/bots`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          role,
          model: createForm.model.trim() || undefined,
          provider: createForm.provider.trim() || undefined,
          description: createForm.description,
          tags: parseCsv(createForm.tags),
          skills: parseCsv(createForm.skills),
          custom_skills: parseCsv(createForm.customSkills),
          memory_seed: createForm.memorySeed,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      const createdId = String(data?.bot?.id || "");
      setCreateForm(EMPTY_FORM);
      await loadBots();
      if (createdId) onSelectAgent(createdId);
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`봇 생성 실패 (${reason})`);
    } finally {
      setSubmittingCreate(false);
    }
  };

  const saveBot = async () => {
    if (!selectedBot || submittingEdit) return;
    setSubmittingEdit(true);
    setError("");
    try {
      const res = await fetch(`${base}/api/bots/${encodeURIComponent(selectedBot.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editForm.name.trim(),
          role: editForm.role.trim(),
          model: editForm.model.trim() || null,
          provider: editForm.provider.trim() || null,
          description: editForm.description,
          tags: parseCsv(editForm.tags),
          skills: parseCsv(editForm.skills),
          custom_skills: parseCsv(editForm.customSkills),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await loadBots();
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`봇 저장 실패 (${reason})`);
    } finally {
      setSubmittingEdit(false);
    }
  };

  const deleteBot = async () => {
    if (!selectedBot) return;
    const confirmed = window.confirm(`봇 ${selectedBot.id}를 삭제할까요?`);
    if (!confirmed) return;

    setSubmittingEdit(true);
    setError("");
    try {
      const res = await fetch(
        `${base}/api/bots/${encodeURIComponent(selectedBot.id)}?purge_files=1&force=1`,
        { method: "DELETE" },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      await loadBots();
      onSelectAgent(null);
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`봇 삭제 실패 (${reason})`);
    } finally {
      setSubmittingEdit(false);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700"
          onClick={() => loadBots().catch(() => undefined)}
          disabled={loading}
        >
          새로고침
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <input
          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          placeholder="id/이름/역할/태그 검색"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-2 text-sm font-semibold text-slate-800">새 봇 생성</div>
        <div className="grid gap-2 md:grid-cols-2">
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="이름" value={createForm.name} onChange={(e) => setCreateForm((p) => ({ ...p, name: e.target.value }))} />
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="역할" value={createForm.role} onChange={(e) => setCreateForm((p) => ({ ...p, role: e.target.value }))} />
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="모델(선택)" value={createForm.model} onChange={(e) => setCreateForm((p) => ({ ...p, model: e.target.value }))} />
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="프로바이더(선택)" value={createForm.provider} onChange={(e) => setCreateForm((p) => ({ ...p, provider: e.target.value }))} />
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm md:col-span-2" placeholder="설명" value={createForm.description} onChange={(e) => setCreateForm((p) => ({ ...p, description: e.target.value }))} />
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="tags CSV" value={createForm.tags} onChange={(e) => setCreateForm((p) => ({ ...p, tags: e.target.value }))} />
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="skills CSV" value={createForm.skills} onChange={(e) => setCreateForm((p) => ({ ...p, skills: e.target.value }))} />
          <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm md:col-span-2" placeholder="custom skills CSV" value={createForm.customSkills} onChange={(e) => setCreateForm((p) => ({ ...p, customSkills: e.target.value }))} />
          <textarea className="min-h-[68px] rounded-lg border border-slate-300 px-2 py-1.5 text-sm md:col-span-2" placeholder="memory seed" value={createForm.memorySeed} onChange={(e) => setCreateForm((p) => ({ ...p, memorySeed: e.target.value }))} />
          <button
            type="button"
            className="w-fit rounded-md border border-blue-500 bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white"
            onClick={() => createBot().catch(() => undefined)}
            disabled={submittingCreate}
          >
            {submittingCreate ? "생성 중..." : "Create Bot"}
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        {!filtered.length ? (
          <div className="text-sm text-slate-500">표시할 봇이 없습니다.</div>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {filtered.map((bot) => (
              <li key={bot.id}>
                <button
                  type="button"
                  onClick={() => onSelectAgent(bot.id)}
                  className={`w-full rounded-lg border p-2.5 text-left ${
                    selectedAgentId === bot.id
                      ? "border-blue-400 bg-blue-50"
                      : "border-slate-200 bg-slate-50 hover:bg-slate-100"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <div className="truncate text-sm font-semibold text-slate-800">{bot.name}</div>
                    <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-[11px] text-slate-700">{bot.id}</span>
                  </div>
                  <div className="truncate text-xs text-slate-600">{bot.role || "-"}</div>
                  <div className="mt-1 truncate text-[11px] text-slate-500">
                    {(bot.tags || []).slice(0, 4).join(", ") || "태그 없음"}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selectedBot ? (
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="mb-2 text-sm font-semibold text-slate-800">선택 봇 설정: {selectedBot.id}</div>
          <div className="grid gap-2 md:grid-cols-2">
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="이름" value={editForm.name} onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))} />
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="역할" value={editForm.role} onChange={(e) => setEditForm((p) => ({ ...p, role: e.target.value }))} />
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="모델" value={editForm.model} onChange={(e) => setEditForm((p) => ({ ...p, model: e.target.value }))} />
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="프로바이더" value={editForm.provider} onChange={(e) => setEditForm((p) => ({ ...p, provider: e.target.value }))} />
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm md:col-span-2" placeholder="설명" value={editForm.description} onChange={(e) => setEditForm((p) => ({ ...p, description: e.target.value }))} />
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="tags CSV" value={editForm.tags} onChange={(e) => setEditForm((p) => ({ ...p, tags: e.target.value }))} />
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" placeholder="skills CSV" value={editForm.skills} onChange={(e) => setEditForm((p) => ({ ...p, skills: e.target.value }))} />
            <input className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm md:col-span-2" placeholder="custom skills CSV" value={editForm.customSkills} onChange={(e) => setEditForm((p) => ({ ...p, customSkills: e.target.value }))} />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              className="rounded-md border border-blue-500 bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white"
              onClick={() => saveBot().catch(() => undefined)}
              disabled={submittingEdit}
            >
              {submittingEdit ? "저장 중..." : "Save"}
            </button>
            <button
              type="button"
              className="rounded-md border border-rose-400 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700"
              onClick={() => deleteBot().catch(() => undefined)}
              disabled={submittingEdit}
            >
              Delete
            </button>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
    </section>
  );
}
