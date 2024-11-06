import os

import polib
from django.conf import settings
from django.test import TestCase
from django.utils.translation import activate

from common.exception_handling.exception_handler_mapper import (
    EXCEPTION_HANDLER_MAPPER,
    API_EXCEPTION_HANDLER_MAPPER,
)


class ExceptionTranslationTestCase(TestCase):
    def get_all_languages(self):
        """
        Retrieve all language codes from the locale directory.
        """
        locale_path = os.path.join(settings.BASE_DIR, "locale")
        return [
            d
            for d in os.listdir(locale_path)
            if os.path.isdir(os.path.join(locale_path, d))
        ]

    def check_translation_exists_in_po(self, text, lang_code):
        """
        Check if the translation exists in the .po file for the specified language.
        """
        po_file_path = os.path.join(
            settings.BASE_DIR, "locale", lang_code, "LC_MESSAGES", "django.po"
        )

        # Load the .po file
        if os.path.exists(po_file_path):
            po = polib.pofile(po_file_path)
            # Check if `text` is translated and not marked as fuzzy or obsolete
            return any(
                entry
                for entry in po
                if entry.msgid == text
                and entry.translated()
                and not entry.fuzzy
                and not entry.obsolete
            )
        return False

    def test_exception_handler_translations(self):
        """
        Test that each response_message in EXCEPTION_HANDLER_MAPPER has a translation in all languages.
        """
        for lang_code in self.get_all_languages():
            activate(lang_code)
            for exception, handler in EXCEPTION_HANDLER_MAPPER.items():
                parameters = handler(exception)
                self.assertTrue(
                    self.check_translation_exists_in_po(
                        parameters.response_message, lang_code
                    ),
                    f"Missing translation for response_message: '{parameters.response_message}' "
                    f"in EXCEPTION_HANDLER_MAPPER for language '{lang_code}'.",
                )

    def test_api_exception_handler_translations(self):
        """
        Test that each response_message in API_EXCEPTION_HANDLER_MAPPER has a translation in all languages.
        """
        for lang_code in self.get_all_languages():
            activate(lang_code)
            for exception, parameters in API_EXCEPTION_HANDLER_MAPPER.items():
                self.assertTrue(
                    self.check_translation_exists_in_po(
                        parameters.response_message, lang_code
                    ),
                    f"Missing translation for response_message: '{parameters.response_message}' "
                    f"in API_EXCEPTION_HANDLER_MAPPER for language '{lang_code}'.",
                )
