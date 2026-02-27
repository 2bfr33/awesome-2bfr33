#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.github.com/graphql"
README_PATH = Path(os.getenv("OUTPUT_README", "README.md"))
JSON_PATH = Path(os.getenv("OUTPUT_JSON", "data/starred-repos.json"))
MAX_DESC_LEN = int(os.getenv("MAX_DESC_LEN", "140"))
ACTIVE_DAYS = int(os.getenv("ACTIVE_DAYS", "180"))
RECENT_STAR_DAYS = int(os.getenv("RECENT_STAR_DAYS", "30"))

GROUP_EMOJIS: Dict[str, str] = {
    "Reference Lists": "📚",
    "AI and Automation": "🤖",
    "Self-Hosting and Homelab": "🏠",
    "DevOps and Security": "🔐",
    "Media and Content": "🎬",
    "System, Desktop and Mobile": "💻",
    "Developer Tools": "🛠️",
    "Other": "📦",
}

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

GRAPHQL_QUERY = """
query($after: String) {
  viewer {
    login
    starredRepositories(
      first: 100
      after: $after
      orderBy: {field: STARRED_AT, direction: DESC}
    ) {
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        starredAt
        node {
          nameWithOwner
          url
          description
          stargazerCount
          isArchived
          primaryLanguage {
            name
          }
          pushedAt
          updatedAt
          defaultBranchRef {
            name
            target {
              __typename
              ... on Commit {
                oid
                committedDate
              }
            }
          }
        }
      }
    }
  }
}
""".strip()


def require_token() -> str:
    token = (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("GH_TOKEN")
        or os.getenv("PERSONAL_ACCESS_TOKEN")
    )
    if token:
        return token
    print(
        "Missing GitHub token. Set GITHUB_TOKEN (recommended) or GH_TOKEN.",
        file=sys.stderr,
    )
    sys.exit(1)


def github_graphql(token: str, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
        "User-Agent": "awesome-starred-list-generator",
    }
    request = Request(API_URL, data=payload, headers=headers, method="POST")

    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc

    parsed = json.loads(raw)
    if "errors" in parsed and parsed["errors"]:
        raise RuntimeError(f"GitHub API GraphQL errors: {json.dumps(parsed['errors'])}")
    if "data" not in parsed or parsed["data"] is None:
        raise RuntimeError("GitHub API response has no data field.")
    return parsed["data"]


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


