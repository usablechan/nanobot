import { useState } from "react";

type TeamCreateModalProps = {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
};

export function TeamCreateModal({ open, onClose, onCreated }: TeamCreateModalProps) {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const reset = () => {
    setName("");
    setGoal("");
    setError("");
  };

  const handleClose = () => {
    if (creating) return;
    reset();
    onClose();
  };

  const handleCreate = async () => {
    if (creating) return;
    if (name.trim().length < 2) {
      setError("팀 이름을 2자 이상 입력해주세요.");
      return;
    }

    setCreating(true);
    setError("");

    try {
      const response = await fetch("/api/teams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          goal: goal.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data?.error || "team_create_failed");
        setCreating(false);
        return;
      }
      onCreated();
      handleClose();
    } catch {
      setError("network_error");
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-300 bg-white p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="m-0 text-xl font-bold text-slate-800">새 팀 만들기</h2>
          <button
            type="button"
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
            onClick={handleClose}
          >
            닫기
          </button>
        </div>

        <div className="grid gap-4">
          <label className="text-sm font-semibold text-slate-700">
            팀 이름
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="예: Marketing Team"
            />
          </label>

          <label className="text-sm font-semibold text-slate-700">
            팀 목표 (선택)
            <textarea
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="예: 런칭 스레드 제작 자동화"
            />
          </label>
        </div>

        {error ? <p className="mt-4 text-sm font-semibold text-rose-600">오류: {error}</p> : null}

        <div className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={handleClose}
            disabled={creating}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm disabled:opacity-40"
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {creating ? "생성 중..." : "팀 생성"}
          </button>
        </div>
      </div>
    </div>
  );
}
