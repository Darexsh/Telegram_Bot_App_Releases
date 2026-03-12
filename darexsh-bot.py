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
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "Darexsh")
LANG_STORE_PATH = Path(
    os.getenv("LANG_STORE_PATH", str(Path(__file__).with_name("user_languages.json")))
)
MAX_REPOS = int(os.getenv("MAX_REPOS", "20"))
GITHUB_CACHE_TTL_SECONDS = int(os.getenv("GITHUB_CACHE_TTL_SECONDS", "300"))
GITHUB_MAX_RETRIES = int(os.getenv("GITHUB_MAX_RETRIES", "2"))
GITHUB_RETRY_BACKOFF_SECONDS = float(os.getenv("GITHUB_RETRY_BACKOFF_SECONDS", "0.8"))

if not TOKEN:
    raise ValueError("TOKEN not found. Please set TOKEN in your .env file.")

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
            "✨ <b>Willkommen bei Darexsh Projects</b>\n"
            "Ein kompakter App-Showcase direkt aus GitHub."
        ),
        "choose_language": "Bitte wähle deine Sprache:",
        "language_changed": "Sprache auf Deutsch gesetzt.",
        "intro": (
            "🚀 <b>Was du hier machen kannst</b>\n"
            "• Apps inkl. Release-Status ansehen\n"
            "• Neueste APK-Releases direkt öffnen\n"
            "• Sprache jederzeit umschalten"
        ),
        "help": (
            "🧭 <b>Hilfe & Befehle</b>\n\n"
            "<b>/start</b> - Startseite und Sprachauswahl\n"
            "<b>/apps</b> - Apps von GitHub anzeigen\n"
            "<b>/language</b> - Sprache wechseln\n"
            "<b>/help</b> - Diese Hilfe anzeigen"
        ),
        "quick_actions": "Schnellzugriff:",
        "btn_apps": "📱 Apps",
        "btn_help": "🧭 Hilfe",
        "btn_language": "🌐 Sprache",
        "language_panel": "🌐 <b>Sprache auswählen</b>",
        "apps_loading": "GitHub-Daten werden geladen...",
        "apps_empty": "Keine konfigurierten Apps gefunden.",
        "apps_error": "GitHub konnte gerade nicht erreicht werden. Bitte später erneut probieren.",
        "apps_rate_limited": "GitHub-Limit erreicht. Bitte erneut versuchen: {reset}",
        "open_github": "Auf GitHub öffnen",
        "download_latest_release": "Neueste Release herunterladen",
        "refresh": "Neu laden",
        "repo": "Repository",
        "updated": "Zuletzt geändert",
        "release_version": "Release-Version",
        "release_published": "Release veröffentlicht",
        "release_status": "Release-Status",
        "release_status_stable": "🟢 Stabil",
        "release_status_prerelease": "🟡 Pre-Release",
        "release_status_none": "🔴 Noch keine Releases",
        "no_release": "Keine Release-Version",
        "no_description": "Keine Beschreibung vorhanden.",
        "all_apps": "Alle Apps",
        "navigation_hint": "Nutze die Pfeile, um durch die Apps zu wechseln.",
        "session_expired": "Sitzung abgelaufen. Bitte /apps erneut senden.",
        "language_button_de": "Deutsch",
        "language_button_en": "English",
        "summary": "Kurzbeschreibung",
        "featured": "⭐ Featured",
        "status_recent": "🟢 Kürzlich aktualisiert",
        "status_active": "🟡 Aktiv gepflegt",
        "status_stable": "⚪ Stabil",
        "brand_footer": "Darexsh by Daniel Sichler",
    },
    "en": {
        "welcome": (
            "✨ <b>Welcome to Darexsh Projects</b>\n"
            "A compact app showcase directly from GitHub."
        ),
        "choose_language": "Please choose your language:",
        "language_changed": "Language switched to English.",
        "intro": (
            "🚀 <b>What you can do here</b>\n"
            "• Browse apps with release status\n"
            "• Open latest APK releases directly\n"
            "• Switch language anytime"
        ),
        "help": (
            "🧭 <b>Help & Commands</b>\n\n"
            "<b>/start</b> - Start page and language picker\n"
            "<b>/apps</b> - Show apps from GitHub\n"
            "<b>/language</b> - Switch language\n"
            "<b>/help</b> - Show this help"
        ),
        "quick_actions": "Quick actions:",
        "btn_apps": "📱 Apps",
        "btn_help": "🧭 Help",
        "btn_language": "🌐 Language",
        "language_panel": "🌐 <b>Select language</b>",
        "apps_loading": "Loading GitHub data...",
        "apps_empty": "No configured apps found.",
        "apps_error": "Could not reach GitHub right now. Please try again later.",
        "apps_rate_limited": "GitHub rate limit reached. Please try again: {reset}",
        "open_github": "Open on GitHub",
        "download_latest_release": "Download latest release",
        "refresh": "Refresh",
        "repo": "Repository",
        "updated": "Last updated",
        "release_version": "Release version",
        "release_published": "Release published",
        "release_status": "Release status",
        "release_status_stable": "🟢 Stable",
        "release_status_prerelease": "🟡 Pre-release",
        "release_status_none": "🔴 No releases yet",
        "no_release": "No release version",
        "no_description": "No description available.",
        "all_apps": "All apps",
        "navigation_hint": "Use arrows to switch through the apps.",
        "session_expired": "Session expired. Please send /apps again.",
        "language_button_de": "Deutsch",
        "language_button_en": "English",
        "summary": "Summary",
        "featured": "⭐ Featured",
        "status_recent": "🟢 Recently updated",
        "status_active": "🟡 Actively maintained",
        "status_stable": "⚪ Stable",
        "brand_footer": "Darexsh by Daniel Sichler",
    },
}


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