def fmt_stars_short(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def sanitize_text(text: Optional[str], max_len: int = MAX_DESC_LEN) -> str:
    if not text:
        return "No description."
    cleaned = re.sub(r"\s+", " ", text).strip().replace("|", "\\|")
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "section"


def classify_repo(repo: Dict[str, Any]) -> str:
    name = str(repo.get("name_with_owner") or "").lower()
    description = str(repo.get("description") or "").lower()
    language = str(repo.get("primary_language") or "")
    full_text = f"{name} {description} {language.lower()}"

    if "/awesome-" in name or name.startswith("awesome-") or "curated list" in description:
        return "Reference Lists"

    for group, keywords in GROUP_RULES:
        if group == "Reference Lists":
            continue
        if any(keyword in full_text for keyword in keywords):
            return group

    if language in {"TypeScript", "JavaScript", "Python", "Go", "Rust", "Zig"}:
        return "Developer Tools"
    if language in {"C", "C++", "C#", "PowerShell", "Shell", "Batchfile", "Kotlin", "Dart"}:
        return "System, Desktop and Mobile"
    return "Other"


def sort_active_key(repo: Dict[str, Any]) -> Tuple[datetime, int]:
    pushed = parse_dt(str(repo.get("pushed_at") or ""))
    if pushed is None:
        pushed = datetime(1970, 1, 1, tzinfo=timezone.utc)
    stars = int(repo.get("stargazer_count") or 0)
    return pushed, stars


def sort_slow_key(repo: Dict[str, Any]) -> Tuple[int, datetime]:
    stars = int(repo.get("stargazer_count") or 0)
    starred_at = parse_dt(str(repo.get("starred_at") or ""))
    if starred_at is None:
        starred_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return stars, starred_at


def split_by_activity(
    repos: Iterable[Dict[str, Any]], snapshot_dt: datetime
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    threshold = snapshot_dt - timedelta(days=ACTIVE_DAYS)
    active: List[Dict[str, Any]] = []
    slow: List[Dict[str, Any]] = []

    for repo in repos:
        pushed = parse_dt(str(repo.get("pushed_at") or ""))
        if pushed and pushed >= threshold:
            active.append(repo)
        else:
            slow.append(repo)
    return active, slow


def group_repositories(
    repos: List[Dict[str, Any]], mode: str
) -> "OrderedDict[str, List[Dict[str, Any]]]":
    grouped: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for group_name, _ in GROUP_RULES:
        grouped[group_name] = []
    grouped["Other"] = []

    if mode == "slow":
        ordered = sorted(repos, key=sort_slow_key, reverse=True)
    else:
        ordered = sorted(repos, key=sort_active_key, reverse=True)

    for repo in ordered:
        grouped[classify_repo(repo)].append(repo)

    return grouped


def freshness_label(repo: Dict[str, Any], snapshot_dt: datetime) -> str:
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




def render_group_index(grouped: "OrderedDict[str, List[Dict[str, Any]]]") -> List[str]:
    lines: List[str] = []
    for group_name, repos in grouped.items():
        if repos:
            emoji = GROUP_EMOJIS.get(group_name, "📦")
            lines.append(
                f"- {emoji} [{group_name}](#{slugify(group_name)}) ({len(repos)})"
            )
    return lines


def render_repo_entry(repo: Dict[str, Any], snapshot_dt: datetime) -> List[str]:
    name = str(repo["name_with_owner"])
    url = str(repo["url"])
    description = sanitize_text(repo.get("description"))
    language = str(repo.get("primary_language") or "Unknown")
    stars = int(repo.get("stargazer_count") or 0)
    pushed = fmt_date(str(repo.get("pushed_at") or ""))
    archived = bool(repo.get("is_archived"))
    status = freshness_label(repo, snapshot_dt)

    parts = [language, f"★ {fmt_stars_short(stars)}", f"pushed {pushed}", status]
    if archived:
        parts.append("archived")
    meta = " | ".join(parts)

    return [
        f"- **[{name}]({url})**",
        f"  {description}<br>",
        f"  <sub>{meta}</sub>",
    ]


def build_readme(
    login: str, repositories: List[Dict[str, Any]], generated_at_iso: str
) -> str:
    snapshot_dt = parse_dt(generated_at_iso) or datetime.now(timezone.utc)
    active, slow = split_by_activity(repositories, snapshot_dt)
    grouped_all = group_repositories(repositories, mode="active")
    grouped_active = group_repositories(active, mode="active")
    grouped_slow = group_repositories(slow, mode="slow")

    recent_threshold = snapshot_dt - timedelta(days=RECENT_STAR_DAYS)
    recently_starred = [
        repo
        for repo in sorted(
            repositories,
            key=lambda r: parse_dt(str(r.get("starred_at") or ""))
            or datetime(1970, 1, 1, tzinfo=timezone.utc),
            reverse=True,
        )
        if (parse_dt(str(repo.get("starred_at") or "")) or datetime(1970, 1, 1, tzinfo=timezone.utc))
        >= recent_threshold
    ][:10]

    total = len(repositories)
    active_count = len(active)
    slow_count = len(slow)

    badge_total = f"![Total](https://img.shields.io/badge/total-{total}-blue?style=flat-square)"
    badge_active = f"![Active](https://img.shields.io/badge/active-{active_count}-brightgreen?style=flat-square)"
    badge_slow = f"![Slower](https://img.shields.io/badge/slower-{slow_count}-orange?style=flat-square)"
    badge_update = "![Auto-update](https://img.shields.io/badge/auto--update-daily-lightgrey?style=flat-square)"

    lines: List[str] = [
        "# Awesome Starred Projects",
        "",
        f"Auto-generated list of GitHub stars for **{login}**.",
        "",
        f"{badge_total} {badge_active} {badge_slow} {badge_update}",
        "",
        f"> Last snapshot: {fmt_datetime_utc(generated_at_iso)}",
        "",
        "## Group Index",
        "",
    ]
    lines.extend(render_group_index(grouped_all))

    # Top 5 by stars
    top5 = sorted(repositories, key=lambda r: int(r.get("stargazer_count") or 0), reverse=True)[:5]
    lines.extend(["", "## Top 5 by Stars", ""])
    lines.append("| # | Repository | Stars | Language |")
    lines.append("|---|-----------|-------|----------|")
    for i, repo in enumerate(top5, 1):
        name = str(repo["name_with_owner"])
        url = str(repo["url"])
        stars = int(repo.get("stargazer_count") or 0)
        lang = str(repo.get("primary_language") or "—")
        lines.append(f"| {i} | [{name}]({url}) | ⭐ {fmt_stars_short(stars)} | `{lang}` |")

    lines.extend(["", f"## Recently Starred (last {RECENT_STAR_DAYS} days)", ""])
    if recently_starred:
        for idx, repo in enumerate(recently_starred, start=1):
            name = str(repo["name_with_owner"])
            url = str(repo["url"])
            desc = sanitize_text(repo.get("description"), max_len=95)
            lines.append(f"{idx}. **[{name}]({url})** — {desc}")
    else:
        lines.append("*No recently starred repositories.*")

    lines.extend(["", f"## Active Projects ({active_count})", ""])
    for group_name, group_repos in grouped_active.items():
        if not group_repos:
            continue
        emoji = GROUP_EMOJIS.get(group_name, "📦")
        lines.append(
            f'<h3 id="{slugify(group_name)}">{emoji} {group_name} '
            f'<sup>({len(group_repos)})</sup></h3>'
        )
        lines.append("")
        for repo in group_repos:
            lines.extend(render_repo_entry(repo, snapshot_dt))
            lines.append("")

    lines.extend([f"## Slower Projects ({slow_count})", ""])
    for group_name, group_repos in grouped_slow.items():
        if not group_repos:
            continue
        emoji = GROUP_EMOJIS.get(group_name, "📦")
        lines.append(
            f'<h3 id="{slugify(group_name)}-slow">{emoji} {group_name} '
            f'<sup>({len(group_repos)})</sup></h3>'
        )
        lines.append("")
        for repo in group_repos:
            lines.extend(render_repo_entry(repo, snapshot_dt))
            lines.append("")

    lines.extend([
        "---",
        "",
        "## How this works",
        "",
        "This list is **auto-generated daily** via GitHub Actions.",
        "A Python script fetches all starred repositories using the GitHub GraphQL API,",
        "classifies them into groups, and commits the updated `README.md` and `data/starred-repos.json`.",
        "",
        f"*Generated by [generate_awesome.py](scripts/generate_awesome.py)*",
    ])

    return "\n".join(lines).strip() + "\n"


def fetch_starred_repositories(token: str) -> Dict[str, Any]:
    all_repos: List[Dict[str, Any]] = []
    after: Optional[str] = None
    login: Optional[str] = None

    while True:
        data = github_graphql(token, GRAPHQL_QUERY, {"after": after})
        viewer = data["viewer"]
        login = viewer["login"]
        connection = viewer["starredRepositories"]
        edges = connection["edges"]

        for edge in edges:
            node = edge["node"]
            default_branch = node.get("defaultBranchRef") or {}
            target = default_branch.get("target") or {}
            if target.get("__typename") == "Commit":
                last_commit = target.get("committedDate")
                last_commit_sha = target.get("oid")
            else:
                last_commit = None
                last_commit_sha = None

            all_repos.append(
                {
                    "name_with_owner": node["nameWithOwner"],
                    "url": node["url"],
                    "description": node.get("description"),
                    "stargazer_count": node.get("stargazerCount", 0),
                    "primary_language": (node.get("primaryLanguage") or {}).get("name"),
                    "pushed_at": node.get("pushedAt"),
                    "updated_at": node.get("updatedAt"),
                    "starred_at": edge.get("starredAt"),
                    "default_branch": default_branch.get("name"),
                    "last_commit_at": last_commit,
                    "last_commit_sha": last_commit_sha,
                    "is_archived": node.get("isArchived", False),
                }
            )

        page = connection["pageInfo"]
        if not page["hasNextPage"]:
            break
        after = page["endCursor"]

    if not login:
        raise RuntimeError("Could not determine GitHub username from token.")

    return {"login": login, "repositories": all_repos}


def write_outputs(login: str, repositories: List[Dict[str, Any]]) -> None:
    README_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    generated_at_iso = datetime.now(timezone.utc).isoformat()
    readme_content = build_readme(login, repositories, generated_at_iso)
    README_PATH.write_text(readme_content, encoding="utf-8")

    payload = {
        "generated_at": generated_at_iso,
        "login": login,
        "count": len(repositories),
        "repositories": repositories,
    }
    JSON_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    token = require_token()
    result = fetch_starred_repositories(token)
    login = result["login"]
    repositories = result["repositories"]
    write_outputs(login, repositories)
    print(f"Generated README and JSON for {len(repositories)} starred repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
