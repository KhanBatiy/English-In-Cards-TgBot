"""
Валидация ввода: не пусто и нужный язык (английский или русский).
"""
MAX_WORD_LENGTH = 80

# Буквы по языкам; пробелы, дефис, апостроф допускаются
LATIN = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
CYRILLIC = set(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
)


def _is_english(s: str) -> bool:
    """Все буквы в строке — латиница"""
    letters = [c for c in s if c.isalpha()]
    return len(letters) > 0 and all(c in LATIN for c in letters)


def _is_russian(s: str) -> bool:
    """Все буквы в строке — кириллица"""
    letters = [c for c in s if c.isalpha()]
    return len(letters) > 0 and all(c in CYRILLIC for c in letters)


def validate_english_word(text: str) -> tuple[bool, str | None]:
    """
    Проверяет: не пусто и введено на английском
    """
    if not text or not text.strip():
        return False, "Введите слово (не пустое)."
    s = text.strip()
    if len(s) > MAX_WORD_LENGTH:
        return False, (
            f"Слишком длинный ввод. Максимум {MAX_WORD_LENGTH} символов."
        )
    if not _is_english(s):
        return False, "Нужно слово на английском (латинскими буквами)."
    return True, None


def validate_russian_text(text: str) -> tuple[bool, str | None]:
    """
    Проверяет: не пусто и введено на русском
    """
    if not text or not text.strip():
        return False, "Введите перевод (не пустое)."
    s = text.strip()
    if len(s) > MAX_WORD_LENGTH:
        return False, (
            f"Слишком длинный ввод. Максимум {MAX_WORD_LENGTH} символов."
        )
    if not _is_russian(s):
        return False, "Нужен перевод на русском (кириллицей)."
    return True, None
