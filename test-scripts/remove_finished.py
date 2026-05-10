from pathlib import Path


def _read_urls(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and line.strip().startswith("http")
    }


def _remove_urls(path: Path, urls_to_remove: set[str]) -> int:
    lines = path.read_text().splitlines(keepends=True)
    filtered_lines = [
        line
        for line in lines
        if not (line.strip().startswith("http") and line.strip() in urls_to_remove)
    ]
    path.write_text("".join(filtered_lines))
    return len(lines) - len(filtered_lines)


def main() -> None:
    scripts_dir = Path(__file__).resolve().parent
    failed_path = scripts_dir / "uv_repos_failed.txt"
    repos_path = scripts_dir / "uv_repos.txt"
    success_path = scripts_dir / "uv_repos_success.txt"

    failed_urls = _read_urls(failed_path)
    removed_from_repos = _remove_urls(repos_path, failed_urls)
    removed_from_success = _remove_urls(success_path, failed_urls)

    print(f"Removed {removed_from_repos} failed URLs from {repos_path.name}")
    print(f"Removed {removed_from_success} failed URLs from {success_path.name}")


if __name__ == "__main__":
    main()
