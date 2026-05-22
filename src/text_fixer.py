# Copyright (C) 2026 Boris Shkylnikov
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Vox Bee.
#
# Vox Bee is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# Vox Bee is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Vox Bee. If not, see <https://www.gnu.org/licenses/>.

"""
Fixes and cleans recognized text.
Исправление и очистка распознанного текста.

Each stage can be enabled or disabled through config.
Каждый этап можно включить/выключить через config.
"""

import re
import json
import sys
from pathlib import Path


from app_paths import USER_DICT_PATH as _USER_DICT_PATH


# === Common Whisper mistakes dictionary ===
# === Словарь частых ошибок Whisper ===

WHISPER_FIXES = {
    # Technical terms.
    # Технические термины.
    "питон": "Python",
    "пайтон": "Python",
    "пайфон": "Python",
    "джава скрипт": "JavaScript",
    "джаваскрипт": "JavaScript",
    "жава скрипт": "JavaScript",
    "ява скрипт": "JavaScript",
    "реакт": "React",
    "риакт": "React",
    "нод жс": "Node.js",
    "ноджс": "Node.js",
    "нод джей эс": "Node.js",
    "гит": "Git",
    "гитхаб": "GitHub",
    "гит хаб": "GitHub",
    "линукс": "Linux",
    "линакс": "Linux",
    "убунту": "Ubuntu",
    "убунта": "Ubuntu",
    "виндовс": "Windows",
    "виндоус": "Windows",
    "виндоуз": "Windows",
    "докер": "Docker",
    "докир": "Docker",
    "кубернетис": "Kubernetes",
    "кубернетес": "Kubernetes",
    "постгрес": "PostgreSQL",
    "постгре": "PostgreSQL",
    "монго": "MongoDB",
    "монгодб": "MongoDB",
    "редис": "Redis",
    "рэдис": "Redis",
    "апи": "API",
    "а пи ай": "API",
    "эй пи ай": "API",
    "рест": "REST",
    "рест апи": "REST API",
    "джейсон": "JSON",
    "джисон": "JSON",
    "джсон": "JSON",
    "эйчтмл": "HTML",
    "хтмл": "HTML",
    "цсс": "CSS",
    "си эс эс": "CSS",
    "эс кью эль": "SQL",
    "скл": "SQL",
    "скуэль": "SQL",
    "вс код": "VS Code",
    "вискод": "VS Code",
    "виэс код": "VS Code",
    "юнити": "Unity",
    "анриал": "Unreal",
    "анреал": "Unreal",
    "тайп скрипт": "TypeScript",
    "тайпскрипт": "TypeScript",
    "фласк": "Flask",
    "джанго": "Django",
    "фастапи": "FastAPI",
    "фаст апи": "FastAPI",
    "нампай": "NumPy",
    "нумпай": "NumPy",
    "пандас": "Pandas",
    "тензорфлоу": "TensorFlow",
    "тензор флоу": "TensorFlow",
    "пайторч": "PyTorch",
    "пай торч": "PyTorch",

    # Abbreviations.
    # Аббревиатуры.
    "гпу": "GPU",
    "цпу": "CPU",
    "г п у": "GPU",
    "ц п у": "CPU",
    "цэпэу": "CPU",
    "джипиу": "GPU",
    "рам": "RAM",
    "ссд": "SSD",
    "эс эс ди": "SSD",
    "ай пи": "IP",
    "урл": "URL",
    "юрл": "URL",
    "ю р л": "URL",
    "юсб": "USB",
    "ю эс би": "USB",
    "вай фай": "Wi-Fi",
    "вайфай": "Wi-Fi",
    "блютус": "Bluetooth",
    "блютуз": "Bluetooth",

    # Common distortions.
    # Частые искажения.
    "щас": "сейчас",
    "ща": "сейчас",
    "чё": "что",
    "чо": "что",
    "грит": "говорит",
    "нету": "нет",
    "тыща": "тысяча",
    "тыщ": "тысяч",
    "ваще": "вообще",
    "вобщем": "в общем",
    "вообщем": "в общем",
    "короч": "короче",
    # AI products and services.
    # AI-продукты и сервисы.
    "вискер": "Whisper",
    "виспер": "Whisper",
    "уиспер": "Whisper",
    "клод": "Claude",
    "клауд": "Claude",
    "чат гпт": "ChatGPT",
    "чатгпт": "ChatGPT",
    "чат жпт": "ChatGPT",
    "опен аи": "OpenAI",
    "опенаи": "OpenAI",

    # Additional common terms.
    # Дополнительные частые термины.
    "телеграм": "Telegram",
    "телеграмм": "Telegram",
    "дискорд": "Discord",
    "дискорт": "Discord",
    "слак": "Slack",
    "гугл": "Google",
    "гугол": "Google",
    "яндекс": "Яндекс",
}

