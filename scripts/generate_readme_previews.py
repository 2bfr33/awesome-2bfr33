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
            "docker",
            "compose",
            "log",
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


def fmt_star_count(value: int) -> str:
    return f"{value:,}"


def clean_text(text: Optional[str], max_len: int = DESC_MAX) -> str:
    if not text:
        return "No description."
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"[^\x20-\x7E]", "", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "section"


def classify_repo(repo: Dict[str, object]) -> str:
    name = str(repo.get("name_with_owner") or "")
    desc = str(repo.get("description") or "")
    lang = str(repo.get("primary_language") or "")
    full_text = f"{name} {desc} {lang}".lower()

    for group, keywords in GROUP_RULES:
        if any(keyword in full_text for keyword in keywords):
            return group

    if lang in {"TypeScript", "JavaScript", "Python", "Go", "Rust"}:
        return "Developer Tools"
    if lang in {"C", "C++", "C#", "PowerShell", "Shell", "Batchfile", "Kotlin", "Dart"}:
        return "System, Desktop and Mobile"
    return "Other"


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

    for repo in repos:
        grouped[classify_repo(repo)].append(repo)

    return grouped


def render_repo_bullet(repo: Dict[str, object]) -> List[str]:
    name = str(repo["name_with_owner"])
    url = str(repo["url"])
    description = clean_text(repo.get("description"))
    language = str(repo.get("primary_language") or "Unknown")
    stars = fmt_star_count(int(repo.get("stargazer_count") or 0))
    pushed = fmt_date(str(repo.get("pushed_at") or ""))
    commit = fmt_date(str(repo.get("last_commit_at") or ""))
    starred = fmt_date(str(repo.get("starred_at") or ""))
    return [
        f"- [{name}]({url})",
        f"  {description}",
        f"  `{language}` | `Stars {stars}` | `Push {pushed}` | `Commit {commit}` | `Starred {starred}`",
    ]


def render_group_index(grouped: "OrderedDict[str, List[Dict[str, object]]]") -> List[str]:
    lines: List[str] = []
    for group_name, repos in grouped.items():
        if not repos:
            continue
        slug = slugify(group_name)
        lines.append(f"- [{group_name} ({len(repos)})](#{slug})")
    return lines


def build_variant_a(login: str, generated_at: str, repos: List[Dict[str, object]]) -> str:
    grouped = group_repositories(repos)
    lines: List[str] = [
        "# README Design A: Topic Groups",
        "",
        f"Preview layout for **{login}**.",
        "",
        f"Generated from starred snapshot: `{generated_at}`",
        f"Total repositories: **{len(repos)}**",
        "",
        "## Group Index",
        "",
    ]
    lines.extend(render_group_index(grouped))
    lines.extend(["", "## Projects", ""])

    for group_name, group_repos in grouped.items():
        if not group_repos:
            continue
        lines.append(f"## {group_name} ({len(group_repos)})")
        lines.append("")
        for repo in group_repos:
            lines.extend(render_repo_bullet(repo))
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_variant_b(login: str, generated_at: str, repos: List[Dict[str, object]]) -> str:
    grouped_all = group_repositories(repos)
    snapshot_dt = parse_dt(generated_at) or datetime.now(timezone.utc)
    active, slow = split_by_activity(repos, snapshot_dt)
    grouped_active = group_repositories(active)
    grouped_slow = group_repositories(slow)
    highlights = sorted(repos, key=lambda x: int(x.get("stargazer_count") or 0), reverse=True)[:12]

    lines: List[str] = [
        "# README Design B: Highlights + Activity",
        "",
        f"Preview layout for **{login}**.",
        "",
        f"Generated from starred snapshot: `{generated_at}`",
        f"Total repositories: **{len(repos)}**",
        f"Active projects (push <= {ACTIVE_DAYS} days): **{len(active)}**",
        f"Slower projects: **{len(slow)}**",
        "",
        "## Group Index",
        "",
    ]
    lines.extend(render_group_index(grouped_all))
    lines.extend(["", "## Highlights (Top by Stars)", ""])

    for idx, repo in enumerate(highlights, start=1):
        name = str(repo["name_with_owner"])
        url = str(repo["url"])
        description = clean_text(repo.get("description"), max_len=100)
        stars = fmt_star_count(int(repo.get("stargazer_count") or 0))
        lines.append(f"{idx}. [{name}]({url}) - {description} (`Stars {stars}`)")

    lines.extend(["", f"## Active Projects ({len(active)})", ""])
    for group_name, group_repos in grouped_active.items():
        if not group_repos:
            continue
        lines.append(f"<details>")
        lines.append(f"<summary><strong>{group_name}</strong> ({len(group_repos)})</summary>")
        lines.append("")
        for repo in group_repos:
            lines.extend(render_repo_bullet(repo))
            lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.extend([f"## Slower Projects ({len(slow)})", ""])
    for group_name, group_repos in grouped_slow.items():
        if not group_repos:
            continue
        lines.append(f"<details>")
        lines.append(f"<summary><strong>{group_name}</strong> ({len(group_repos)})</summary>")
        lines.append("")
        for repo in group_repos:
            lines.extend(render_repo_bullet(repo))
            lines.append("")
        lines.append("</details>")
        lines.append("")

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
