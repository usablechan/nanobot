import { useCallback, useEffect, useState } from "react";
import type { KeyboardEvent } from "react";
import type { Agent, TaskItem } from "../../types";
import { getBackendHttpBase } from "../../utils";

type TasksPanelProps = {
  title: string;
  subtitle: string;
  agents: Agent[];
  selectedTeamId: string;
};

export function TasksPanel({ title, subtitle, agents, selectedTeamId }: TasksPanelProps) {
  const base = getBackendHttpBase();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${base}/api/tasks?teamId=${encodeURIComponent(selectedTeamId)}`);
      if (!res.ok) throw new Error("fetch_failed");
      const data = await res.json();
      setTasks(Array.isArray(data.tasks) ? data.tasks : []);
    } catch {
      setError("할 일 목록을 불러오지 못했어요.");
    } finally {
      setLoading(false);
    }
  }, [base, selectedTeamId]);

  useEffect(() => {
    fetchTasks().catch(() => undefined);
    const timer = setInterval(() => fetchTasks().catch(() => undefined), 6000);
    return () => clearInterval(timer);
  }, [fetchTasks]);

  const patchTask = useCallback(
    async (taskId: string, payload: Partial<TaskItem>) => {
      const res = await fetch(`${base}/api/tasks/${taskId}?teamId=${encodeURIComponent(selectedTeamId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("patch_failed");
    },
    [base, selectedTeamId],
  );

  const deleteTask = useCallback(
    async (taskId: string) => {
      const res = await fetch(`${base}/api/tasks/${taskId}?teamId=${encodeURIComponent(selectedTeamId)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("delete_failed");
    },
    [base, selectedTeamId],
  );

  const handleCreate = async () => {
    const titleValue = newTitle.trim();
    if (!titleValue || submitting) return;

    setError("");
    setSubmitting(true);

    const optimisticId = `temp-${Date.now()}`;
    const optimisticTask: TaskItem = {
      id: optimisticId,
      title: titleValue,
      description: "",
      status: "todo",
      priority: "P2",
      assignee: "",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      retryCount: 0,
      retryLimit: 0,
    };

    setTasks((prev) => [optimisticTask, ...prev]);
    setNewTitle("");

    try {
      const res = await fetch(`${base}/api/tasks?teamId=${encodeURIComponent(selectedTeamId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: titleValue, status: "todo" }),
      });
      if (!res.ok) throw new Error("create_failed");
      const data = await res.json();
      const created = data?.task as TaskItem | undefined;
      if (!created?.id) throw new Error("invalid_payload");
      setTasks((prev) => prev.map((task) => (task.id === optimisticId ? created : task)));
    } catch {
      setTasks((prev) => prev.filter((task) => task.id !== optimisticId));
      setError("할 일 추가에 실패했어요.");
      fetchTasks().catch(() => undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const handleChangeStatus = async (task: TaskItem, status: TaskItem["status"]) => {
    if (task.status === status) return;
    setError("");

    const previous = task.status;
    setTasks((prev) => prev.map((item) => (item.id === task.id ? { ...item, status } : item)));

    try {
      await patchTask(task.id, { status });
    } catch {
      setTasks((prev) =>
        prev.map((item) => (item.id === task.id ? { ...item, status: previous } : item)),
      );
      setError("상태 변경에 실패했어요.");
      fetchTasks().catch(() => undefined);
    }
  };

  const handleDelete = async (taskId: string) => {
    setError("");
    const snapshot = tasks;
    setTasks((prev) => prev.filter((task) => task.id !== taskId));

    try {
      await deleteTask(taskId);
    } catch {
      setTasks(snapshot);
      setError("할 일 삭제에 실패했어요.");
      fetchTasks().catch(() => undefined);
    }
  };

  const onCreateKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleCreate().catch(() => undefined);
    }
  };

  const todoTasks = tasks.filter((task) => task.status === "todo");
  const doingTasks = tasks.filter((task) => task.status === "doing");
  const doneTasks = tasks.filter((task) => task.status === "done");

  const statusStyle: Record<string, string> = {
    todo: "border-slate-200 bg-slate-50",
    doing: "border-amber-200 bg-amber-50",
    done: "border-emerald-200 bg-emerald-50",
  };

  return (
    <section className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          <p className="m-0 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] uppercase tracking-wider text-blue-700">
          SIMPLE TASKS
        </span>
      </div>
      <div className="text-[11px] text-slate-500">활성 에이전트 {agents.length}명</div>

      <div className="rounded-xl border border-slate-200 bg-white p-3 sm:p-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            type="text"
            placeholder="할 일을 입력하세요"
            value={newTitle}
            onChange={(event) => setNewTitle(event.target.value)}
            onKeyDown={onCreateKeyDown}
          />
          <button
            type="button"
            onClick={() => handleCreate().catch(() => undefined)}
            disabled={submitting}
            className="rounded-lg border border-blue-500 bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "추가 중" : "추가"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
      {loading ? <div className="text-xs text-slate-500">로딩 중...</div> : null}

      <div className="grid min-h-0 grid-cols-1 gap-3 overflow-auto pr-1 lg:grid-cols-3">
        {[
          { key: "todo", label: "Todo", items: todoTasks },
          { key: "doing", label: "Doing", items: doingTasks },
          { key: "done", label: "Done", items: doneTasks },
        ].map((column) => (
          <div key={column.key} className="flex min-h-[240px] flex-col rounded-xl border border-slate-200 bg-white p-3">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="m-0 text-sm font-semibold text-slate-800">{column.label}</h3>
              <span className="text-xs text-slate-500">{column.items.length}개</span>
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto">
              {column.items.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-xs text-slate-500">
                  항목이 없습니다.
                </div>
              ) : (
                column.items.map((task) => (
                  <div
                    key={task.id}
                    className={`flex flex-col gap-2 rounded-lg border p-3 ${statusStyle[task.status] || "border-slate-200 bg-slate-50"}`}
                  >
                    <div className="truncate text-sm font-medium text-slate-800">{task.title}</div>
                    <div className="flex items-center gap-2">
                      <select
                        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
                        value={task.status}
                        onChange={(event) =>
                          handleChangeStatus(task, event.target.value as TaskItem["status"]).catch(() => undefined)
                        }
                      >
                        <option value="todo">todo</option>
                        <option value="doing">doing</option>
                        <option value="done">done</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => handleDelete(task.id).catch(() => undefined)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
