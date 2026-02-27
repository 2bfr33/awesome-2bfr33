#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.github.com/graphql"
README_PATH = Path(os.getenv("OUTPUT_README", "README.md"))
JSON_PATH = Path(os.getenv("OUTPUT_JSON", "data/starred-repos.json"))
MAX_DESC_LEN = int(os.getenv("MAX_DESC_LEN", "140"))

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


def format_iso_date(iso_value: Optional[str]) -> str:
    if not iso_value:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return iso_value
    return dt.strftime("%Y-%m-%d")


def sanitize_md(text: Optional[str], max_len: int = MAX_DESC_LEN) -> str:
    if not text:
        return "-"
    cleaned = " ".join(text.split()).replace("|", "\\|")
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


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
                    "primary_language": (
                        node.get("primaryLanguage") or {}
                    ).get("name"),
                    "pushed_at": node.get("pushedAt"),
                    "updated_at": node.get("updatedAt"),
                    "starred_at": edge.get("starredAt"),
                    "default_branch": default_branch.get("name"),
                    "last_commit_at": last_commit,
                    "last_commit_sha": last_commit_sha,
                }
            )

        page = connection["pageInfo"]
        if not page["hasNextPage"]:
            break
        after = page["endCursor"]

    if not login:
        raise RuntimeError("Could not determine GitHub username from token.")

    return {"login": login, "repositories": all_repos}


def build_readme(login: str, repositories: List[Dict[str, Any]]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: List[str] = [
        "# Awesome Starred Projects",
        "",
        f"Auto-generated list of GitHub stars for **{login}**.",
        "",
        f"Last updated: `{generated_at}`",
        f"Total repositories: **{len(repositories)}**",
        "",
        "## Setup",
        "",
        "1. Create a GitHub token and add it to repository secret `GH_STAR_PAT`.",
        "2. Run workflow `Update Awesome List` manually, or wait for the daily schedule.",
        "3. The workflow regenerates this README and `data/starred-repos.json`.",
        "",
        "## Starred Repositories",
        "",
        "| # | Repository | Description | Language | Stars | Last push | Last commit | Starred at |",
        "|---:|---|---|---|---:|---|---|---|",
    ]

    for idx, repo in enumerate(repositories, start=1):
        name = repo["name_with_owner"]
        url = repo["url"]
        description = sanitize_md(repo.get("description"))
        language = sanitize_md(repo.get("primary_language"), max_len=40)
        stars = repo.get("stargazer_count", 0)
        pushed = format_iso_date(repo.get("pushed_at"))
        last_commit = format_iso_date(repo.get("last_commit_at"))
        starred_at = format_iso_date(repo.get("starred_at"))
        lines.append(
            f"| {idx} | [{name}]({url}) | {description} | {language} | {stars} | {pushed} | {last_commit} | {starred_at} |"
        )

    lines.append("")
    return "\n".join(lines)


def write_outputs(login: str, repositories: List[Dict[str, Any]]) -> None:
    README_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    readme_content = build_readme(login, repositories)
    README_PATH.write_text(readme_content, encoding="utf-8")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "login": login,
        "count": len(repositories),
        "repositories": repositories,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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
