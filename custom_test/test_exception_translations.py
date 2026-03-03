import ast
import os
import re

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

    def extract_strings_from_mapper_file(self):
        """
        Extract all hardcoded strings from the exception handler mapper file.
        Returns a set of strings that should be marked for translation.
        """
        mapper_file_path = os.path.join(
            settings.BASE_DIR,
            "common",
            "exception_handling",
            "exception_handler_mapper.py",
        )

        with open(mapper_file_path, "r", encoding="utf-8") as file:
            content = file.read()

        # Parse the AST to find string literals in exception handlers
        tree = ast.parse(content)
        strings_in_handlers = set()

        # Look for string literals in the EXCEPTION_HANDLER_MAPPER and API_EXCEPTION_HANDLER_MAPPER
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in [
                        "EXCEPTION_HANDLER_MAPPER",
                        "API_EXCEPTION_HANDLER_MAPPER",
                    ]:
                        # Extract strings from this assignment
                        for string_node in ast.walk(node.value):
                            if isinstance(string_node, ast.Str):
                                strings_in_handlers.add(string_node.s)
                            elif isinstance(string_node, ast.Constant) and isinstance(
                                string_node.value, str
                            ):
                                strings_in_handlers.add(string_node.value)

            # Also check function definitions like get_integrity_error_parameters
            elif isinstance(node, ast.FunctionDef):
                if "error_parameters" in node.name.lower():
                    for string_node in ast.walk(node):
                        if isinstance(string_node, ast.Str):
                            strings_in_handlers.add(string_node.s)
                        elif isinstance(string_node, ast.Constant) and isinstance(
                            string_node.value, str
                        ):
                            strings_in_handlers.add(string_node.value)

        return strings_in_handlers

    def extract_marked_translation_strings(self):
        """
        Extract strings that are marked for translation using _() in the mapper file.
        """
        mapper_file_path = os.path.join(
            settings.BASE_DIR,
            "common",
            "exception_handling",
            "exception_handler_mapper.py",
        )

        with open(mapper_file_path, "r", encoding="utf-8") as file:
            content = file.read()

        # Find all _("...") patterns
        pattern = r'_\("([^"]+)"\)'
        marked_strings = set(re.findall(pattern, content))

        return marked_strings

    def get_all_handler_strings(self):
        """
        Get all strings used in exception handlers by actually calling them.
        """
        handler_strings = set()

        # Test EXCEPTION_HANDLER_MAPPER
        for exception_class, handler in EXCEPTION_HANDLER_MAPPER.items():
            try:
                if callable(handler):
                    # Create a dummy exception instance
                    if exception_class is Exception:
                        dummy_exception = Exception("test")
                    else:
                        dummy_exception = exception_class("test")

                    parameters = handler(dummy_exception)
                    handler_strings.add(parameters.response_message)
                    handler_strings.add(parameters.error_msg)

                    # Special handling for IntegrityError to test both paths
                    if exception_class.__name__ == "IntegrityError":
                        # Test duplicate key path
                        from django.db import IntegrityError

                        duplicate_error = IntegrityError(
                            "duplicate key value violates unique constraint"
                        )
                        duplicate_params = handler(duplicate_error)
                        handler_strings.add(duplicate_params.response_message)
                        handler_strings.add(duplicate_params.error_msg)

                        # Test generic integrity error path
                        generic_error = IntegrityError("some other integrity error")
                        generic_params = handler(generic_error)
                        handler_strings.add(generic_params.response_message)
                        handler_strings.add(generic_params.error_msg)
                else:
                    # Handle non-callable handlers
                    handler_strings.add(handler.response_message)
            except Exception:
                # Skip handlers that can't be instantiated
                continue

        # Test API_EXCEPTION_HANDLER_MAPPER
        for exception_class, parameters in API_EXCEPTION_HANDLER_MAPPER.items():
            handler_strings.add(parameters.response_message)

        return handler_strings

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

    def test_all_handler_strings_are_marked_for_translation(self):
        """
        NEW TEST: Ensure all strings used in exception handlers are marked for translation.
        This test will fail if an engineer adds a new exception handler without marking strings for translation.
        """
        # Get all strings actually used in handlers
        handler_strings = self.get_all_handler_strings()

        # Get strings marked for translation
        marked_strings = self.extract_marked_translation_strings()

        # Check that all handler strings are marked for translation
        unmarked_strings = handler_strings - marked_strings

        self.assertEqual(
            len(unmarked_strings),
            0,
            f"The following strings are used in exception handlers but are NOT marked for translation "
            f"with _() in exception_handler_mapper.py: {unmarked_strings}\n\n"
            f"Please add these strings to the translation section at the top of the file:\n"
            f"# Mark strings for translation\n"
            + "\n".join([f'_("{string}")' for string in unmarked_strings])
            + "\n\nThis ensures they will be picked up by makemessages and won't be marked as obsolete.",
        )

    def test_marked_strings_have_translations_in_all_languages(self):
        """
        NEW TEST: Ensure all marked translation strings have actual translations in all language files.
        This catches cases where strings are marked but not translated.
        """
        marked_strings = self.extract_marked_translation_strings()
        languages = self.get_all_languages()

        missing_translations = []

        for lang_code in languages:
            for string in marked_strings:
                if not self.check_translation_exists_in_po(string, lang_code):
                    missing_translations.append(f"'{string}' in {lang_code}")

        self.assertEqual(
            len(missing_translations),
            0,
            f"The following marked strings are missing translations: {missing_translations}\n\n"
            f"Please add translations for these strings in the respective .po files.\n"
            f"Run 'python manage.py makemessages --all' and then add translations.",
        )

    def test_no_orphaned_translation_markers(self):
        """
        NEW TEST: Ensure no strings are marked for translation but not actually used.
        This catches cases where old exception handlers are removed but translation markers remain.
        """
        handler_strings = self.get_all_handler_strings()
        marked_strings = self.extract_marked_translation_strings()

        # Find strings marked for translation but not used in handlers
        orphaned_strings = marked_strings - handler_strings

        # Filter out strings that might be used elsewhere (like common messages)
        common_messages = {
            "An error occured!",  # Used in multiple places
            "Request parameters are not valid!",  # Used in multiple places
            "Content not found!",  # Used in multiple places
            "Authentication failed!",  # Used in multiple places
            "You don't have permission for this action!",  # Used in multiple places
        }

        actual_orphaned = orphaned_strings - common_messages

        if actual_orphaned:
            self.fail(
                f"The following strings are marked for translation but not used in exception handlers: "
                f"{actual_orphaned}\n\n"
                f"Consider removing these from the translation markers section in exception_handler_mapper.py "
                f"if they are no longer needed."
            )


class ExceptionHandlerComplianceTestCase(TestCase):
    """
    Additional test class to ensure exception handler best practices.
    """

    def test_exception_handler_mapper_structure_compliance(self):
        """
        Ensure the exception handler mapper file follows the required structure.
        """
        mapper_file_path = os.path.join(
            settings.BASE_DIR,
            "common",
            "exception_handling",
            "exception_handler_mapper.py",
        )

        with open(mapper_file_path, "r", encoding="utf-8") as file:
            content = file.read()

        # Check that the file has the translation marking section
        self.assertIn(
            "# Mark strings for translation",
            content,
            "exception_handler_mapper.py must have a '# Mark strings for translation' section "
            "where all exception handler strings are marked with _()",
        )

        # Check that gettext is imported
        self.assertIn(
            "from django.utils.translation import",
            content,
            "exception_handler_mapper.py must import translation utilities",
        )

        # Check that _() is used for marking strings
        translation_markers = re.findall(r'_\("([^"]+)"\)', content)
        self.assertGreater(
            len(translation_markers),
            0,
            "exception_handler_mapper.py should have strings marked for translation using _()",
        )