def get_user_language(user_id: int, fallback_language_code: str | None = None) -> str:
    if user_id in user_languages:
        return user_languages[user_id]
    if fallback_language_code and fallback_language_code.lower().startswith("de"):
        return "de"
    return "en"


def t(lang: str, key: str) -> str:
    return TEXTS[lang][key]


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


def apps_keyboard(
    lang: str,
    index: int,
    total: int,
    github_url: str,
    release_download_url: str | None,
) -> InlineKeyboardMarkup:
    if release_download_url:
        row1 = [
            InlineKeyboardButton(f"🔗 {t(lang, 'open_github')}", url=github_url),
            InlineKeyboardButton(f"⬇️ {t(lang, 'download_latest_release')}", url=release_download_url),
        ]
    else:
        row1 = [InlineKeyboardButton(f"🔗 {t(lang, 'open_github')}", url=github_url)]

    return InlineKeyboardMarkup(
        [
            row1,
            [
                InlineKeyboardButton("◀️", callback_data="apps_prev"),
                InlineKeyboardButton(f"{index + 1}/{total}", callback_data="apps_noop"),
                InlineKeyboardButton("▶️", callback_data="apps_next"),
            ],
            [InlineKeyboardButton(f"🔄 {t(lang, 'refresh')}", callback_data="apps_refresh")],
        ]
    )


def github_request(url: str):
    now = datetime.now(timezone.utc)
    cached = github_cache.get(url)
    if cached:
        cache_time, payload = cached
        if now - cache_time <= timedelta(seconds=GITHUB_CACHE_TTL_SECONDS):
            return payload

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "darexsh-telegram-bot",
        },
    )

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


def app_description(repo: dict, lang: str) -> str:
    repo_name = repo.get("name", "")
    metadata = REPO_METADATA.get(repo_name)
    if metadata:
        return metadata["description"][lang]
    description = repo.get("description")
    return description if description else t(lang, "no_description")


def app_display_name(repo: dict) -> str:
    repo_name = repo.get("name", "")
    metadata = REPO_METADATA.get(repo_name)
    if metadata:
        return metadata["display_name"]
    return repo_name.replace("_", " ")


def app_emoji(repo: dict) -> str:
    repo_name = repo.get("name", "")
    metadata = REPO_METADATA.get(repo_name)
    if metadata:
        return metadata["emoji"]
    return "🚀"


def app_featured(repo: dict) -> bool:
    repo_name = repo.get("name", "")
    metadata = REPO_METADATA.get(repo_name)
    if not metadata:
        return False
    return bool(metadata.get("featured", False))


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
        f"🕒 <b>{t(lang, 'updated')}:</b> {escape(app['updated'])}\n"
        f"{release_line}\n\n"
        f"📌 <b>{t(lang, 'summary')}:</b>\n"
        f"{escape(app['description'])}\n\n"
        f"━━━━━━━━━━━━\n"
        f"<b>{t(lang, 'all_apps')}</b> {index + 1}/{total}\n"
        f"{t(lang, 'navigation_hint')}\n"
        f"<i>{t(lang, 'brand_footer')}</i>"
    )


