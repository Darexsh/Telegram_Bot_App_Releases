"""Project metadata for the Telegram showcase bot.

Update this file to describe the repositories you want to show in the bot.
Key = GitHub repository name.
"""

REPO_METADATA = {
    "example-android-app": {
        "display_name": "Example Android App",
        "emoji": "📱",
        "featured": True,
        "category": "android",
        "description": {
            "de": "Beispielbeschreibung fuer eine Android-App.",
            "en": "Example description for an Android app.",
        },
        "links": [
            {
                "label": {
                    "de": "Dokumentation",
                    "en": "Documentation",
                },
                "url": "https://github.com/your-user/example-android-app#readme",
            }
        ],
    },
    "example-hardware-project": {
        "display_name": "Example Hardware Project",
        "emoji": "🛠️",
        "featured": False,
        "category": "hardware",
        "release_strategy": "none",
        "description": {
            "de": "Beispielbeschreibung fuer ein Hardware-Projekt ohne GitHub-Releases.",
            "en": "Example description for a hardware project without GitHub releases.",
        },
        "links": [
            {
                "label": {
                    "de": "Installationsanleitung",
                    "en": "Install Guide",
                },
                "url": "https://github.com/your-user/example-hardware-project#installation",
            }
        ],
    },
}