HALLUCINATIONS_EXACT = [
    "www.",
    "[BLANK_AUDIO]",
]

# Regex patterns for hallucinations catch variants with spaces and periods.
# Regex-паттерны галлюцинаций — ловят вариации с пробелами/точками
HALLUCINATION_PATTERNS = [
    re.compile(r'[АA]\.?\s*Семкин', re.IGNORECASE),
    re.compile(r'Корректор\s+[АA]\.?\s*Егорова', re.IGNORECASE),
    re.compile(r'Редактор\s+субтитров', re.IGNORECASE),
    re.compile(r'[Сс]убтитры\s+(сделал|делал|подготовил|добавил|создал|создавал)\w*', re.IGNORECASE),
    re.compile(r'Подписывайтесь\s+на\s+канал[.!]?', re.IGNORECASE),
    re.compile(r'[♪♫]+'),
    re.compile(r'\.{3,}'),
    re.compile(r'DimaTorz\w*', re.IGNORECASE),
]

_NUMERIC_DICTATION_WORDS = {
    "ноль", "нуль",
    "один", "одна", "одно",
    "два", "две",
    "три", "четыре", "пять",
    "шесть", "семь", "восемь", "девять",
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
    "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто",
    "сто", "двести", "триста", "четыреста", "пятьсот",
    "шестьсот", "семьсот", "восемьсот", "девятьсот",
    "тысяча", "тысячи", "тысяч", "тысячу",
    "миллион", "миллиона", "миллионов",
    "миллиард", "миллиарда", "миллиардов",
}

_MATH_SYMBOL_DICTATION_WORDS = {
    "собака",
    "решетка", "решётка", "хеш",
    "доллар",
    "амперсанд",
    "звездочка", "звёздочка",
    "подчеркивание", "подчёркивание",
    "дефис", "тире",
    "плюсик",
    "точка", "запятая", "двоеточие",
    "скобка", "скобку", "скобки", "скобу",
    "открыть", "закрыть",
    "левая", "правая",
    "квадратная", "фигурная",
    "слэш", "бэкслэш",
    "восклицательный", "вопросительный",
    "знак",
    "апостроф", "кавычка", "кавычки",
    "обратная", "тильда",
    "пробел",
}

_MATH_DICTATION_WORDS = _NUMERIC_DICTATION_WORDS | _MATH_SYMBOL_DICTATION_WORDS
_MATH_OPERATOR_DICTATION_WORDS = {
    "плюс", "минус",
    "умножить", "умножение",
    "разделить", "делить", "деление",
    "равно", "равняется",
    "больше", "меньше",
    "процент", "процентов",
    "корень",
}
_MATH_DICTATION_WORDS |= _MATH_OPERATOR_DICTATION_WORDS
_MATH_CASE_DICTATION_WORDS = {
    "большая", "заглавная", "прописная", "большой", "заглавный", "прописной",
    "маленькая", "строчная", "маленький", "строчной",
}
_MATH_DICTATION_WORDS |= _MATH_CASE_DICTATION_WORDS

# === User dictionary ===
# === Пользовательский словарь ===

_user_dict_cache = None
_full_dict_cache = None


def get_user_dict_path():
    return _USER_DICT_PATH


