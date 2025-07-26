# Exception Handler Guide

## Adding New Exception Handlers

When adding new exception handlers to `exception_handler_mapper.py`, follow these steps to ensure proper internationalization:

### 1. Add Your Exception Handler

```python
EXCEPTION_HANDLER_MAPPER = {
    # ... existing handlers ...
    YourNewException: lambda x: ExceptionHandlingParameters(
        "Your error message!",  # This string needs translation
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.YOUR_ERROR_CODE,
        "Your response message!",  # This string also needs translation
    ),
}
```

### 2. Mark Strings for Translation

**CRITICAL**: Add ALL new strings to the translation marking section at the top of the file:

```python
# Mark strings for translation - these will be picked up by makemessages
# but we'll translate them dynamically in the exception handlers
_("Your error message!")
_("Your response message!")
# ... existing strings ...
```

### 3. Add Translations

After marking strings, run:

```bash
python manage.py makemessages --all
```

Then add translations in:
- `locale/en/LC_MESSAGES/django.po` (English)
- `locale/tr/LC_MESSAGES/django.po` (Turkish)

```po
msgid "Your error message!"
msgstr "Your error message!"  # English

msgid "Your response message!"
msgstr "Your response message!"  # English
```

```po
msgid "Your error message!"
msgstr "Hata mesajınız!"  # Turkish

msgid "Your response message!"
msgstr "Yanıt mesajınız!"  # Turkish
```

### 4. Compile Messages

```bash
python manage.py compilemessages
```

## Why This Process is Important

1. **Automatic Detection**: Our tests will catch missing translation markers
2. **No Obsolete Strings**: Prevents strings from being marked as obsolete (`#~`) by `makemessages`
3. **Consistent UX**: Ensures all error messages are properly translated for users
4. **Test Coverage**: Your changes will be validated by automated tests

## Test Validation

The following tests will validate your changes:

### `test_all_handler_strings_are_marked_for_translation`
- ✅ **Passes**: All strings in handlers are marked with `_()`
- ❌ **Fails**: Tells you exactly which strings to add to the marking section

### `test_marked_strings_have_translations_in_all_languages`
- ✅ **Passes**: All marked strings have translations in all language files
- ❌ **Fails**: Lists missing translations you need to add

### `test_no_orphaned_translation_markers`
- ✅ **Passes**: No unused translation markers
- ❌ **Fails**: Suggests removing unused markers

## Common Mistakes to Avoid

❌ **DON'T** add exception handlers without marking strings:
```python
YourException: lambda x: ExceptionHandlingParameters(
    "Unmarked string!",  # Will cause test failure
    status.HTTP_400_BAD_REQUEST,
    ErrorCode.YOUR_ERROR,
    "Another unmarked string!",  # Will cause test failure
),
```

❌ **DON'T** use `gettext_lazy` directly in the mapper:
```python
YourException: lambda x: ExceptionHandlingParameters(
    _("Direct translation"),  # Breaks language detection
    status.HTTP_400_BAD_REQUEST,
    ErrorCode.YOUR_ERROR,
),
```

✅ **DO** mark strings separately and use them as plain strings:
```python
# At the top of the file:
_("Your error message!")

# In the mapper:
YourException: lambda x: ExceptionHandlingParameters(
    "Your error message!",  # Plain string, marked separately
    status.HTTP_400_BAD_REQUEST,
    ErrorCode.YOUR_ERROR,
),
```

## Example: Adding a New Database Exception

1. **Add the handler**:
```python
DatabaseConnectionError: lambda x: ExceptionHandlingParameters(
    "Database connection failed!",
    status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.DATABASE_ERROR,
    "Service temporarily unavailable!",
),
```

2. **Mark strings for translation**:
```python
# Mark strings for translation
_("Database connection failed!")
_("Service temporarily unavailable!")
```

3. **Run makemessages and add translations**
4. **Run tests to verify everything is correct**

## Questions?

If tests fail or you need help with translations, check:
1. The test error messages (they tell you exactly what to fix)
2. This guide
3. Ask the team for help with translation strings 