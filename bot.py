import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from apps_data import REPO_METADATA

load_dotenv()

TOKEN = os.getenv("TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
BOT_TITLE = os.getenv("BOT_TITLE", "Project Showcase")
BOT_FOOTER = os.getenv("BOT_FOOTER", "Powered by Telegram + GitHub")
BOT_IDENTIFIER = os.getenv("BOT_IDENTIFIER", "telegram-showcase").strip() or "telegram-showcase"
PROJECTS_SNAPSHOT_PATH = Path(
    os.getenv("PROJECTS_SNAPSHOT_PATH", "/data/projects_snapshot.json")
)
LANG_STORE_PATH = Path(
    os.getenv("LANG_STORE_PATH", str(Path(__file__).with_name("user_languages.json")))
)
MAX_REPOS = int(os.getenv("MAX_REPOS", "20"))
GITHUB_CACHE_TTL_SECONDS = int(os.getenv("GITHUB_CACHE_TTL_SECONDS", "300"))
GITHUB_MAX_RETRIES = int(os.getenv("GITHUB_MAX_RETRIES", "2"))
GITHUB_RETRY_BACKOFF_SECONDS = float(os.getenv("GITHUB_RETRY_BACKOFF_SECONDS", "0.8"))

if not TOKEN:
    raise ValueError("TOKEN not found. Please set TOKEN in your .env file.")
if not GITHUB_USERNAME:
    raise ValueError("GITHUB_USERNAME not found. Please set GITHUB_USERNAME in your .env file.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

TEXTS = {
    "de": {
        "welcome": (
            "✨ <b>Willkommen beim Project Showcase Bot</b>\n"
            "Ein kompakter Projekt-Showcase direkt aus GitHub."
        ),
        "choose_language": "Bitte wähle deine Sprache:",
        "language_changed": "Sprache auf Deutsch gesetzt.",
        "intro": (
            "🚀 <b>Was du hier machen kannst</b>\n"
            "• Projekte inkl. Release-Status ansehen\n"
            "• APK-Releases, Dokus und Install-Guides direkt öffnen\n"
            "• Sprache jederzeit umschalten"
        ),
        "help": (
            "🧭 <b>Hilfe & Befehle</b>\n\n"
            "<b>/start</b> - Startseite und Sprachauswahl\n"
            "<b>/apps</b> - Projekte anzeigen (mit Kategorien)\n"
            "<b>/language</b> - Sprache wechseln\n"
            "<b>/help</b> - Diese Hilfe anzeigen"
        ),
        "quick_actions": "Schnellzugriff:",
        "btn_apps": "📁 Projects",
        "btn_help": "🧭 Hilfe",
        "btn_language": "🌐 Sprache",
        "language_panel": "🌐 <b>Sprache auswählen</b>",
        "choose_category": "📂 <b>Kategorie waehlen</b>",
        "apps_loading": "Projektdaten werden geladen...",
        "apps_empty": "Keine konfigurierten Projekte gefunden.",
        "apps_empty_filtered": "Keine Projekte in dieser Kategorie gefunden: {category}",
        "apps_error": "Projektdaten-Snapshot ist nicht verfügbar. Bitte später erneut probieren.",
        "apps_rate_limited": "GitHub-Limit erreicht. Bitte erneut versuchen: {reset}",
        "open_github": "Auf GitHub öffnen",
        "download_latest_release": "Neueste Release herunterladen",
        "refresh": "Neu laden",
        "repo": "Repository",
        "category": "Kategorie",
        "updated": "Zuletzt geändert",
        "release_version": "Release-Version",
        "release_published": "Release veröffentlicht",
        "release_status": "Release-Status",
        "release_status_stable": "🟢 Stabil",
        "release_status_prerelease": "🟡 Pre-release",
        "release_status_none": "🔴 Noch keine Releases",
        "release_status_direct_publish": "ℹ️ Ohne GitHub-Releases veroeffentlicht",
        "no_release": "Keine Release-Version",
        "direct_publish_version": "Direkt veroeffentlicht (ohne Release)",
        "no_description": "Keine Beschreibung vorhanden.",
        "all_apps": "Alle Projekte",
        "navigation_hint": "Nutze die Pfeile, um durch die Projekte zu wechseln.",
        "session_expired": "Sitzung abgelaufen. Bitte /apps erneut senden.",
        "language_button_de": "Deutsch",
        "language_button_en": "English",
        "summary": "Kurzbeschreibung",
        "featured": "⭐ Hervorgehoben",
        "status_recent": "🟢 Kürzlich aktualisiert",
        "status_active": "🟡 Aktiv gepflegt",
        "status_stable": "🟢 Stabil",
        "filter_all": "🌍 Alle",
        "filter_android": "📱 Android",
        "filter_browser": "🌐 Browser",
        "filter_hardware": "🛠️ Hardware",
        "filter_desktop": "🧰 Desktop",
        "filter_theme": "🎨 Theme",
        "filter_misc": "🗃️ Sonstiges",
    },
    "en": {
        "welcome": (
            "✨ <b>Welcome to the Project Showcase Bot</b>\n"
            "A compact project showcase directly from GitHub."
        ),
        "choose_language": "Please choose your language:",
        "language_changed": "Language switched to English.",
        "intro": (
            "🚀 <b>What you can do here</b>\n"
            "• Browse projects with release status\n"
            "• Open APK releases, docs, and install guides directly\n"
            "• Switch language anytime"
        ),
        "help": (
            "🧭 <b>Help & Commands</b>\n\n"
            "<b>/start</b> - Start page and language picker\n"
            "<b>/apps</b> - Show projects (with categories)\n"
            "<b>/language</b> - Switch language\n"
            "<b>/help</b> - Show this help"
        ),
        "quick_actions": "Quick actions:",
        "btn_apps": "📁 Projects",
        "btn_help": "🧭 Help",
        "btn_language": "🌐 Language",
        "language_panel": "🌐 <b>Select language</b>",
        "choose_category": "📂 <b>Select category</b>",
        "apps_loading": "Loading project data...",
        "apps_empty": "No configured projects found.",
        "apps_empty_filtered": "No projects found in this category: {category}",
        "apps_error": "Project snapshot is not available right now. Please try again later.",
        "apps_rate_limited": "GitHub rate limit reached. Please try again: {reset}",
        "open_github": "Open on GitHub",
        "download_latest_release": "Download latest release",
        "refresh": "Refresh",
        "repo": "Repository",
        "category": "Category",
        "updated": "Last updated",
        "release_version": "Release version",
        "release_published": "Release published",
        "release_status": "Release status",
        "release_status_stable": "🟢 Stable",
        "release_status_prerelease": "🟡 Pre-release",
        "release_status_none": "🔴 No releases yet",
        "release_status_direct_publish": "ℹ️ Published without GitHub releases",
        "no_release": "No release version",
        "direct_publish_version": "Direct publish (no release)",
        "no_description": "No description available.",
        "all_apps": "All projects",
        "navigation_hint": "Use arrows to switch through the projects.",
        "session_expired": "Session expired. Please send /apps again.",
        "language_button_de": "Deutsch",
        "language_button_en": "English",
        "summary": "Summary",
        "featured": "⭐ Featured",
        "status_recent": "🟢 Recently updated",
        "status_active": "🟡 Actively maintained",
        "status_stable": "🟢 Stable",
        "filter_all": "🌍 All",
        "filter_android": "📱 Android",
        "filter_browser": "🌐 Browser",
        "filter_hardware": "🛠️ Hardware",
        "filter_desktop": "🧰 Desktop",
        "filter_theme": "🎨 Theme",
        "filter_misc": "🗃️ Misc",
    },
}


def collect_project_filters() -> tuple[str, ...]:
    categories = {"all"}
    for metadata in REPO_METADATA.values():
        category = metadata.get("category", "misc")
        if not isinstance(category, str):
            continue
        normalized = category.strip().lower()
        if normalized:
            categories.add(normalized)

    sorted_categories = sorted(categories - {"all"})
    return ("all", *sorted_categories)


PROJECT_FILTERS = collect_project_filters()


def load_user_languages() -> dict[int, str]:
    if not LANG_STORE_PATH.exists():
        return {}
    try:
        raw = json.loads(LANG_STORE_PATH.read_text(encoding="utf-8"))
        return {
            int(user_id): lang
            for user_id, lang in raw.items()
            if lang in ("de", "en")
        }
    except (OSError, ValueError, TypeError):
        logger.warning("Could not parse user language store. Starting with empty state.")
        return {}


def save_user_languages(languages: dict[int, str]) -> None:
    data = {str(user_id): lang for user_id, lang in languages.items()}
    try:
        LANG_STORE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        logger.exception("Could not persist user languages.")


user_languages: dict[int, str] = load_user_languages()
github_cache: dict[str, tuple[datetime, object]] = {}


class GitHubRateLimitError(Exception):
    def __init__(self, reset_at: datetime | None):
        super().__init__("GitHub API rate limit reached")
        self.reset_at = reset_at


class SnapshotLoadError(Exception):
    pass


def get_user_language(user_id: int, fallback_language_code: str | None = None) -> str:
    if user_id in user_languages:
        return user_languages[user_id]
    if fallback_language_code and fallback_language_code.lower().startswith("de"):
        return "de"
    return "en"


def t(lang: str, key: str) -> str:
    return TEXTS[lang][key]


def category_label(lang: str, category: str) -> str:
    mapping = {
        "all": t(lang, "filter_all"),
        "android": t(lang, "filter_android"),
        "browser": t(lang, "filter_browser"),
        "hardware": t(lang, "filter_hardware"),
        "desktop": t(lang, "filter_desktop"),
        "theme": t(lang, "filter_theme"),
        "misc": t(lang, "filter_misc"),
    }
    if category in mapping:
        return mapping[category]
    return category.replace("_", " ").title()


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(TEXTS["de"]["language_button_de"], callback_data="lang_de"),
            InlineKeyboardButton(TEXTS["en"]["language_button_en"], callback_data="lang_en"),
        ]]
    )


