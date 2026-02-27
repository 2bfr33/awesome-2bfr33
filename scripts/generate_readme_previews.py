#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

DATA_PATH = Path("data/starred-repos.json")
OUT_A = Path("docs/readme-variant-a.md")
OUT_B = Path("docs/readme-variant-b.md")

ACTIVE_DAYS = 180
RECENT_STAR_DAYS = 30
DESC_MAX = 140

GROUP_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    (
        "Reference Lists",
        (
            "awesome-",
            "curated list",
            "awesome privacy",
            "awesome selfhosted",
        ),
    ),
    (
        "AI and Automation",
        (
            "llm",
            "agent",
            "claude",
            "autonomous",
            "diffusion",
            "model",
            "comfyui",
            "prompt",
            "machine learning",
            "open source coding agent",
        ),
    ),
    (
        "Self-Hosting and Homelab",
        (
            "self-host",
            "selfhost",
            "homelab",
            "proxmox",
            "dockge",
            "homepage",
            "dashboard",
            "linkwarden",
            "linkding",
            "nginx",
            "beszel",
            "code-server",
            "komodo",
            "rustdesk",
            "doco-cd",
            "puter",
        ),
    ),
    (
        "DevOps and Security",
        (
            "security",
            "vulnerab",
            "sbom",
            "trivy",
            "deploy",
            "backup",
            "monitor",
            "firewall",
            "alert",
            "log",
            "ci",
            "cd",
        ),
    ),
    (
        "Media and Content",
        (
            "media",
            "subtitle",
            "player",
            "video",
            "torrent",
            "soulseek",
            "aegisub",
            "handbrake",
            "mpv",
            "qbittorrent",
        ),
    ),
    (
        "System, Desktop and Mobile",
        (
            "windows",
            "android",
            "keyboard",
            "driver",
            "explorer",
            "activation",
            "winutil",
            "obtainium",
            "florisboard",
            "opensnitch",
            "remote desktop",
        ),
    ),
    (
        "Developer Tools",
        (
            "api",
            "cli",
            "editor",
            "tool",
            "web ui",
            "admin panel",
            "nicegui",
            "client",
            "typescript",
            "python",
            "go",
            "rust",
        ),
    ),
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


def fmt_datetime_utc(value: Optional[str]) -> str:
    dt = parse_dt(value)
    if not dt:
        dt = datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fmt_stars(value: int) -> str:
    return f"{value:,}"


def clean_text(text: Optional[str], max_len: int = DESC_MAX) -> str:
    if not text:
        return "No description."
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"[^\x20-\x7E]", "", cleaned).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "section"


def classify_repo(repo: Dict[str, object]) -> str:
    name = str(repo.get("name_with_owner") or "").lower()
    desc = str(repo.get("description") or "").lower()
    lang = str(repo.get("primary_language") or "")
    full_text = f"{name} {desc} {lang.lower()}"

    if "/awesome-" in name or name.startswith("awesome-") or "curated list" in desc:
        return "Reference Lists"

    for group, keywords in GROUP_RULES:
        if group == "Reference Lists":
            continue
        if any(keyword in full_text for keyword in keywords):
            return group

    if lang in {"TypeScript", "JavaScript", "Python", "Go", "Rust", "Zig"}:
        return "Developer Tools"
    if lang in {"C", "C++", "C#", "PowerShell", "Shell", "Batchfile", "Kotlin", "Dart"}:
        return "System, Desktop and Mobile"
    return "Other"


def sort_key(repo: Dict[str, object]) -> Tuple[datetime, int]:
    pushed = parse_dt(str(repo.get("pushed_at") or ""))
    if pushed is None:
        pushed = datetime(1970, 1, 1, tzinfo=timezone.utc)
    stars = int(repo.get("stargazer_count") or 0)
    return pushed, stars


