#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_PATH = Path("data/starred-repos.json")
DOCS_DIR = Path("docs")
ACTIVE_DAYS = 180

PROPOSALS = [
    ("01-compact-two-lines", "Proposal 01 - Compact 2 Lines"),
    ("02-inline-badges", "Proposal 02 - Inline Badge Style"),
    ("03-single-line-list", "Proposal 03 - Single Line List"),
    ("04-collapsible-metrics", "Proposal 04 - Collapsible Metrics"),
    ("05-no-description-default", "Proposal 05 - No Description by Default"),
    ("06-grouped-compact-cards", "Proposal 06 - Grouped Compact Cards"),
    ("07-status-first", "Proposal 07 - Status First"),
    ("08-mini-tabular", "Proposal 08 - Mini Tabular"),
]

SAMPLE_NAMES = [
    "gethomepage/homepage",
    "anomalyco/opencode",
    "aquasecurity/trivy",
    "rustdesk/rustdesk",
    "linkwarden/linkwarden",
]


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_date(value: Optional[str]) -> str:
    dt = parse_dt(value)
    return dt.strftime("%Y-%m-%d") if dt else "-"


def fmt_dt_utc(value: Optional[str]) -> str:
    dt = parse_dt(value)
    if not dt:
        dt = datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fmt_stars(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


def clean_desc(text: Optional[str], max_len: int = 120) -> str:
    if not text:
        return "No description."
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"[^\x20-\x7E]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace("|", "\\|")
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def status_label(repo: Dict[str, Any], snapshot_dt: datetime) -> str:
    pushed = parse_dt(repo.get("pushed_at"))
    if not pushed:
        return "stale"
    days = (snapshot_dt.date() - pushed.date()).days
    if days <= 7:
        return "fresh"
    if days <= 30:
        return "recent"
    if days <= ACTIVE_DAYS:
        return "active"
    return "stale"


def snapshot_counts(repos: List[Dict[str, Any]], snapshot_dt: datetime) -> Dict[str, int]:
    threshold = snapshot_dt - timedelta(days=ACTIVE_DAYS)
    active = 0
    slow = 0
    for repo in repos:
        pushed = parse_dt(repo.get("pushed_at"))
        if pushed and pushed >= threshold:
            active += 1
        else:
            slow += 1
    return {"total": len(repos), "active": active, "slow": slow}


def snapshot_block_style_1(snapshot_text: str, counts: Dict[str, int]) -> List[str]:
    return [
        f"Last snapshot: `{snapshot_text}`",
        f"Total **{counts['total']}** | Active **{counts['active']}** | Slower **{counts['slow']}** | Daily auto-update",
    ]


def snapshot_block_style_2(snapshot_text: str, counts: Dict[str, int]) -> List[str]:
    return [
        f"`last {snapshot_text}` `total {counts['total']}` `active {counts['active']}` `slower {counts['slow']}` `daily`",
    ]


def pick_samples(repos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_name = {r.get("name_with_owner"): r for r in repos}
    picked: List[Dict[str, Any]] = []
    for name in SAMPLE_NAMES:
        repo = by_name.get(name)
        if repo:
            picked.append(repo)
    if len(picked) < 5:
        for repo in repos:
            if repo not in picked:
                picked.append(repo)
            if len(picked) >= 5:
                break
    return picked


def repo_fields(repo: Dict[str, Any], snapshot_dt: datetime) -> Dict[str, str]:
    return {
        "name": str(repo.get("name_with_owner") or "unknown/repo"),
        "url": str(repo.get("url") or "#"),
        "desc": clean_desc(repo.get("description")),
        "lang": str(repo.get("primary_language") or "Unknown"),
        "stars": fmt_stars(repo.get("stargazer_count")),
        "push": fmt_date(repo.get("pushed_at")),
        "starred": fmt_date(repo.get("starred_at")),
        "status": status_label(repo, snapshot_dt),
    }


def build_proposal_01(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 01 - Compact 2 Lines",
        "",
        "Intent: short snapshot + 2-line repo entries.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_1(snapshot_text, counts))
    lines.extend(["", "## Sample Projects", ""])
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(f"- [{f['name']}]({f['url']}) - {f['desc']}")
        lines.append(
            f"  `{f['lang']}` | `{f['stars']} stars` | `push {f['push']}` | `starred {f['starred']}` | `{f['status']}`"
        )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_proposal_02(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 02 - Inline Badge Style",
        "",
        "Intent: compact markdown badge look.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_2(snapshot_text, counts))
    lines.extend(["", "## Sample Projects", ""])
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(f"- [{f['name']}]({f['url']}) - {f['desc']}")
        lines.append(
            f"  `lang {f['lang']}` | `stars {f['stars']}` | `push {f['push']}` | `starred {f['starred']}` | `{f['status']}`"
        )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_proposal_03(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 03 - Single Line List",
        "",
        "Intent: maximum density, minimum vertical space.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_1(snapshot_text, counts))
    lines.extend(["", "## Sample Projects", ""])
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(
            f"- [{f['name']}]({f['url']}) - {f['desc']} ({f['lang']} | {f['stars']} stars | push {f['push']} | starred {f['starred']} | {f['status']})"
        )
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_proposal_04(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 04 - Collapsible Metrics",
        "",
        "Intent: clean list, metrics visible on demand.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_1(snapshot_text, counts))
    lines.extend(["", "## Sample Projects", ""])
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(f"- [{f['name']}]({f['url']}) - {f['desc']}")
        lines.append("  <details>")
        lines.append("  <summary>metrics</summary>")
        lines.append("")
        lines.append(
            f"  `{f['lang']}` | `{f['stars']} stars` | `push {f['push']}` | `starred {f['starred']}` | `{f['status']}`"
        )
        lines.append("")
        lines.append("  </details>")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_proposal_05(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 05 - No Description by Default",
        "",
        "Intent: fast scanning of names and metrics, description optional.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_1(snapshot_text, counts))
    lines.extend(["", "## Sample Projects", ""])
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(f"- [{f['name']}]({f['url']})")
        lines.append(
            f"  `{f['lang']}` | `{f['stars']} stars` | `push {f['push']}` | `starred {f['starred']}` | `{f['status']}`"
        )
        lines.append("  <details>")
        lines.append("  <summary>description</summary>")
        lines.append("")
        lines.append(f"  {f['desc']}")
        lines.append("")
        lines.append("  </details>")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_proposal_06(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 06 - Grouped Compact Cards",
        "",
        "Intent: balanced readability and compactness.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_1(snapshot_text, counts))
    lines.extend(
        [
            "",
            "## Self-Hosting and Homelab (sample)",
            "",
        ]
    )
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(f"- [{f['name']}]({f['url']})")
        lines.append(f"  {f['desc']}")
        lines.append(
            f"  `{f['lang']} | {f['stars']} stars | push {f['push']} | starred {f['starred']} | {f['status']}`"
        )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_proposal_07(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 07 - Status First",
        "",
        "Intent: surface activity state before technical details.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_1(snapshot_text, counts))
    lines.extend(["", "## Sample Projects", ""])
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(f"- [{f['name']}]({f['url']}) - {f['desc']}")
        lines.append(
            f"  `{f['status']}` | `push {f['push']}` | `starred {f['starred']}` | `{f['lang']}` | `{f['stars']} stars`"
        )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_proposal_08(snapshot_text: str, counts: Dict[str, int], samples: List[Dict[str, Any]], snapshot_dt: datetime) -> str:
    lines = [
        "# Proposal 08 - Mini Tabular",
        "",
        "Intent: labeled metrics with compact alignment feel.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(snapshot_block_style_1(snapshot_text, counts))
    lines.extend(["", "## Sample Projects", ""])
    for repo in samples:
        f = repo_fields(repo, snapshot_dt)
        lines.append(f"- [{f['name']}]({f['url']}) - {f['desc']}")
        lines.append(
            f"  `Lang: {f['lang']} | Stars: {f['stars']} | Push: {f['push']} | Starred: {f['starred']} | Status: {f['status']}`"
        )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_index(files: List[str]) -> str:
    lines = [
        "# Layout Proposals",
        "",
        "Visual variants for README formatting.",
        "",
        "## Files",
        "",
    ]
    for file in files:
        lines.append(f"- [{file}](./{file})")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    repos: List[Dict[str, Any]] = list(payload.get("repositories") or [])
    generated_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())
    snapshot_dt = parse_dt(generated_at) or datetime.now(timezone.utc)
    snapshot_text = fmt_dt_utc(generated_at)
    counts = snapshot_counts(repos, snapshot_dt)
    samples = pick_samples(repos)

    builders = [
        build_proposal_01,
        build_proposal_02,
        build_proposal_03,
        build_proposal_04,
        build_proposal_05,
        build_proposal_06,
        build_proposal_07,
        build_proposal_08,
    ]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for (slug, _title), builder in zip(PROPOSALS, builders):
        path = DOCS_DIR / f"layout-{slug}.md"
        content = builder(snapshot_text, counts, samples, snapshot_dt)
        path.write_text(content, encoding="utf-8")
        written.append(path.name)

    index_path = DOCS_DIR / "layout-proposals-index.md"
    index_path.write_text(build_index(written), encoding="utf-8")
    print(f"Wrote {len(written)} proposal files + index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
