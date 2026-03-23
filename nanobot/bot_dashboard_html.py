"""HTML rendering helpers for the bot dashboard."""

from __future__ import annotations

import html
from typing import Any


def render_dashboard_html(summaries: list[dict[str, Any]]) -> str:
    """Render the static HTML dashboard payload for bot summaries."""
    cards = []
    for bot in summaries:
        tags_html = "".join(
            f'<span class="tag">{html.escape(tag)}</span>' for tag in bot.get("tags", [])
        ) or '<span class="tag muted">no tags</span>'
        cards.append(
            f"""
            <article class="card">
              <div class="card-top">
                <div>
                  <h2>{html.escape(bot['name'])}</h2>
                  <p class="role">{html.escape(bot['role'])}</p>
                </div>
                <span class="pill">{html.escape(bot['id'])}</span>
              </div>
              <p class="desc">{html.escape(bot.get('description') or 'No description yet.')}</p>
              <div class="metrics">
                <div><strong>{bot['session_count']}</strong><span>sessions</span></div>
                <div><strong>{bot['skills_dir_count']}</strong><span>skill dirs</span></div>
                <div><strong>{bot['history_entries']}</strong><span>history entries</span></div>
              </div>
              <div class="tags">{tags_html}</div>
              <dl>
                <dt>Model</dt><dd>{html.escape(str(bot.get('model') or ''))}</dd>
                <dt>Skills</dt><dd>{html.escape(bot.get('skill_summary') or 'none')}</dd>
                <dt>Custom Skills</dt><dd>{html.escape(bot.get('custom_skill_summary') or 'none')}</dd>
                <dt>Workspace</dt><dd><code>{html.escape(str(bot['workspace']))}</code></dd>
                <dt>Config</dt><dd><code>{html.escape(str(bot['config_path']))}</code></dd>
                <dt>Last Session</dt><dd>{html.escape(str(bot.get('last_session_at') or 'never'))}</dd>
              </dl>
              <div class="memory">
                <h3>Memory Snapshot</h3>
                <pre>{html.escape(bot.get('memory_excerpt') or 'No memory yet.')}</pre>
              </div>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>nanobot team dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #121933;
      --line: #2a3565;
      --text: #eef2ff;
      --muted: #a5b0d6;
      --accent: #7c9cff;
      --accent-soft: rgba(124, 156, 255, 0.18);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      background: radial-gradient(circle at top, #14204a, var(--bg) 45%);
      color: var(--text);
    }}
    header {{
      padding: 48px 24px 24px;
      max-width: 1200px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 2.25rem;
    }}
    .subtitle {{
      color: var(--muted);
      max-width: 760px;
      line-height: 1.5;
    }}
    .overview {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }}
    .overview .box, .card {{
      background: rgba(18, 25, 51, 0.92);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
    }}
    .overview .box {{
      padding: 18px;
    }}
    .overview .label {{
      display: block;
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 6px;
    }}
    .overview strong {{
      font-size: 1.7rem;
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px 48px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
    }}
    .card {{
      padding: 20px;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }}
    .card h2 {{
      margin: 0;
      font-size: 1.25rem;
    }}
    .role {{
      margin: 6px 0 0;
      color: #c5d0ff;
    }}
    .pill, .tag {{
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 0.82rem;
      background: var(--accent-soft);
      color: #dce4ff;
      border: 1px solid rgba(124, 156, 255, 0.34);
    }}
    .tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 14px 0;
    }}
    .tag.muted {{
      color: var(--muted);
      background: rgba(255,255,255,0.04);
      border-color: rgba(255,255,255,0.08);
    }}
    .desc {{
      color: var(--muted);
      line-height: 1.5;
      min-height: 3.2em;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      margin: 14px 0;
    }}
    .metrics div {{
      padding: 12px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.06);
      text-align: center;
    }}
    .metrics strong {{
      display: block;
      font-size: 1.25rem;
      margin-bottom: 4px;
    }}
    .metrics span, dt {{
      color: var(--muted);
      font-size: 0.88rem;
    }}
    dl {{
      display: grid;
      grid-template-columns: 96px 1fr;
      gap: 6px 12px;
      margin: 16px 0;
    }}
    dd {{
      margin: 0;
      word-break: break-word;
    }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .memory {{
      margin-top: 18px;
      border-top: 1px solid rgba(255,255,255,0.08);
      padding-top: 16px;
    }}
    .memory h3 {{
      margin: 0 0 10px;
      font-size: 1rem;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      background: #0a0f1f;
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 14px;
      padding: 14px;
      color: #dfe7ff;
    }}
  </style>
</head>
<body>
  <header>
    <h1>nanobot team dashboard</h1>
    <p class="subtitle">
      Static overview of isolated specialist bots. Each card reflects one bot workspace with its own config,
      memory, skills, and session history.
    </p>
    <section class="overview">
      <div class="box"><span class="label">Bots</span><strong>{len(summaries)}</strong></div>
      <div class="box"><span class="label">Total Sessions</span><strong>{sum(bot['session_count'] for bot in summaries)}</strong></div>
      <div class="box"><span class="label">Custom Skill Dirs</span><strong>{sum(bot['skills_dir_count'] for bot in summaries)}</strong></div>
      <div class="box"><span class="label">History Entries</span><strong>{sum(bot['history_entries'] for bot in summaries)}</strong></div>
    </section>
  </header>
  <main>
    <section class="grid">
      {''.join(cards) if cards else '<article class="card"><h2>No bots yet</h2><p class="desc">Run `nanobot bots create ...` to scaffold your first specialist.</p></article>'}
    </section>
  </main>
</body>
</html>
"""