def split_by_activity(
    repos: Iterable[Dict[str, object]], reference_dt: datetime
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    threshold = reference_dt - timedelta(days=ACTIVE_DAYS)
    active: List[Dict[str, object]] = []
    slow: List[Dict[str, object]] = []

    for repo in repos:
        pushed = parse_dt(str(repo.get("pushed_at") or ""))
        if pushed and pushed >= threshold:
            active.append(repo)
        else:
            slow.append(repo)
    return active, slow


def group_repositories(
    repos: List[Dict[str, object]]
) -> "OrderedDict[str, List[Dict[str, object]]]":
    grouped: "OrderedDict[str, List[Dict[str, object]]]" = OrderedDict()
    for group_name, _ in GROUP_RULES:
        grouped[group_name] = []
    grouped["Other"] = []

    sorted_repos = sorted(repos, key=sort_key, reverse=True)
    for repo in sorted_repos:
        grouped[classify_repo(repo)].append(repo)

    return grouped


def freshness_label(repo: Dict[str, object], snapshot_dt: datetime) -> str:
    pushed = parse_dt(str(repo.get("pushed_at") or ""))
    if not pushed:
        return "stale"
    days = (snapshot_dt.date() - pushed.date()).days
    if days <= 7:
        return "fresh this week"
    if days <= 30:
        return "fresh this month"
    if days <= ACTIVE_DAYS:
        return "active"
    return "stale"


def render_repo_entry(
    repo: Dict[str, object],
    snapshot_dt: datetime,
    include_commit: bool,
    include_freshness: bool,
) -> List[str]:
    name = str(repo["name_with_owner"])
    url = str(repo["url"])
    description = clean_text(repo.get("description"))
    language = str(repo.get("primary_language") or "Unknown")
    stars = fmt_stars(int(repo.get("stargazer_count") or 0))
    pushed = fmt_date(str(repo.get("pushed_at") or ""))
    commit = fmt_date(str(repo.get("last_commit_at") or ""))
    starred = fmt_date(str(repo.get("starred_at") or ""))

    meta_parts = [
        f"`{language}`",
        f"`Stars {stars}`",
        f"`Push {pushed}`",
    ]
    if include_commit:
        meta_parts.append(f"`Commit {commit}`")
    meta_parts.append(f"`Starred {starred}`")
    if include_freshness:
        meta_parts.append(f"`{freshness_label(repo, snapshot_dt)}`")

    return [
        f"- [{name}]({url})",
        f"  {description}",
        f"  {' | '.join(meta_parts)}",
    ]


def render_group_index(grouped: "OrderedDict[str, List[Dict[str, object]]]") -> List[str]:
    lines: List[str] = []
    for group_name, repos in grouped.items():
        if not repos:
            continue
        lines.append(f"- [{group_name} ({len(repos)})](#{slugify(group_name)})")
    return lines


def render_stats_block(generated_at: str, total: int, active: int, slow: int) -> List[str]:
    return [
        f"Last updated: `{fmt_datetime_utc(generated_at)}`",
        f"Total repositories: **{total}**",
        f"Active projects (push <= {ACTIVE_DAYS} days): **{active}**",
        f"Slower projects: **{slow}**",
        "Auto-updated daily.",
    ]


def build_variant_a(login: str, generated_at: str, repos: List[Dict[str, object]]) -> str:
    snapshot_dt = parse_dt(generated_at) or datetime.now(timezone.utc)
    active, slow = split_by_activity(repos, snapshot_dt)
    grouped_all = group_repositories(repos)
    grouped_active = group_repositories(active)
    grouped_slow = group_repositories(slow)

    lines: List[str] = [
        "# README Variant B2 - Compact",
        "",
        f"Auto-generated list of GitHub stars for **{login}**.",
        "",
    ]
    lines.extend(render_stats_block(generated_at, len(repos), len(active), len(slow)))
    lines.extend(["", "## Group Index", ""])
    lines.extend(render_group_index(grouped_all))
    lines.extend(["", f"## Active Projects ({len(active)})", ""])

    for group_name, group_repos in grouped_active.items():
        if not group_repos:
            continue
        lines.append(f"### {group_name} ({len(group_repos)})")
        lines.append("")
        for repo in group_repos:
            lines.extend(
                render_repo_entry(
                    repo=repo,
                    snapshot_dt=snapshot_dt,
                    include_commit=False,
                    include_freshness=True,
                )
            )
            lines.append("")

    lines.extend([f"## Slower Projects ({len(slow)})", ""])
    for group_name, group_repos in grouped_slow.items():
        if not group_repos:
            continue
        lines.append("<details>")
        lines.append(f"<summary><strong>{group_name}</strong> ({len(group_repos)})</summary>")
        lines.append("")
        for repo in group_repos:
            lines.extend(
                render_repo_entry(
                    repo=repo,
                    snapshot_dt=snapshot_dt,
                    include_commit=False,
                    include_freshness=True,
                )
            )
            lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_variant_b(login: str, generated_at: str, repos: List[Dict[str, object]]) -> str:
    snapshot_dt = parse_dt(generated_at) or datetime.now(timezone.utc)
    active, slow = split_by_activity(repos, snapshot_dt)
    grouped_all = group_repositories(repos)
    grouped_active = group_repositories(active)
    grouped_slow = group_repositories(slow)

    recent_threshold = snapshot_dt - timedelta(days=RECENT_STAR_DAYS)
    recently_starred = [
        repo
        for repo in sorted(
            repos,
            key=lambda r: parse_dt(str(r.get("starred_at") or ""))
            or datetime(1970, 1, 1, tzinfo=timezone.utc),
            reverse=True,
        )
        if (parse_dt(str(repo.get("starred_at") or "")) or datetime(1970, 1, 1, tzinfo=timezone.utc))
        >= recent_threshold
    ][:10]

    lines: List[str] = [
        "# README Variant B2 - Curated",
        "",
        f"Auto-generated list of GitHub stars for **{login}**.",
        "",
    ]
    lines.extend(render_stats_block(generated_at, len(repos), len(active), len(slow)))
    lines.extend(["", "## Group Index", ""])
    lines.extend(render_group_index(grouped_all))

    lines.extend(["", f"## Recently Starred (last {RECENT_STAR_DAYS} days)", ""])
    if recently_starred:
        for idx, repo in enumerate(recently_starred, start=1):
            name = str(repo["name_with_owner"])
            url = str(repo["url"])
            desc = clean_text(repo.get("description"), max_len=95)
            starred = fmt_date(str(repo.get("starred_at") or ""))
            stars = fmt_stars(int(repo.get("stargazer_count") or 0))
            lines.append(
                f"{idx}. [{name}]({url}) - {desc} (`Starred {starred}` | `Stars {stars}`)"
            )
    else:
        lines.append("- No recently starred repositories.")

    lines.extend(["", f"## Active Projects ({len(active)})", ""])
    for group_name, group_repos in grouped_active.items():
        if not group_repos:
            continue
        lines.append("<details>")
        lines.append(f"<summary><strong>{group_name}</strong> ({len(group_repos)})</summary>")
        lines.append("")
        for repo in group_repos:
            lines.extend(
                render_repo_entry(
                    repo=repo,
                    snapshot_dt=snapshot_dt,
                    include_commit=False,
                    include_freshness=True,
                )
            )
            lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.extend([f"## Slower Projects ({len(slow)})", ""])
    for group_name, group_repos in grouped_slow.items():
        if not group_repos:
            continue
        lines.append("<details>")
        lines.append(f"<summary><strong>{group_name}</strong> ({len(group_repos)})</summary>")
        lines.append("")
        for repo in group_repos:
            lines.extend(
                render_repo_entry(
                    repo=repo,
                    snapshot_dt=snapshot_dt,
                    include_commit=True,
                    include_freshness=True,
                )
            )
            lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.extend(
        [
            "## Optional Add-ons",
            "",
            "- Add a manual `Pinned Picks` section (3-8 projects) to keep the list personal.",
            "- Add short personal notes per project (`why it matters`, `what to try first`).",
            "- Add tag badges (`infra`, `ai`, `security`, `media`) for faster scanning.",
            "- Add archive markers and hide archived repos by default.",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    login = str(payload.get("login") or "unknown")
    generated_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())
    repositories = list(payload.get("repositories") or [])

    OUT_A.parent.mkdir(parents=True, exist_ok=True)
    OUT_B.parent.mkdir(parents=True, exist_ok=True)

    OUT_A.write_text(build_variant_a(login, generated_at, repositories), encoding="utf-8")
    OUT_B.write_text(build_variant_b(login, generated_at, repositories), encoding="utf-8")

    print(f"Wrote {OUT_A} and {OUT_B}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
