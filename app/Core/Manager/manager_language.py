from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QEvent, QLocale, QObject, QTranslator

from Config import DirPathsInstance, SettingMangerInstance, logger

LANGUAGE_SECTION = "Appearance"
LANGUAGE_OPTION = "Language"
LANGUAGE_ZH_CN = "zh_CN"
LANGUAGE_EN_US = "en_US"


class DictTranslator(QTranslator):
    def __init__(self, translations: dict[str, str]):
        super().__init__()
        self._translations = translations

    def set_translations(self, translations: dict[str, str]) -> None:
        self._translations = translations

    def translate(self, context: str, sourceText: str, disambiguation: str | None = None, n: int = -1) -> str:
        return self._translations.get(sourceText, sourceText)


class LanguageManager(QObject):
    def __init__(self):
        super().__init__()
        self._translator: DictTranslator | None = None
        self._current_language = LANGUAGE_EN_US
        self._translations_cache: dict[str, dict[str, str]] = {}

    def language_file(self, language: str) -> Path:
        return DirPathsInstance.BaseDir / "Resources" / "Language" / f"{language}.json"

    def load_translations(self, language: str) -> dict[str, str]:
        if language in self._translations_cache:
            return self._translations_cache[language]

        path = self.language_file(language)
        if not path.exists():
            logger.warning(f"Language file not found: {path}")
            self._translations_cache[language] = {}
            return {}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(f"Failed to load language file {path}: {exc}")
            self._translations_cache[language] = {}
            return {}

        if not isinstance(data, dict):
            logger.error(f"Language file is not a JSON object: {path}")
            self._translations_cache[language] = {}
            return {}

        translations = {str(key): str(value) for key, value in data.items()}
        self._translations_cache[language] = translations
        return translations

    def get_saved_language(self) -> str:
        fallback = self.system_language()
        return SettingMangerInstance.get(LANGUAGE_SECTION, LANGUAGE_OPTION, fallback) or fallback

    def save_language(self, language: str) -> None:
        SettingMangerInstance.set(LANGUAGE_SECTION, LANGUAGE_OPTION, language)

    def system_language(self) -> str:
        return LANGUAGE_ZH_CN if QLocale.system().name().startswith("zh") else LANGUAGE_EN_US

    def current_language(self) -> str:
        return self._current_language

    def apply_language(self, app, language: str | None = None) -> str:
        language = language or self.get_saved_language()
        self._current_language = language
        translations = self.load_translations(language) if language == LANGUAGE_ZH_CN else {}

        if self._translator is not None:
            app.removeTranslator(self._translator)

        self._translator = DictTranslator(translations)
        app.installTranslator(self._translator)

        self._dispatch_language_change(app)

        return self._current_language

    @staticmethod
    def _dispatch_language_change(app) -> None:
        event = QEvent(QEvent.LanguageChange)
        for widget in app.topLevelWidgets():
            QCoreApplication.sendEvent(widget, event)


language_manager = LanguageManager()