def load_user_dictionary():
    """Loads the user dictionary.
    Загружает пользовательский словарь."""
    dict_path = get_user_dict_path()
    if dict_path.exists():
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # Ignore metadata keys used only for comments or hints inside the JSON file.
            # Игнорируем служебные ключи, которые используются только как комментарии и подсказки внутри JSON.
            user_dict = {k: v for k, v in raw.items()
                         if not k.startswith("_") and v}
            print(f"[FIX] Словарь пользователя: {len(user_dict)} слов ({dict_path.name})")
            return user_dict
        except Exception as e:
            print(f"[FIX] Ошибка словаря: {e}")
    return {}


def create_sample_dictionary():
    """Creates a sample dictionary if it does not exist.
    Создаёт пример словаря если его нет."""
    dict_path = get_user_dict_path()
    if dict_path.exists():
        return

    sample = {
        "_comment": "Ваш словарь замен: 'как whisper слышит' → 'как надо написать'",
        "_comment2": "Нажмите 'Перезагрузить словарь' в трее после изменений",
        "_comment3": "Ключи с _ в начале игнорируются",
        "иван иванович": "Иван Иванович",
        "гугл": "Google",
        "телеграм": "Telegram",
        "ватсап": "WhatsApp",
        "вотсап": "WhatsApp",
    }

    try:
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(sample, f, indent=2, ensure_ascii=False)
        print(f"[FIX] Создан пример словаря: {dict_path}")
    except Exception:
        pass


def reload_dictionary():
    """Reloads the dictionary from the tray.
    Перезагружает словарь (вызывается из трея)."""
    global _user_dict_cache, _full_dict_cache
    _user_dict_cache = None
    _full_dict_cache = None
    # Force a fresh load so tray reload picks up on-disk edits immediately.
    # Принудительно загружаем словарь заново, чтобы reload из трея сразу видел изменения на диске.
    _get_full_dictionary()
    print("[FIX] ✅ Словарь перезагружен")


def get_user_dict_word_count():
    """Returns the number of words in the user dictionary.
    Количество слов в пользовательском словаре."""
    d = load_user_dictionary()
    return len(d)


def _get_full_dictionary():
    """Combines the built-in and user dictionaries.
    Объединяет встроенный и пользовательский словари."""
    global _user_dict_cache, _full_dict_cache
    if _full_dict_cache is None:
        _full_dict_cache = {}
        _full_dict_cache.update(WHISPER_FIXES)
        _user_dict_cache = load_user_dictionary()
        _full_dict_cache.update(_user_dict_cache)  # User entries override the built-in dictionary. / Пользовательские записи перекрывают встроенный словарь.
    return _full_dict_cache


# === Main function ===
# === Основная функция ===

