import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from apps_data import REPO_METADATA

load_dotenv()

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
BOT_IDENTIFIER = os.getenv("BOT_IDENTIFIER", "telegram-showcase").strip() or "telegram-showcase"
MAX_REPOS = int(os.getenv("MAX_REPOS", "20"))
SYNC_INTERVAL_SECONDS = int(os.getenv("TELEGRAM_SYNC_INTERVAL_SECONDS", "86400"))
RUN_ONCE = os.getenv("TELEGRAM_SYNC_RUN_ONCE", "0") == "1"
SNAPSHOT_PATH = Path(os.getenv("PROJECTS_SNAPSHOT_PATH", "/data/projects_snapshot.json"))
GITHUB_MAX_RETRIES = int(os.getenv("GITHUB_MAX_RETRIES", "2"))
GITHUB_RETRY_BACKOFF_SECONDS = float(os.getenv("GITHUB_RETRY_BACKOFF_SECONDS", "0.8"))

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def github_request(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{BOT_IDENTIFIER}-sync",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    request = Request(url, headers=headers)
    for attempt in range(GITHUB_MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as err:
            should_retry = err.code in (429, 500, 502, 503, 504)
            if should_retry and attempt < GITHUB_MAX_RETRIES:
                sleep_seconds = GITHUB_RETRY_BACKOFF_SECONDS * (2**attempt)
                logger.warning(
                    "retry_http url=%s code=%s attempt=%s/%s sleep=%.2fs",
                    url,
                    err.code,
                    attempt + 1,
                    GITHUB_MAX_RETRIES + 1,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue
            raise
        except (URLError, TimeoutError) as err:
            if attempt < GITHUB_MAX_RETRIES:
                sleep_seconds = GITHUB_RETRY_BACKOFF_SECONDS * (2**attempt)
                logger.warning(
                    "retry_net url=%s attempt=%s/%s sleep=%.2fs error=%s",
                    url,
                    attempt + 1,
                    GITHUB_MAX_RETRIES + 1,
                    sleep_seconds,
                    err,
                )
                time.sleep(sleep_seconds)
                continue
            raise

    raise RuntimeError("Unexpected retry loop exit")


def fetch_release_info(repo_name: str) -> dict:
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/releases/latest"
    try:
        release = github_request(url)
    except HTTPError as err:
        if err.code == 404:
            return {
                "release_mode": "github_release",
                "release_version": "No release version",
                "release_download_url": None,
                "release_published_at": "-",
                "release_is_prerelease": False,
                "release_has_release": False,
            }
        raise

    if not isinstance(release, dict):
        return {
            "release_mode": "github_release",
            "release_version": "No release version",
            "release_download_url": None,
            "release_published_at": "-",
            "release_is_prerelease": False,
            "release_has_release": False,
        }

    version = release.get("name") or release.get("tag_name") or "No release version"
    published_at = release.get("published_at") or "-"

    download_url = None
    assets = release.get("assets") or []
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            asset_url = asset.get("browser_download_url")
            if (
                isinstance(asset_url, str)
                and asset_url.split("?", 1)[0].lower().endswith(".apk")
            ):
                download_url = asset_url
                break

    return {
        "release_mode": "github_release",
        "release_version": str(version),
        "release_download_url": download_url,
        "release_published_at": str(published_at),
        "release_is_prerelease": bool(release.get("prerelease", False)),
        "release_has_release": True,
    }


def write_snapshot(projects: list[dict]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "github_username": GITHUB_USERNAME,
        "projects": projects,
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SNAPSHOT_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SNAPSHOT_PATH)


def build_projects_snapshot() -> list[dict]:
    configured_repo_names = list(REPO_METADATA.keys())
    if not configured_repo_names:
        return []

    max_items = min(max(MAX_REPOS, 1), len(configured_repo_names))
    selected_names = configured_repo_names[:max_items]
    projects: list[dict] = []

    for repo_name in selected_names:
        repo_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}"
        repo = github_request(repo_url)
        if not isinstance(repo, dict):
            continue
        if repo.get("private"):
            continue

        metadata = REPO_METADATA.get(repo_name, {})
        release_strategy = metadata.get("release_strategy", "github_release")
        if release_strategy == "none":
            release_info = {
                "release_mode": "direct_publish",
                "release_version": "Direct publish (no release)",
                "release_download_url": None,
                "release_published_at": "-",
                "release_is_prerelease": False,
                "release_has_release": False,
            }
        else:
            release_info = fetch_release_info(repo_name)

        projects.append(
            {
                "name": repo.get("name", repo_name),
                "html_url": repo.get("html_url", ""),
                "pushed_at": repo.get("pushed_at"),
                **release_info,
            }
        )

    return projects


def sync_once() -> None:
    projects = build_projects_snapshot()
    write_snapshot(projects)
    logger.info("snapshot_updated path=%s projects=%s", SNAPSHOT_PATH, len(projects))


def main() -> None:
    if not GITHUB_USERNAME:
        raise ValueError("GITHUB_USERNAME not found. Please set GITHUB_USERNAME in your .env file.")

    while True:
        try:
            sync_once()
        except Exception:
            logger.exception("snapshot_sync_failed")

        if RUN_ONCE:
            break

        sleep_seconds = max(SYNC_INTERVAL_SECONDS, 300)
        logger.info("next_sync_in_seconds=%s", sleep_seconds)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
