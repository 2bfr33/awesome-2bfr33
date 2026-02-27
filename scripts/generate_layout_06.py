#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from generate_awesome import (
    ACTIVE_DAYS,
    fmt_date,
    fmt_datetime_utc,
    fmt_stars,
    freshness_label,
    group_repositories,
    parse_dt,
    split_by_activity,
)

DATA_PATH = Path("data/starred-repos.json")
OUTPUT_PATH = Path("docs/layout-06-grouped-compact-cards.md")


def clean_desc(text: Any, max_len: int = 140) -> str:
    if not text:
        return "No description."
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    cleaned = re.sub(r"[^\x20-\x7E]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace("|", "\\|")
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def build_layout(payload: Dict[str, Any]) -> str:
    repos: List[Dict[str, Any]] = list(payload.get("repositories") or [])
    login = str(payload.get("login") or "unknown")
    generated_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())
    snapshot_dt = parse_dt(generated_at) or datetime.now(timezone.utc)
    active, slow = split_by_activity(repos, snapshot_dt)
    grouped = group_repositories(repos, mode="active")

    lines: List[str] = [
        "# Proposal 06 - Grouped Compact Cards",
        "",
        f"Full preview for **{login}**.",
        "",
        "## Snapshot",
        "",
        f"Last snapshot: `{fmt_datetime_utc(generated_at)}`",
        f"Total **{len(repos)}** | Active **{len(active)}** | Slower **{len(slow)}** | Daily auto-update",
        "",
        "## Group Index",
        "",
    ]

    for group_name, items in grouped.items():
        if items:
            anchor = re.sub(r"[^a-z0-9]+", "-", group_name.lower()).strip("-")
            lines.append(f"- [{group_name} ({len(items)})](#{anchor})")

    lines.extend(["", "## Projects", ""])

    for group_name, items in grouped.items():
        if not items:
            continue
        lines.append(f"## {group_name} ({len(items)})")
        lines.append("")
        for repo in items:
            name = str(repo.get("name_with_owner") or "unknown/repo")
            url = str(repo.get("url") or "#")
            desc = clean_desc(repo.get("description"))
            language = str(repo.get("primary_language") or "Unknown")
            stars = fmt_stars(int(repo.get("stargazer_count") or 0))
            pushed = fmt_date(repo.get("pushed_at"))
            commit = fmt_date(repo.get("last_commit_at"))
            starred = fmt_date(repo.get("starred_at"))
            status = freshness_label(repo, snapshot_dt)
            is_archived = bool(repo.get("is_archived"))

            lines.append(f"- [{name}]({url})")
            lines.append(f"  {desc}")
            lines.append(f"  - `Language: {language}`")
            lines.append(f"  - `Stars: {stars}`")
            lines.append(f"  - `Push: {pushed}`")
            lines.append(f"  - `Commit: {commit}`")
            lines.append(f"  - `Starred: {starred}`")
            lines.append(f"  - `Status: {status}`")
            if is_archived:
                lines.append("  - `State: archived`")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    content = build_layout(payload)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