def fix_text(text, settings=None, verbose=True):
    """
    Full text processing.
    Полная обработка текста.

    settings is a dict with the following keys:
    settings — dict с ключами:
        text_fix_enabled        bool  — global on/off
        text_fix_enabled        bool  — глобальный вкл/выкл
        text_fix_hallucinations bool  — remove hallucinations
        text_fix_hallucinations bool  — удалять галлюцинации
        text_fix_dictionary     bool  — built-in dictionary
        text_fix_dictionary     bool  — встроенный словарь
        text_fix_punctuation    bool  — punctuation
        text_fix_punctuation    bool  — пунктуация
        text_fix_repetitions    bool  — repetitions
        text_fix_repetitions    bool  — повторы
        text_fix_user_dict      bool  — user dictionary
        text_fix_user_dict      bool  — пользовательский словарь
        preserve_numeric_repetitions bool — do not collapse numeric dictation
        preserve_numeric_repetitions bool — не схлопывать числовую диктовку
        preserve_math_symbol_repetitions bool — do not collapse repeated math symbols
        preserve_math_symbol_repetitions bool — не схлопывать повторы названий мат-символов

    If settings=None, everything is enabled.
    Если settings=None — всё включено.
    """
    if not text or not text.strip():
        return ""

    # Default settings treat missing keys as enabled.
    # По умолчанию отсутствие ключей трактуем как включённые этапы.
    if settings is None:
        settings = {}

    enabled = settings.get("text_fix_enabled", True)
    if not enabled:
        if verbose:
            print("[FIX] ⏭ Исправление выключено")
        return text.strip()

    do_hallucinations = settings.get("text_fix_hallucinations", True)
    do_dictionary = settings.get("text_fix_dictionary", True)
    do_punctuation = settings.get("text_fix_punctuation", True)
    do_repetitions = settings.get("text_fix_repetitions", True)
    do_user_dict = settings.get("text_fix_user_dict", True)
    preserve_numeric_repetitions = settings.get("preserve_numeric_repetitions", False)
    preserve_math_symbol_repetitions = settings.get("preserve_math_symbol_repetitions", False)

    original = text
    fixes_applied = []

    # 1. Hallucinations.
    # 1. Галлюцинации.
    if do_hallucinations:
        text_before = text
        text = _remove_hallucinations(text)
        if text != text_before:
            fixes_applied.append("галлюцинации")

    # 2. Basic cleanup (always).
    # 2. Базовая очистка (всегда).
    text = _basic_cleanup(text)

    # 3. Built-in dictionary.
    # 3. Встроенный словарь.
    if do_dictionary:
        text_before = text
        text, word_fixes = _apply_builtin_dictionary(text)
        if word_fixes:
            fixes_applied.extend(word_fixes)

    # 4. User dictionary.
    # 4. Пользовательский словарь.
    if do_user_dict:
        text_before = text
        text, user_fixes = _apply_user_dictionary(text)
        if user_fixes:
            fixes_applied.extend(user_fixes)

    # 5. Repetitions.
    # 5. Повторы.
    if do_repetitions:
        text_before = text
        text = _remove_repetitions(
            text,
            preserve_numeric_repetitions=preserve_numeric_repetitions,
            preserve_math_symbol_repetitions=preserve_math_symbol_repetitions,
        )
        if text != text_before:
            fixes_applied.append("повторы")

    # 6. Punctuation.
    # 6. Пунктуация.
    if do_punctuation:
        text_before = text
        text = _fix_punctuation(text)
        if text != text_before:
            fixes_applied.append("пунктуация")

    # 7. Final cleanup (always).
    # 7. Финальная очистка (всегда).
    text = _final_cleanup(text)

    # Verbose logging summarizes which stages actually changed the text.
    # Подробный лог показывает, какие этапы действительно изменили текст.
    if verbose and fixes_applied and text != original.strip():
        fixes_str = ", ".join(fixes_applied[:6])
        if len(fixes_applied) > 6:
            fixes_str += f" (+{len(fixes_applied) - 6})"
        print(f"[FIX] Исправления: {fixes_str}")
        print(f"[FIX] Было:  '{original.strip()}'")
        print(f"[FIX] Стало: '{text}'")
    elif verbose and not fixes_applied:
        print(f"[FIX] Без изменений")

    return text


# === Stages ===
# === Этапы ===

def _remove_hallucinations(text):
    # 1. Exact matches.
    # 1. Точные совпадения.
    for h in HALLUCINATIONS_EXACT:
        text = text.replace(h, "").strip()

    # 2. Regex patterns.
    # 2. Regex-паттерны.
    for pat in HALLUCINATION_PATTERNS:
        text = pat.sub("", text).strip()

    # 3. If only punctuation or spaces remain, the whole input was junk.
    # 3. Если после удаления осталась только пунктуация и пробелы, значит весь ввод был мусором.
    if not re.sub(r'[\s.,!?\-–—…:;\'\"()\[\]]+', '', text):
        return ""

    return text.strip()


def _basic_cleanup(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.,!?;:»\)])', r'\1', text)
    text = re.sub(r'([.,!?;:])(\w)', r'\1 \2', text)
    text = re.sub(r'([«\(])\s+', r'\1', text)
    return text.strip()


def _apply_builtin_dictionary(text):
    """Applies the built-in dictionary.
    Применяет встроенный словарь."""
    fixes = []
    sorted_keys = sorted(WHISPER_FIXES.keys(), key=len, reverse=True)

    for wrong in sorted_keys:
        correct = WHISPER_FIXES[wrong]
        pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(correct, text)
            fixes.append(f"'{wrong}'→'{correct}'")

    return text, fixes


