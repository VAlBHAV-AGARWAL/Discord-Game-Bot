# Simple localization utility for the bot
import json
import os

LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locales')

class Localization:
    def __init__(self, default_lang='en'):
        self.default_lang = default_lang
        self.locales = {}
        self.load_locales()

    def load_locales(self):
        if not os.path.exists(LOCALE_DIR):
            os.makedirs(LOCALE_DIR)
        for fname in os.listdir(LOCALE_DIR):
            if fname.endswith('.json'):
                lang = fname[:-5]
                with open(os.path.join(LOCALE_DIR, fname), 'r', encoding='utf-8') as f:
                    self.locales[lang] = json.load(f)

    def get(self, key, lang=None, **kwargs):
        lang = lang or self.default_lang
        locale = self.locales.get(lang, self.locales.get(self.default_lang, {}))
        text = locale.get(key, key)
        return text.format(**kwargs)

localization = Localization()