def format_rate_limit_reset(reset_at: datetime | None, lang: str) -> str:
    if not reset_at:
        return "-"
    return format_datetime_for_lang(reset_at, lang)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    logger.info("cmd_start user_id=%s lang=%s", user.id, lang)

    await update.message.reply_text(
        f"{t(lang, 'welcome')}\n\n{t(lang, 'intro')}\n\n{t(lang, 'choose_language')}",
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


def build_apps_state(repos: list[dict], lang: str) -> list[dict]:
    result: list[dict] = []
    for repo in repos:
        release_info = fetch_latest_release_info(
            GITHUB_USERNAME, repo.get("name", ""), lang
        )
        updated_dt = parse_iso_datetime(repo.get("pushed_at"))

        result.append(
            {
                "name": app_display_name(repo),
                "repo_name": repo.get("name", "-"),
                "description": app_description(repo, lang),
                "url": repo.get("html_url", ""),
                "updated": format_datetime_for_lang(updated_dt, lang),
                "status_badge": app_status_badge(updated_dt, lang),
                "featured": app_featured(repo),
                "release_version": release_info["version"],
                "release_download_url": release_info["download_url"],
                "release_published": release_info["published_at"],
                "release_is_prerelease": release_info["is_prerelease"],
                "has_release": release_info["has_release"],
                "release_status": release_status_label(
                    lang,
                    release_info["has_release"],
                    release_info["is_prerelease"],
                ),
                "emoji": app_emoji(repo),
            }
        )
    return result


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
        app["url"],
        app["release_download_url"],
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


async def apps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    lang = get_user_language(user.id, user.language_code)
    logger.info("cmd_apps user_id=%s lang=%s", user.id, lang)

    loading_msg = await update.message.reply_text(t(lang, "apps_loading"))

    try:
        repos = fetch_github_repositories(GITHUB_USERNAME, MAX_REPOS)
        apps = build_apps_state(repos, lang)
    except GitHubRateLimitError as err:
        logger.warning("apps_rate_limited user_id=%s reset_at=%s", user.id, err.reset_at)
        reset_text = format_rate_limit_reset(err.reset_at, lang)
        await loading_msg.edit_text(t(lang, "apps_rate_limited").format(reset=reset_text))
        return
    except (HTTPError, URLError, TimeoutError, ValueError):
        logger.exception("Could not fetch repositories from GitHub.")
        await loading_msg.edit_text(t(lang, "apps_error"))
        return

    if not apps:
        await loading_msg.edit_text(t(lang, "apps_empty"))
        return

    context.user_data["apps"] = apps
    context.user_data["apps_index"] = 0
    logger.info("apps_loaded user_id=%s count=%s", user.id, len(apps))

    await loading_msg.delete()
    await send_app_card(update.message, lang, apps, 0, edit=False)


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
        github_cache.clear()
        try:
            repos = fetch_github_repositories(GITHUB_USERNAME, MAX_REPOS)
            apps = build_apps_state(repos, lang)
        except GitHubRateLimitError as err:
            logger.warning("apps_refresh_rate_limited user_id=%s reset_at=%s", user.id, err.reset_at)
            reset_text = format_rate_limit_reset(err.reset_at, lang)
            await query.answer(
                t(lang, "apps_rate_limited").format(reset=reset_text),
                show_alert=True,
            )
            return
        except (HTTPError, URLError, TimeoutError, ValueError):
            logger.exception("Could not refresh repositories from GitHub.")
            await query.answer(t(lang, "apps_error"), show_alert=True)
            return

        if not apps:
            await query.answer(t(lang, "apps_empty"), show_alert=True)
            return

        context.user_data["apps"] = apps
        context.user_data["apps_index"] = 0
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
        if not query.message:
            return
        loading_msg = await query.message.reply_text(t(lang, "apps_loading"))
        try:
            repos = fetch_github_repositories(GITHUB_USERNAME, MAX_REPOS)
            apps = build_apps_state(repos, lang)
        except GitHubRateLimitError as err:
            reset_text = format_rate_limit_reset(err.reset_at, lang)
            await loading_msg.edit_text(t(lang, "apps_rate_limited").format(reset=reset_text))
            return
        except (HTTPError, URLError, TimeoutError, ValueError):
            await loading_msg.edit_text(t(lang, "apps_error"))
            return

        if not apps:
            await loading_msg.edit_text(t(lang, "apps_empty"))
            return

        context.user_data["apps"] = apps
        context.user_data["apps_index"] = 0
        await loading_msg.delete()
        await send_app_card(query.message, lang, apps, 0, edit=False)
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
        CallbackQueryHandler(apps_navigation, pattern="^apps_(prev|next|noop|refresh)$")
    )

    application.add_error_handler(error_handler)
    logger.info("Bot started. Username=%s", GITHUB_USERNAME)
    application.run_polling()


if __name__ == "__main__":
    main()