def quick_actions_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(lang, "btn_apps"), callback_data="ui_apps"),
                InlineKeyboardButton(t(lang, "btn_help"), callback_data="ui_help"),
            ],
            [InlineKeyboardButton(t(lang, "btn_language"), callback_data="ui_language")],
        ]
    )


def apps_filter_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(category_label(lang, category), callback_data=f"apps_filter_{category}")
        for category in PROJECT_FILTERS
    ]
    rows = [buttons[index:index + 3] for index in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(rows)


def apps_keyboard(
    lang: str,
    index: int,
    total: int,
    action_buttons: list[dict],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    valid_actions = [
        action for action in action_buttons
        if isinstance(action.get("text"), str) and isinstance(action.get("url"), str)
    ]

    if valid_actions:
        first_row = [InlineKeyboardButton(item["text"], url=item["url"]) for item in valid_actions[:2]]
        rows.append(first_row)
        if len(valid_actions) > 2:
            second_row = [InlineKeyboardButton(item["text"], url=item["url"]) for item in valid_actions[2:4]]
            rows.append(second_row)

    rows.append(
        [
            InlineKeyboardButton("◀️", callback_data="apps_prev"),
            InlineKeyboardButton(f"{index + 1}/{total}", callback_data="apps_noop"),
            InlineKeyboardButton("▶️", callback_data="apps_next"),
        ]
    )
    rows.append([InlineKeyboardButton(f"🔄 {t(lang, 'refresh')}", callback_data="apps_refresh")])

    return InlineKeyboardMarkup(rows)


def github_request(url: str):
    now = datetime.now(timezone.utc)
    cached = github_cache.get(url)
    if cached:
        cache_time, payload = cached
        if now - cache_time <= timedelta(seconds=GITHUB_CACHE_TTL_SECONDS):
            return payload

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{BOT_IDENTIFIER}-bot",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    request = Request(url, headers=headers)

    for attempt in range(GITHUB_MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
                github_cache[url] = (now, payload)
                return payload
        except HTTPError as err:
            remaining = err.headers.get("X-RateLimit-Remaining")
            if err.code == 403 and remaining == "0":
                reset_raw = err.headers.get("X-RateLimit-Reset")
                reset_at = None
                if reset_raw and reset_raw.isdigit():
                    reset_at = datetime.fromtimestamp(int(reset_raw), tz=timezone.utc)
                raise GitHubRateLimitError(reset_at) from err

            should_retry = err.code in (429, 500, 502, 503, 504)
            if should_retry and attempt < GITHUB_MAX_RETRIES:
                sleep_seconds = GITHUB_RETRY_BACKOFF_SECONDS * (2**attempt)
                logger.warning(
                    "github_retry_http url=%s code=%s attempt=%s/%s sleep=%.2fs",
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
                    "github_retry_network url=%s attempt=%s/%s sleep=%.2fs error=%s",
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


def fetch_github_repositories(username: str, limit: int) -> list[dict]:
    configured_repo_names = list(REPO_METADATA.keys())
    if not configured_repo_names:
        return []

    max_items = min(max(limit, 1), len(configured_repo_names))
    selected_names = configured_repo_names[:max_items]

    repos: list[dict] = []
    for repo_name in selected_names:
        url = f"https://api.github.com/repos/{username}/{repo_name}"
        repo = github_request(url)
        if not isinstance(repo, dict):
            continue
        if repo.get("private"):
            continue
        repos.append(repo)
    return repos


def fetch_latest_release_info(username: str, repo_name: str, lang: str) -> dict:
    url = f"https://api.github.com/repos/{username}/{repo_name}/releases/latest"
    try:
        release = github_request(url)
    except HTTPError as err:
        if err.code == 404:
            return {
                "version": t(lang, "no_release"),
                "download_url": None,
                "published_at": "-",
                "is_prerelease": False,
                "has_release": False,
            }
        raise

    if not isinstance(release, dict):
        return {
            "version": t(lang, "no_release"),
            "download_url": None,
            "published_at": "-",
            "is_prerelease": False,
            "has_release": False,
        }

    version = release.get("name") or release.get("tag_name") or t(lang, "no_release")
    published_at = format_datetime_for_lang(parse_iso_datetime(release.get("published_at")), lang)

    assets = release.get("assets") or []
    download_url = None
    if isinstance(assets, list) and assets:
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
        "version": str(version),
        "download_url": download_url,
        "published_at": published_at,
        "is_prerelease": bool(release.get("prerelease", False)),
        "has_release": True,
    }


def app_metadata(repo: dict) -> dict | None:
    return REPO_METADATA.get(repo.get("name", ""))


def app_description(repo: dict, lang: str) -> str:
    metadata = app_metadata(repo)
    if metadata:
        return metadata["description"][lang]
    description = repo.get("description")
    return description if description else t(lang, "no_description")


def app_display_name(repo: dict) -> str:
    metadata = app_metadata(repo)
    if metadata:
        return metadata["display_name"]
    return repo.get("name", "").replace("_", " ")


def app_emoji(repo: dict) -> str:
    metadata = app_metadata(repo)
    if metadata:
        return metadata["emoji"]
    return "🚀"


def app_featured(repo: dict) -> bool:
    metadata = app_metadata(repo)
    if not metadata:
        return False
    return bool(metadata.get("featured", False))


def app_category(repo: dict) -> str:
    metadata = app_metadata(repo)
    if not metadata:
        return "misc"
    category = str(metadata.get("category", "misc")).strip().lower()
    return category if category in PROJECT_FILTERS else "misc"


def app_release_strategy(repo: dict) -> str:
    metadata = app_metadata(repo)
    if not metadata:
        return "github_release"
    strategy = metadata.get("release_strategy", "github_release")
    return strategy if strategy in ("github_release", "none") else "github_release"


def app_custom_links(repo: dict, lang: str) -> list[dict]:
    metadata = app_metadata(repo)
    if not metadata:
        return []

    links = metadata.get("links") or []
    result: list[dict] = []
    for item in links:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        label_obj = item.get("label", {})
        label = None
        if isinstance(label_obj, dict):
            label = label_obj.get(lang) or label_obj.get("en")
        if isinstance(label, str) and isinstance(url, str):
            result.append({"text": f"🧩 {label}", "url": url})
    return result


def filter_apps(apps: list[dict], selected_filter: str) -> list[dict]:
    if selected_filter == "all":
        return apps
    return [app for app in apps if app.get("category") == selected_filter]


def parse_iso_datetime(iso_date: str | None) -> datetime | None:
    if not iso_date:
        return None
    try:
        return datetime.strptime(iso_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def format_datetime_for_lang(dt: datetime | None, lang: str) -> str:
    if not dt:
        return "-"
    if lang == "de":
        return dt.strftime("%d.%m.%Y %H:%M UTC")
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def app_status_badge(updated_dt: datetime | None, lang: str) -> str:
    if not updated_dt:
        return t(lang, "status_stable")

    age_days = (datetime.now(timezone.utc) - updated_dt).days
    if age_days <= 7:
        return t(lang, "status_recent")
    if age_days <= 30:
        return t(lang, "status_active")
    return t(lang, "status_stable")


def release_status_label(lang: str, has_release: bool, is_prerelease: bool) -> str:
    if not has_release:
        return t(lang, "release_status_none")
    if is_prerelease:
        return t(lang, "release_status_prerelease")
    return t(lang, "release_status_stable")


def direct_publish_release_info(lang: str) -> dict:
    return {
        "version": t(lang, "direct_publish_version"),
        "download_url": None,
        "published_at": "-",
        "is_prerelease": False,
        "has_release": False,
        "release_status": t(lang, "release_status_direct_publish"),
    }


def build_app_message(lang: str, app: dict, index: int, total: int) -> str:
    badges = [app["status_badge"]]
    if app["featured"]:
        badges.append(t(lang, "featured"))

    release_line = f"🏷️ <b>{t(lang, 'release_version')}:</b> {escape(app['release_version'])}"
    if app["release_published"] != "-":
        release_line += f"\n📅 <b>{t(lang, 'release_published')}:</b> {escape(app['release_published'])}"
    release_line += f"\n🧭 <b>{t(lang, 'release_status')}:</b> {escape(app['release_status'])}"

    return (
        f"{app['emoji']} <b>{escape(app['name'])}</b>\n"
        f"{' | '.join(badges)}\n"
        f"━━━━━━━━━━━━\n"
        f"🧾 <b>{t(lang, 'repo')}:</b> <code>{escape(app['repo_name'])}</code>\n"
        f"🗂️ <b>{t(lang, 'category')}:</b> {escape(category_label(lang, app['category']))}\n"
        f"🕒 <b>{t(lang, 'updated')}:</b> {escape(app['updated'])}\n"
        f"{release_line}\n\n"
        f"📌 <b>{t(lang, 'summary')}:</b>\n"
        f"{escape(app['description'])}\n\n"
        f"━━━━━━━━━━━━\n"
        f"<b>{t(lang, 'all_apps')}</b> {index + 1}/{total}\n"
        f"{t(lang, 'navigation_hint')}\n"
        f"<i>{escape(BOT_FOOTER)}</i>"
    )


def format_rate_limit_reset(reset_at: datetime | None, lang: str) -> str:
    if not reset_at:
        return "-"
    return format_datetime_for_lang(reset_at, lang)


def build_apps_state(repos: list[dict], lang: str) -> list[dict]:
    result: list[dict] = []
    for repo in repos:
        repo_name = repo.get("name", "")
        if app_release_strategy(repo) == "none":
            release_info = direct_publish_release_info(lang)
        else:
            release_info = fetch_latest_release_info(GITHUB_USERNAME, repo_name, lang)
            release_info["release_status"] = release_status_label(
                lang,
                release_info["has_release"],
                release_info["is_prerelease"],
            )
        updated_dt = parse_iso_datetime(repo.get("pushed_at"))

        action_buttons = [{"text": f"🔗 {t(lang, 'open_github')}", "url": repo.get("html_url", "")}]
        if release_info["download_url"]:
            action_buttons.append(
                {
                    "text": f"⬇️ {t(lang, 'download_latest_release')}",
                    "url": release_info["download_url"],
                }
            )
        action_buttons.extend(app_custom_links(repo, lang))

        deduped_buttons: list[dict] = []
        seen_urls: set[str] = set()
        for button in action_buttons:
            url = button.get("url", "")
            if not isinstance(url, str) or not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            deduped_buttons.append(button)

        result.append(
            {
                "name": app_display_name(repo),
                "repo_name": repo.get("name", "-"),
                "description": app_description(repo, lang),
                "url": repo.get("html_url", ""),
                "category": app_category(repo),
                "updated": format_datetime_for_lang(updated_dt, lang),
                "status_badge": app_status_badge(updated_dt, lang),
                "featured": app_featured(repo),
                "release_version": release_info["version"],
                "release_download_url": release_info["download_url"],
                "release_published": release_info["published_at"],
                "release_is_prerelease": release_info["is_prerelease"],
                "has_release": release_info["has_release"],
                "release_status": release_info["release_status"],
                "emoji": app_emoji(repo),
                "action_buttons": deduped_buttons,
            }
        )
    return result


def load_snapshot_projects() -> list[dict]:
    if not PROJECTS_SNAPSHOT_PATH.exists():
        raise SnapshotLoadError(f"Snapshot file missing: {PROJECTS_SNAPSHOT_PATH}")

    try:
        payload = json.loads(PROJECTS_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as err:
        raise SnapshotLoadError("Could not read snapshot payload") from err

    projects = payload.get("projects")
    if not isinstance(projects, list):
        raise SnapshotLoadError("Snapshot payload missing 'projects' list")

    return [project for project in projects if isinstance(project, dict)]


def build_apps_state_from_snapshot(snapshot_projects: list[dict], lang: str) -> list[dict]:
    result: list[dict] = []
    for snapshot_project in snapshot_projects:
        repo_name = snapshot_project.get("name", "")
        repo = {
            "name": repo_name,
            "html_url": snapshot_project.get("html_url", ""),
            "pushed_at": snapshot_project.get("pushed_at"),
        }

        if snapshot_project.get("release_mode") == "direct_publish":
            release_info = direct_publish_release_info(lang)
        else:
            release_info = {
                "version": snapshot_project.get("release_version") or t(lang, "no_release"),
                "download_url": snapshot_project.get("release_download_url"),
                "published_at": snapshot_project.get("release_published_at") or "-",
                "is_prerelease": bool(snapshot_project.get("release_is_prerelease", False)),
                "has_release": bool(snapshot_project.get("release_has_release", False)),
            }
            release_info["release_status"] = release_status_label(
                lang,
                release_info["has_release"],
                release_info["is_prerelease"],
            )

        updated_dt = parse_iso_datetime(repo.get("pushed_at"))

        action_buttons = [{"text": f"🔗 {t(lang, 'open_github')}", "url": repo.get("html_url", "")}]
        if release_info["download_url"]:
            action_buttons.append(
                {
                    "text": f"⬇️ {t(lang, 'download_latest_release')}",
                    "url": release_info["download_url"],
                }
            )
        action_buttons.extend(app_custom_links(repo, lang))

        deduped_buttons: list[dict] = []
        seen_urls: set[str] = set()
        for button in action_buttons:
            url = button.get("url", "")
            if not isinstance(url, str) or not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            deduped_buttons.append(button)

        result.append(
            {
                "name": app_display_name(repo),
                "repo_name": repo.get("name", "-"),
                "description": app_description(repo, lang),
                "url": repo.get("html_url", ""),
                "category": app_category(repo),
                "updated": format_datetime_for_lang(updated_dt, lang),
                "status_badge": app_status_badge(updated_dt, lang),
                "featured": app_featured(repo),
                "release_version": release_info["version"],
                "release_download_url": release_info["download_url"],
                "release_published": release_info["published_at"],
                "release_is_prerelease": release_info["is_prerelease"],
                "has_release": release_info["has_release"],
                "release_status": release_info["release_status"],
                "emoji": app_emoji(repo),
                "action_buttons": deduped_buttons,
            }
        )
    return result


async def load_apps_for_filter(lang: str, selected_filter: str) -> list[dict]:
    snapshot_projects = load_snapshot_projects()
    all_apps = build_apps_state_from_snapshot(snapshot_projects, lang)
    return filter_apps(all_apps, selected_filter)


async def send_app_card(
    chat_target,
    lang: str,
    apps: list[dict],
    index: int,
    *,
    edit: bool = False,
) -> None:
    app = apps[index]
    message = build_app_message(lang, app, index, len(apps))
    reply_markup = apps_keyboard(
        lang,
        index,
        len(apps),
        app.get("action_buttons", []),
    )

    if edit:
        await chat_target.edit_message_text(
            message,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
    else:
        await chat_target.reply_text(
            message,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )


async def show_filter_menu(target_message, lang: str) -> None:
    await target_message.reply_text(
        t(lang, "choose_category"),
        parse_mode="HTML",
        reply_markup=apps_filter_keyboard(lang),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    logger.info("cmd_start user_id=%s lang=%s", user.id, lang)

    await update.message.reply_text(
        (
            f"✨ <b>{escape(BOT_TITLE)}</b>\n\n"
            f"{t(lang, 'welcome')}\n\n{t(lang, 'intro')}\n\n{t(lang, 'choose_language')}"
        ),
        reply_markup=language_keyboard(),
        parse_mode="HTML",
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    logger.info("cmd_language user_id=%s lang=%s", user.id, lang)
    await update.message.reply_text(
        f"{t(lang, 'language_panel')}\n\n{t(lang, 'choose_language')}",
        reply_markup=language_keyboard(),
        parse_mode="HTML",
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    user_id = update.effective_user.id
    user_languages[user_id] = "de" if query.data == "lang_de" else "en"
    save_user_languages(user_languages)
    lang = user_languages[user_id]
    logger.info("set_language user_id=%s lang=%s", user_id, lang)

    await query.edit_message_text(
        f"{t(lang, 'language_changed')}\n\n{t(lang, 'intro')}\n\n{t(lang, 'quick_actions')}",
        reply_markup=quick_actions_keyboard(lang),
        parse_mode="HTML",
    )


async def apps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    logger.info("cmd_apps user_id=%s lang=%s", user.id, lang)
    await show_filter_menu(update.message, lang)


async def apps_filter_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not query.data:
        return

    await query.answer()
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    selected_filter = query.data.removeprefix("apps_filter_")
    if selected_filter not in PROJECT_FILTERS:
        return

    logger.info("apps_filter user_id=%s filter=%s", user.id, selected_filter)

    if not query.message:
        return

    loading_msg = await query.message.reply_text(t(lang, "apps_loading"))

    try:
        apps = await load_apps_for_filter(lang, selected_filter)
    except SnapshotLoadError:
        logger.exception("Could not load project snapshot.")
        await loading_msg.edit_text(t(lang, "apps_error"))
        return

    if not apps:
        await loading_msg.edit_text(
            t(lang, "apps_empty_filtered").format(category=category_label(lang, selected_filter))
        )
        return

    context.user_data["apps"] = apps
    context.user_data["apps_index"] = 0
    context.user_data["apps_filter"] = selected_filter
    logger.info("apps_loaded user_id=%s count=%s filter=%s", user.id, len(apps), selected_filter)

    await loading_msg.delete()
    await send_app_card(query.message, lang, apps, 0, edit=False)


async def apps_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return

    await query.answer()
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    logger.info("apps_nav user_id=%s action=%s", user.id, query.data)

    if query.data == "apps_noop":
        return

    if query.data == "apps_refresh":
        selected_filter = context.user_data.get("apps_filter", "all")
        if selected_filter not in PROJECT_FILTERS:
            selected_filter = "all"

        try:
            apps = await load_apps_for_filter(lang, selected_filter)
        except SnapshotLoadError:
            logger.exception("Could not load project snapshot on refresh.")
            await query.answer(t(lang, "apps_error"), show_alert=True)
            return

        if not apps:
            await query.answer(
                t(lang, "apps_empty_filtered").format(category=category_label(lang, selected_filter)),
                show_alert=True,
            )
            return

        context.user_data["apps"] = apps
        context.user_data["apps_index"] = 0
        context.user_data["apps_filter"] = selected_filter
        await send_app_card(query, lang, apps, 0, edit=True)
        return

    apps = context.user_data.get("apps")
    index = context.user_data.get("apps_index", 0)
    if not apps:
        await query.answer(t(lang, "session_expired"), show_alert=True)
        return

    if query.data == "apps_next":
        index = (index + 1) % len(apps)
    elif query.data == "apps_prev":
        index = (index - 1) % len(apps)
    else:
        return

    context.user_data["apps_index"] = index
    await send_app_card(query, lang, apps, index, edit=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    logger.info("cmd_help user_id=%s lang=%s", user.id, lang)
    await update.message.reply_text(
        f"{t(lang, 'help')}\n\n{t(lang, 'quick_actions')}",
        parse_mode="HTML",
        reply_markup=quick_actions_keyboard(lang),
    )


async def ui_shortcuts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)

    if query.data == "ui_apps":
        if query.message:
            await show_filter_menu(query.message, lang)
        return
    if query.data == "ui_help":
        if query.message:
            await query.message.reply_text(
                f"{t(lang, 'help')}\n\n{t(lang, 'quick_actions')}",
                parse_mode="HTML",
                reply_markup=quick_actions_keyboard(lang),
            )
        return
    if query.data == "ui_language":
        if query.message:
            await query.message.reply_text(
                f"{t(lang, 'language_panel')}\n\n{t(lang, 'choose_language')}",
                reply_markup=language_keyboard(),
                parse_mode="HTML",
            )
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)


def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("apps", apps_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CallbackQueryHandler(set_language, pattern="^lang_(de|en)$"))
    application.add_handler(CallbackQueryHandler(ui_shortcuts, pattern="^ui_(apps|help|language)$"))
    application.add_handler(
        CallbackQueryHandler(
            apps_filter_select,
            pattern="^apps_filter_",
        )
    )
    application.add_handler(
        CallbackQueryHandler(apps_navigation, pattern="^apps_(prev|next|noop|refresh)$")
    )

    application.add_error_handler(error_handler)
    logger.info("Bot started. GitHub username=%s, title=%s", GITHUB_USERNAME, BOT_TITLE)
    application.run_polling()


if __name__ == "__main__":
    main()
