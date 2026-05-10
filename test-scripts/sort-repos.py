from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


API_URL_TEMPLATE = "https://api.github.com/repos/{owner}/{repo}"
GROUPS = (
    ("Over 10k stars", 10_000),
    ("Over 1k stars", 1_000),
    ("Over 100 stars", 100),
    ("Over 10 stars", 10),
)
LOGGER = logging.getLogger("pepip.sort_repos")


@dataclass(frozen=True)
class RepoStats:
    owner: str
    name: str
    stars: int
    forks: int

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"

    @property
    def markdown_link(self) -> str:
        return f"[{self.owner}/{self.name}]({self.url})"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch GitHub stars/forks for repositories and print a grouped "
            "markdown table."
        )
    )
    parser.add_argument(
        "repos_file",
        nargs="?",
        default=Path(__file__).resolve().parent / "uv_repos_success.txt",
        type=Path,
        help="Path to a file containing GitHub repository URLs.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logs and only print the final markdown table.",
    )
    return parser.parse_args()


def _configure_logging(*, quiet: bool) -> None:
    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)


def _read_repo_urls(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and line.strip().startswith("https://github.com/")
    ]


def _split_repo_url(url: str) -> tuple[str, str]:
    parts = url.rstrip("/").split("/")
    if len(parts) < 5:
        raise ValueError(f"Unsupported GitHub repository URL: {url}")
    return parts[-2], parts[-1]


def _github_request(url: str) -> request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "pepip-sort-repos",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return request.Request(url, headers=headers)


def _fetch_repo_stats(repo_url: str) -> RepoStats:
    owner, repo = _split_repo_url(repo_url)
    api_url = API_URL_TEMPLATE.format(owner=owner, repo=repo)
    req = _github_request(api_url)
    LOGGER.info("Fetching %s/%s via GitHub API", owner, repo)

    try:
        with request.urlopen(req) as response:
            payload = json.load(response)
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        if exc.code == 403:
            try:
                LOGGER.info("API rate-limited for %s/%s; falling back to gh", owner, repo)
                return _fetch_repo_stats_with_gh(owner, repo)
            except RuntimeError:
                pass
            raise RuntimeError(
                "GitHub API rate limit exceeded. Set GITHUB_TOKEN or authenticate "
                f"`gh` to continue. Repository: {repo_url}. Response: {message}"
            ) from exc
        raise RuntimeError(f"GitHub API request failed for {repo_url}: {message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach GitHub API for {repo_url}: {exc}") from exc

    return RepoStats(
        owner=owner,
        name=repo,
        stars=int(payload["stargazers_count"]),
        forks=int(payload["forks_count"]),
    )


def _fetch_repo_stats_with_gh(owner: str, repo: str) -> RepoStats:
    LOGGER.info("Fetching %s/%s via gh CLI", owner, repo)
    result = subprocess.run(
        [
            "gh",
            "repo",
            "view",
            f"{owner}/{repo}",
            "--json",
            "stargazerCount,forkCount",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    payload = json.loads(result.stdout)
    return RepoStats(
        owner=owner,
        name=repo,
        stars=int(payload["stargazerCount"]),
        forks=int(payload["forkCount"]),
    )


def _format_count(value: int) -> str:
    if value >= 1_000_000:
        text = f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        text = f"{value / 1_000:.1f}k"
    else:
        return str(value)
    return text.replace(".0", "")


def _group_repos(repos: list[RepoStats]) -> list[tuple[str, list[RepoStats]]]:
    grouped: list[tuple[str, list[RepoStats]]] = []
    remaining = repos

    for label, threshold in GROUPS:
        current = [repo for repo in remaining if repo.stars >= threshold]
        grouped.append((label, current))
        remaining = [repo for repo in remaining if repo.stars < threshold]

    if remaining:
        grouped.append(("Under 10 stars", remaining))
    return grouped


def _render_table(repos: list[RepoStats]) -> str:
    lines = [
        "| Repository                                                  | Stars | Forks |",
        "| ----------------------------------------------------------- | ----: | ----: |",
    ]

    for label, grouped_repos in _group_repos(repos):
        if not grouped_repos:
            continue
        lines.append(f"{label}:                                               |       |       |")
        for repo in grouped_repos:
            lines.append(
                f"| {repo.markdown_link:<59} | {(_format_count(repo.stars)):>5} | "
                f"{(_format_count(repo.forks)):>5} |"
            )

    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    _configure_logging(quiet=args.quiet)
    repo_urls = _read_repo_urls(args.repos_file)

    if not repo_urls:
        print(f"No repository URLs found in {args.repos_file}", file=sys.stderr)
        return 1

    LOGGER.info("Loaded %d repository URLs from %s", len(repo_urls), args.repos_file)
    repos: list[RepoStats] = []
    total = len(repo_urls)

    for index, repo_url in enumerate(repo_urls, start=1):
        LOGGER.info("[%d/%d] Processing %s", index, total, repo_url)
        repos.append(_fetch_repo_stats(repo_url))

    repos.sort(key=lambda repo: (-repo.stars, repo.owner.lower(), repo.name.lower()))
    LOGGER.info("Finished fetching %d repositories; rendering markdown table", len(repos))
    print(_render_table(repos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