def _load_user_dictionary_silent():
    """Loads the dictionary without logging for cache use.
    Загружает словарь без лога (для кэша)."""
    dict_path = get_user_dict_path()
    if dict_path.exists():
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            return {k: v for k, v in raw.items()
                    if not k.startswith("_") and v}
        except Exception:
            pass
    return {}




def _apply_user_dictionary(text):
    """Applies the user dictionary.
    Применяет пользовательский словарь."""
    global _user_dict_cache
    if _user_dict_cache is None:
        _user_dict_cache = _load_user_dictionary_silent()

    if not _user_dict_cache:
        return text, []

    fixes = []
    sorted_keys = sorted(_user_dict_cache.keys(), key=len, reverse=True)

    for wrong in sorted_keys:
        correct = _user_dict_cache[wrong]
        if not correct:
            continue
        pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(correct, text)
            fixes.append(f"[user] '{wrong}'→'{correct}'")

    return text, fixes


def _remove_repetitions(
    text,
    preserve_numeric_repetitions=False,
    preserve_math_symbol_repetitions=False,
):
    """Collapses consecutive identical words into one.
    Схлопывает подряд идущие одинаковые слова до одного."""
    if not text:
        return text

    words = text.split()
    if len(words) < 2:
        return text

    def strip_punct(w):
        return re.sub(r'^[^\w]+|[^\w]+$', '', w).lower()

    def is_math_dictation_token(token):
        if not token:
            return False
        if token in _MATH_DICTATION_WORDS:
            return True
        if len(token) == 1 and token.isalpha():
            return True
        if token.isalpha() and len(set(token.lower())) == 1:
            return True
        return bool(re.fullmatch(r'\d+(?:[.,]\d+)?', token))

    def is_math_dictation_word(word):
        stripped = word.strip()
        if not stripped:
            return False
        parts = [strip_punct(part) for part in re.split(r'-+', stripped)]
        parts = [part for part in parts if part]
        if not parts:
            return False
        return all(is_math_dictation_token(part) for part in parts)

    cleaned_words = [strip_punct(word) for word in words]
    if preserve_numeric_repetitions and cleaned_words and all(word in _NUMERIC_DICTATION_WORDS for word in cleaned_words if word):
        return text.strip()
    if preserve_math_symbol_repetitions and words:
        if all(is_math_dictation_word(word) for word in words):
            return text.strip()

    result = []
    prev_clean = None
    collapsed_any = False

    for word in words:
        # Collapse hyphenated repetitions like "да-да-да-да" into a single word.
        # Схлопываем повторы через дефис вроде "да-да-да-да" в одно слово.
        if '-' in word:
            parts = word.split('-')
            clean_parts = [re.sub(r'[^\w]', '', p).lower() for p in parts if p.strip()]
            if len(clean_parts) >= 2 and len(set(clean_parts)) == 1:
                # All segments are identical, so keeping the first one is lossless.
                # Если все сегменты одинаковые, можно без потерь оставить только первый.
                word = parts[0]
                collapsed_any = True

        current_clean = strip_punct(word)

        # Skip consecutive duplicates after punctuation-insensitive normalization.
        # Пропускаем подряд идущие дубли после нормализации без учёта пунктуации.
        if current_clean and current_clean == prev_clean:
            collapsed_any = True
            continue

        result.append(word)
        prev_clean = current_clean

    if collapsed_any:
        print(f"[FIX] 🔄 Повторы схлопнуты: '{text}' → '{' '.join(result)}'")

    return ' '.join(result).strip()

def _fix_punctuation(text):
    if not text:
        return text
    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()

    def capitalize_after(match):
        return match.group(1) + ' ' + match.group(2).upper()

    text = re.sub(r'([.!?])\s+(\w)', capitalize_after, text)

    compact = re.sub(r'\s+', '', text)
    looks_like_math = bool(compact) and bool(re.fullmatch(r'[0-9+\-*/=<>^%(),.]+', compact))

    if text and text[-1] not in '.!?…':
        if not looks_like_math:
            text += '.'

    return text


def _final_cleanup(text):
    text = re.sub(r'\.{4,}', '...', text)
    text = re.sub(r'([!?])\1+', r'\1', text)
    text = re.sub(r'\.\.(?!\.)', '.', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\[\s*\]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
