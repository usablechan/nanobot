import { useCallback, useEffect, useMemo, useState } from "react";
import { getBackendHttpBase } from "../../utils";

type SkillsPanelProps = {
  title: string;
  subtitle: string;
};

type SkillInfo = {
  name: string;
  description: string;
  location: string;
  content: string;
};

export function SkillsPanel({ title, subtitle }: SkillsPanelProps) {
  const base = getBackendHttpBase();
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [query, setQuery] = useState("");
  const [openByName, setOpenByName] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${base}/api/nanobot/skills`);
      const data = await res.json();
      if (!res.ok || !data?.ok) throw new Error(String(data?.error || `HTTP_${res.status}`));
      const rows = Array.isArray(data?.skills) ? data.skills : [];
      setSkills(rows);
      setError("");
    } catch (err) {
      const reason = err instanceof Error ? err.message : "network";
      setError(`스킬 목록 로딩 실패 (${reason})`);
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = skills
      .filter((skill) => {
        if (!q) return true;
        const target = `${skill.name} ${skill.description} ${skill.location}`.toLowerCase();
        return target.includes(q);
      })
      .sort((a, b) => a.name.localeCompare(b.name));
    return rows;
  }, [skills, query]);

  return (
    <section className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 disabled:opacity-50"
          onClick={() => load()}
          disabled={loading}
        >
          새로고침
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <input
          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          placeholder="이름/설명/경로 검색"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <p className="m-0 mt-2 text-xs text-slate-500">
          nanobot 에이전트는{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[11px] text-slate-700">
            skill({"{"} name: "git-release" {"}"})
          </code>{" "}
          같은 형태로 스킬을 로드해.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        {loading && !filtered.length ? <div className="text-sm text-slate-500">불러오는 중...</div> : null}
        {!loading && !filtered.length ? (
          <div className="text-sm text-slate-500">
            스킬이 없습니다. `~/.nanobot/skills/&lt;name&gt;/SKILL.md` 또는 `nanobot/skills`를 확인해줘.
          </div>
        ) : null}

        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {filtered.map((skill) => {
            const opened = openByName[skill.name] ?? false;
            return (
              <li key={skill.name} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-800">{skill.name}</div>
                    <div className="mt-1 text-xs text-slate-600">{skill.description}</div>
                    <div className="mt-1 truncate font-mono text-[11px] text-slate-500">{skill.location}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700"
                      onClick={() => {
                        navigator.clipboard?.writeText(skill.name).catch(() => undefined);
                      }}
                      title="스킬 이름 복사"
                    >
                      Copy
                    </button>
                    <button
                      type="button"
                      className="rounded-md border border-blue-300 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700"
                      onClick={() => setOpenByName((prev) => ({ ...prev, [skill.name]: !opened }))}
                    >
                      {opened ? "접기" : "보기"}
                    </button>
                  </div>
                </div>

                {opened ? (
                  <pre className="mt-3 max-h-[320px] overflow-auto rounded-lg border border-slate-200 bg-white p-2 text-[11px] text-slate-800">
                    {skill.content}
                  </pre>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
    </section>
  );
}
