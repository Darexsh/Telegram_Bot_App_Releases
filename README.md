* * *

<div align="center">

🤖 Darexsh Telegram Bot
============================

**A bilingual Telegram portfolio bot for showcasing apps from GitHub**  
🌍📱🚀🔔

![Project Status](https://img.shields.io/badge/Status-Active-brightgreen) ![License](https://img.shields.io/badge/License-NonCommercial-blue) ![Platform](https://img.shields.io/badge/Platform-Telegram-2CA5E0) ![Language](https://img.shields.io/badge/Languages-DE%20%2F%20EN-orange)

[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-2AABEE?logo=telegram&logoColor=white)](https://t.me/darexsh_bot) [![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-yellow?logo=buy-me-a-coffee)](https://buymeacoffee.com/darexsh)  
<sub>Check out my bot in Telegram to see it in live action.<br>If you want to support more projects, you can leave a small donation for a coffee.</sub>

</div>


* * *

✨ Authors
---------

| Name | GitHub | Role | Contact | Contributions |
| --- | --- | --- | --- | --- |
| **[Darexsh by Daniel Sichler](https://github.com/Darexsh)** | [Link](https://github.com/Darexsh?tab=repositories) | Bot Development 🤖🛠️, UX/UI Text Design ✨ | 📧 [E-Mail](mailto:sichler.daniel@gmail.com) | Concept, Bot Architecture, GitHub API Integration, Release/Status Logic, Bilingual UX |

* * *

🚀 About the Project
==============

**Telegram GitHub Showcase Bot** is a bilingual (German/English) Telegram bot that presents curated app projects directly from GitHub in a clean portfolio format. It shows release information, update activity, and quick links for repository and APK releases.

* * *

✨ Features
----------

* 🌍 **Bilingual User Experience**: Full German and English support with language selection and persistent language preferences.

* 📚 **Curated App Portfolio**: Only repositories configured in `apps_data.py` are shown (no full-account listing).

* 🧭 **Polished App Cards**: Structured card layout with title, summary, update information, release details, and branding.

* 🟢🟡⚪ **Activity Status Badge**: Shows maintenance activity based on latest push date (recently updated / actively maintained / stable).

* 🟢🟡🔴 **Release Status**: Distinguishes stable releases, pre-releases, and repositories with no release yet.

* ⬇️ **APK-Only Download Button**: Download button appears only when latest release provides an `.apk` asset.

* 🔁 **Inline Navigation**: Browse apps with previous/next buttons and refresh from inside Telegram.

* 🧩 **Category Filter Menu**: Dynamic category buttons are built from your `apps_data.py` metadata.

* 🗂️ **Snapshot-Based Data Flow**: `telegram-sync` writes `/data/projects_snapshot.json`, and the bot reads from it for consistent, low-latency responses.

* ❤️ **Health Endpoint Service**: `telegram-health` exposes `/status` (port `9106`) for external monitoring/badges.

* ⚡ **No Polling for Release Notifications**: Optional GitHub Actions workflow can push release notifications to Telegram directly.

* 🛡️ **Reliability Hardening**: GitHub API caching plus retry/backoff and rate-limit handling.

* 🧾 **Reduced Log Noise**: Runtime logs are warnings/errors focused.


* * *

📥 Installation
---------------

1. **Clone from GitHub**:

    ```bash
    git clone https://github.com/Darexsh/Telegram_Bot_App_Releases.git
    ```

2. **Open bot directory**:

    ```bash
    cd Telegram_Bot_App_Releases
    ```

3. **Create env file from template**:

    ```bash
    cp .env.example .env
    ```

4. **Edit `.env` and set at least**:

- `TOKEN=...`
- `GITHUB_USERNAME=...`
- `GITHUB_TOKEN=...` (recommended)

5. **Edit `apps_data.py` and define your repositories**:

- Add/update repository keys to match your real GitHub repo names.
- Set display names, categories, descriptions, and optional links.

6. **Build and start services with Docker Compose**:

```bash
docker compose up -d --build telegram-sync telegram-bot telegram-health
```

7. **Check logs**:

```bash
docker compose logs -f telegram-sync telegram-bot telegram-health
```

Language preferences are persisted in `data/user_languages.json`.


* * *

📝 Usage
--------

1. **Create a bot via BotFather**:

- Open Telegram and chat with `@BotFather`.
- Send `/newbot` and follow the setup.
- Copy the generated token.

2. **Set `.env` values**:

```env
TOKEN=YOUR_NEW_BOT_TOKEN
GITHUB_USERNAME=YOUR_USER_NAME
GITHUB_TOKEN=YOUR_GITHUB_TOKEN
BOT_TITLE=Darexsh Projects
BOT_FOOTER=Darexsh by Daniel Sichler
BOT_IDENTIFIER=darexsh-telegram
MAX_REPOS=20
GITHUB_CACHE_TTL_SECONDS=300
GITHUB_MAX_RETRIES=2
GITHUB_RETRY_BACKOFF_SECONDS=0.8
TELEGRAM_SYNC_INTERVAL_SECONDS=86400
TELEGRAM_HEALTH_CACHE_TTL=60
```

3. **Run services (Docker Compose)**:

```bash
docker compose up -d --build telegram-sync telegram-bot telegram-health
```

4. **Verify services**:

```bash
docker compose ps
docker compose logs -f telegram-sync telegram-bot telegram-health
```

Health endpoint:

```bash
curl -s http://localhost:9106/status
```

5. **Use commands in Telegram**:

- `/start` - Start page and language selection
- `/apps` - Show app portfolio
- `/language` - Switch language
- `/help` - Show command help

6. **Manual snapshot refresh (optional)**:

```bash
docker compose up -d --force-recreate telegram-sync
docker compose logs -f telegram-sync
```

### Optional: Run without Docker

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```


* * *

🔔 GitHub Release Notifications (Optional)
------------------------------------------

If you want automatic Telegram notifications when a release is published (without periodic bot polling):

1. Copy workflow into each monitored app repository:

    * `.github/workflows/release-telegram.yml`

2. Set repository secrets in each app repository:

    * `TELEGRAM_BOT_TOKEN`

    * `TELEGRAM_CHAT_ID`

3. Trigger behavior:

    * On `release: published`, GitHub Actions sends a Telegram notification with buttons:
      * `Open on GitHub`
      * `Download latest release`


* * *

⚙️ Technical Details
--------------------

* 🐍 Built with **Python** and **python-telegram-bot**.

* 🌐 Uses **GitHub REST API** for repository and release metadata.

* 🧠 User language preferences are persisted locally (`data/user_languages.json` in Docker mode).

* ⚡ GitHub responses are cached in-memory with configurable TTL.

* 🔁 Retry/backoff logic handles transient GitHub errors and rate limiting.

* 📦 App metadata (display name, emoji, descriptions, featured flag) is maintained in `apps_data.py`.


* * *

🔐 Security Notes
-----------------

* Never commit `.env`.

* If token leaks, rotate immediately in BotFather (`/revoke` or regenerate token).

* Ensure `.gitignore` excludes runtime and secret files (`.env`, `venv/`, `__pycache__/`, `user_languages.json`, `data/`).


* * *

🔁 Token Rotation Script (Multi-Repo)
-------------------------------------

This repository includes a helper script to update the GitHub Actions secret
`TELEGRAM_BOT_TOKEN` across repositories that contain the release workflow.

Script path:

* `scripts/update_telegram_secret.sh`
* `scripts/update_telegram_secret.ps1`

Usage:

```bash
chmod +x scripts/update_telegram_secret.sh
./scripts/update_telegram_secret.sh your-github-user-or-org
```

`your-github-user-or-org` is the required GitHub owner argument (`<github-owner>`).

Or with environment variable:

```bash
NEW_TG_TOKEN='YOUR_NEW_BOT_TOKEN' ./scripts/update_telegram_secret.sh your-github-user-or-org
```

PowerShell (Windows):

```powershell
.\scripts\update_telegram_secret.ps1 your-github-user-or-org
```

PowerShell with environment variable:

```powershell
$env:NEW_TG_TOKEN='YOUR_NEW_BOT_TOKEN'
.\scripts\update_telegram_secret.ps1 your-github-user-or-org
```

Requirements:

* GitHub CLI installed (`gh`)
* Authenticated session (`gh auth login`)


* * *

📜 License
----------

This project is licensed under the **Non-Commercial Software License (MIT-style) v1.0** and was developed as an educational project. You are free to use, modify, and distribute the code for **non-commercial purposes only**, and must credit the author:

**Copyright (c) 2026 Darexsh by Daniel Sichler**

Please include the following notice with any use or distribution:

> Developed by Daniel Sichler aka Darexsh. Licensed under the Non-Commercial Software License (MIT-style) v1.0. See `LICENSE` for details.

The full license is available in the [LICENSE](LICENSE) file.

* * *

<div align="center"> <sub>Created with ❤️ by Daniel Sichler</sub> </div>
