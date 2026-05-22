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
Voice commands: recognized text -> action.
Голосовые команды: распознанный текст → действие.

Commands are stored in commands.json (triggers[] format).
Команды хранятся в commands.json (формат triggers[]).

Aliases are stored in aliases.json.
Алиасы — в aliases.json.
"""

import json
import time
import ctypes
import re
import shutil
from script_manager import find_script_by_trigger, run_script as run_named_script
from mouse_controller import get_mouse_controller
from ui_copy_handler import smart_copy as _smart_copy
from selection_overlay import selection_more as _selection_more, selection_less as _selection_less
from input_sender import send_hotkey


# Russian numeral dictionary -> numbers, including inflected forms.
# Словарь русских числительных → числа (включая падежные формы)
_WORD_TO_NUM = {
    "один": 1, "одна": 1, "одно": 1, "одного": 1, "одной": 1,
    "два": 2, "две": 2, "двух": 2, "двое": 2,
    "три": 3, "трех": 3, "трёх": 3, "трое": 3,
    "четыре": 4, "четырех": 4, "четырёх": 4, "четверо": 4,
    "пять": 5, "пяти": 5, "шесть": 6, "шести": 6,
    "семь": 7, "семи": 7, "восемь": 8, "восьми": 8,
    "девять": 9, "девяти": 9,
    "десять": 10, "десяти": 10,
    "одиннадцать": 11, "одиннадцати": 11,
    "двенадцать": 12, "двенадцати": 12,
    "тринадцать": 13, "тринадцати": 13,
    "четырнадцать": 14, "четырнадцати": 14,
    "пятнадцать": 15, "пятнадцати": 15,
    "шестнадцать": 16, "шестнадцати": 16,
    "семнадцать": 17, "семнадцати": 17,
    "восемнадцать": 18, "восемнадцати": 18,
    "девятнадцать": 19, "девятнадцати": 19,
    "двадцать": 20, "двадцати": 20,
    "тридцать": 30, "тридцати": 30,
    "сорок": 40, "сорока": 40,
    "пятьдесят": 50, "пятидесяти": 50,
    "шестьдесят": 60, "шестидесяти": 60,
    "семьдесят": 70, "семидесяти": 70,
    "восемьдесят": 80, "восьмидесяти": 80,
    "девяносто": 90, "девяноста": 90,
    "сто": 100, "ста": 100,
}

# Fuzzy aliases for common Whisper mistakes while recognizing numbers.
# Fuzzy-алиасы: частые ошибки Whisper при распознавании чисел
_FUZZY_NUM_ALIASES = {
    "адин": 1, "одын": 1,
    "садили": 1,
    "тва": 2, "дуа": 2,
    "тры": 3, "tree": 3,
    "читыре": 4, "четыри": 4, "чотыри": 4,
    "пат": 5, "пядь": 5,
    "шест": 6, "шэсть": 6, "шесь": 6,
    "сям": 7, "съем": 7,
    "восем": 8,
    "девить": 9, "дивять": 9,
    "десить": 10, "дисять": 10,
    "одинадцать": 11, "одинацать": 11,
    "двенацать": 12, "двинадцать": 12,
    "тринацать": 13, "тренадцать": 13,
    "четырнацать": 14,
    "пятнацать": 15, "питнадцать": 15,
    "шестнацать": 16,
    "семнацать": 17,
    "восемнацать": 18,
    "девятнацать": 19,
    "дватцать": 20, "двадцить": 20, "двацать": 20, "двадцат": 20,
    "тритцать": 30, "тридцить": 30, "тридцат": 30,
    "сорак": 40,
    "пидесят": 50, "пятдесят": 50, "пятьдисят": 50,
    "шистдесят": 60, "шездесят": 60,
    "симдесят": 70, "семдесят": 70,
}

# Filler words that Whisper tends to add to short commands.
# Мусорные слова — Whisper добавляет к коротким командам
_FILLER_WORDS = frozenset({
    "ну", "так", "ам", "эм", "э", "а", "ага", "угу",
    "вот", "типа", "короче", "значит", "просто",
    "пожалуйста", "давай", "ладно", "же", "ведь",
    "слушай", "смотри", "это", "ой",
})


from app_paths import COMMANDS_PATH, ALIASES_PATH, get_template_path

# === CACHES ===
# === КЭШИ ===
# _trigger_index: {"save": {"type": "hotkey", "value": "ctrl+s", "name": "hotkey_save"}, ...}
# _trigger_index: {"сохрани": {"type": "hotkey", "value": "ctrl+s", "name": "hotkey_save"}, ...}
_trigger_index = None
_trigger_index_by_lang = {}
_commands_raw_cache = None
# _aliases: {"svetka": "setka", ...}
# _aliases: {"светка": "сетка", ...}
_aliases_cache = None
_aliases_cache_by_lang = {}
_aliases_raw_cache = None
_math_mode_callback = None


def set_math_mode_callback(fn):
    """Registers a callback for toggling math mode.
    Регистрирует callback для переключения режима математики."""
    global _math_mode_callback
    _math_mode_callback = fn


def _get_active_language():
    """Returns the active voice-command language from config.
    Возвращает активный язык голосовых команд из config."""
    try:
        from config import load_config
        lang = load_config().get("language", "ru")
    except Exception:
        lang = "ru"
    return lang if lang in ("ru", "en") else "ru"


def _dedupe_keep_order(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _extract_localized_triggers(raw_value, language):
    """Supports both legacy triggers:[...] and new triggers:{ru/en/common:[...]} formats.
    Поддержка старого triggers:[...] и нового triggers:{ru/en/common:[...]}."""
    if isinstance(raw_value, list):
        return raw_value
    if not isinstance(raw_value, dict):
        return []

    result = []
    for key in ("common", language):
        values = raw_value.get(key, [])
        if isinstance(values, list):
            result.extend(values)

    if result:
        return _dedupe_keep_order(result)

    for values in raw_value.values():
        if isinstance(values, list):
            result.extend(values)
    return _dedupe_keep_order(result)


def _extract_localized_aliases(raw_value, language):
    """Supports both the legacy flat aliases.json and the new multilingual format.
    Поддержка старого flat aliases.json и нового multilingual-формата."""
    if not isinstance(raw_value, dict):
        return {}

    has_language_blocks = any(key in raw_value for key in ("common", "ru", "en"))
    if not has_language_blocks:
        return {k: v for k, v in raw_value.items() if not k.startswith("_") and isinstance(v, str)}

    result = {}
    for block_name in ("common", language):
        block = raw_value.get(block_name, {})
        if not isinstance(block, dict):
            continue
        for k, v in block.items():
            if not k.startswith("_") and isinstance(v, str):
                result[k] = v
    return result






def get_commands_path():
    return COMMANDS_PATH


def _load_aliases(language=None):
    """Loads aliases.json. Keys are normalized to lowercase.
    Загружает aliases.json. Ключи нормализуются в lowercase."""
    global _aliases_cache, _aliases_raw_cache
    if language is None:
        language = _get_active_language()

    if language in _aliases_cache_by_lang:
        _aliases_cache = _aliases_cache_by_lang[language]
        return

    if ALIASES_PATH.exists():
        try:
            if _aliases_raw_cache is None:
                with open(ALIASES_PATH, 'r', encoding='utf-8') as f:
                    _aliases_raw_cache = json.load(f)

            localized_aliases = _extract_localized_aliases(_aliases_raw_cache, language)
            aliases_map = {}
            for k, v in localized_aliases.items():
                # Normalize the key: lowercase + remove punctuation + ё->е.
                # Нормализуем ключ: lowercase + убираем пунктуацию + ё→е
                key_normalized = _normalize(k)
                if key_normalized:
                    aliases_map[key_normalized] = _normalize(v)
            _aliases_cache_by_lang[language] = aliases_map
            _aliases_cache = aliases_map
            return
        except Exception as e:
            print(f"[CMD] Ошибка загрузки aliases: {e}")
    _aliases_cache_by_lang[language] = {}
    _aliases_cache = {}


def _build_trigger_index(commands_raw, language):
    """
    Expands {name: {triggers:[], type, value}} into {trigger: {type, value, name}}.
    Разворачивает {name: {triggers:[], type, value}} → {trigger: {type, value, name}}.

    Multi-word triggers are sorted first (longest match).
    Многословные триггеры сортируются первыми (longest match).
    """
    index = {}
    for name, cmd in commands_raw.items():
        if name.startswith("_") or not isinstance(cmd, dict):
            continue
        triggers = _extract_localized_triggers(cmd.get("triggers", []), language)
        cmd_type = cmd.get("type", "paste")
        cmd_value = cmd.get("value", "")
        action = {"type": cmd_type, "value": cmd_value, "name": name}
        for trigger in triggers:
            normalized = _normalize(trigger)
            if normalized in index:
                print(f"[CMD] ⚠️ Дубль триггера '{trigger}' (команда '{name}', уже в '{index[normalized]['name']}')")
            index[normalized] = action
    return index


def load_commands(language=None):
    """Loads commands from file and builds the trigger index.
    Загружает команды из файла и строит индекс триггеров."""
    global _trigger_index, _commands_raw_cache
    if language is None:
        language = _get_active_language()

    if COMMANDS_PATH.exists():
        try:
            if _commands_raw_cache is None:
                with open(COMMANDS_PATH, 'r', encoding='utf-8') as f:
                    _commands_raw_cache = json.load(f)
            if language not in _trigger_index_by_lang:
                _trigger_index_by_lang[language] = _build_trigger_index(_commands_raw_cache, language)
            _trigger_index = _trigger_index_by_lang[language]
            _load_aliases(language)
            return _trigger_index
        except Exception as e:
            print(f"[CMD] Ошибка загрузки: {e}")
    _trigger_index = {}
    return _trigger_index


def reload_commands():
    """Reloads commands and aliases.
    Перезагрузка команд и алиасов."""
    global _trigger_index, _aliases_cache, _commands_raw_cache, _aliases_raw_cache
    _trigger_index = None
    _aliases_cache = None
    _commands_raw_cache = None
    _aliases_raw_cache = None
    _trigger_index_by_lang.clear()
    _aliases_cache_by_lang.clear()
    load_commands()
    print("[CMD] ✅ Команды перезагружены")


def get_commands_count():
    """Returns the number of unique triggers.
    Количество уникальных триггеров."""
    if _trigger_index is None:
        load_commands()
    return len(_trigger_index) if _trigger_index else 0


def _copy_template(template_name, target_path, label):
    """Copies a template file to the target path.
    Копирует файл-шаблон в целевой путь."""
    template = get_template_path(template_name)
    if template.exists():
        shutil.copy2(template, target_path)
        print(f"[CMD] Создан пример {label}: {target_path}")
    else:
        print(f"[CMD] ⚠️ Шаблон не найден: {template}")


def create_sample_commands():
    """Creates commands.json from the template on first launch.
    Создаёт commands.json из шаблона при первом запуске."""
    if COMMANDS_PATH.exists():
        return
    _copy_template("commands_template.json", COMMANDS_PATH, "команд")


def create_sample_aliases():
    """Creates aliases.json from the template on first launch.
    Создаёт aliases.json из шаблона при первом запуске."""
    if ALIASES_PATH.exists():
        return
    _copy_template("aliases_template.json", ALIASES_PATH, "алиасов")  


def _apply_aliases(text):
    """Replaces known Whisper mistakes with correct words using aliases.json.
    Заменяет известные ошибки Whisper на правильные слова через aliases.json."""
    if _aliases_cache is None:
        _load_aliases(_get_active_language())
    if not _aliases_cache:
        return text

    if text in _aliases_cache:
        replacement = _aliases_cache[text]
        print(f"[CMD] 🔄 Алиас-фраза: '{text}' → '{replacement}'")
        return replacement

    phrase_aliases = [(k, v) for k, v in _aliases_cache.items() if ' ' in k]
    phrase_aliases.sort(key=lambda item: len(item[0]), reverse=True)
    for alias, replacement in phrase_aliases:
        pattern = rf'(?<!\S){re.escape(alias)}(?!\S)'
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            print(f"[CMD] 🔄 Алиас-фраза: '{alias}' → '{replacement}'")
            text = re.sub(r'\s+', ' ', new_text).strip()

    words = text.split()
    changed = False
    result = []

    for word in words:
        if word in _aliases_cache:
            replacement = _aliases_cache[word]
            result.append(replacement)
            changed = True
            print(f"[CMD] 🔄 Алиас: '{word}' → '{replacement}'")
        else:
            result.append(word)

    return ' '.join(result) if changed else text


def _remove_fillers(text):
    """Removes filler words for better command matching.
    Убирает мусорные слова для лучшего matching команд."""
    words = text.split()
    cleaned = [w for w in words if w not in _FILLER_WORDS]
    return ' '.join(cleaned) if cleaned else text


def _parse_number_from_text(text):
    """
    Extracts a number from text.
    Извлекает число из текста.

    Supported input: digits, numerals, fuzzy aliases, and prefix matching.
    Поддержка: цифры, числительные, fuzzy-алиасы, prefix-matching.

    Returns (number, text_without_number) or (None, text).
    Возвращает (число, текст_без_числа) или (None, text).
    """
    decimal_match = re.search(r'(?:^|[^0-9])0?\s*\.\s*(\d+)', text)
    if decimal_match:
        num = int(decimal_match.group(1))
        remaining = text[:decimal_match.start()] + text[decimal_match.end():]
        remaining = re.sub(r'\s+', ' ', remaining).strip()
        if num > 0:
            return num, remaining

    match = re.search(r'\b(\d+)\b', text)
    if match:
        num = int(match.group(1))
        remaining = text[:match.start()] + text[match.end():]
        remaining = re.sub(r'\s+', ' ', remaining).strip()
        return num, remaining

    words = text.lower().split()
    for i, word in enumerate(words):
        clean_word = re.sub(r'[.,!?;:]$', '', word)
        if clean_word in _FUZZY_NUM_ALIASES:
            num = _FUZZY_NUM_ALIASES[clean_word]
            remaining = ' '.join(words[:i] + words[i+1:]).strip()
            print(f"[NUM] Fuzzy: '{clean_word}' → {num}")
            return num, remaining

    total = 0
    found_any = False
    num_indices = []

    for i, word in enumerate(words):
        clean_word = re.sub(r'[.,!?;:]$', '', word)
        if clean_word in _WORD_TO_NUM:
            val = _WORD_TO_NUM[clean_word]
            total += val
            found_any = True
            num_indices.append(i)

    if found_any and total > 0:
        remaining = ' '.join(w for i, w in enumerate(words) if i not in num_indices).strip()
        return total, remaining

    _NUM_PREFIXES = {
        "оди": 1, "одн": 1, "два": 2, "дво": 2, "две": 2,
        "три": 3, "тро": 3, "чет": 4, "пят": 5, "шес": 6,
        "сем": 7, "вос": 8, "дев": 9, "дес": 10,
    }
    for i, word in enumerate(words):
        clean = re.sub(r'[.,!?;:]$', '', word)
        if len(clean) >= 3:
            prefix = clean[:3]
            if prefix in _NUM_PREFIXES:
                num = _NUM_PREFIXES[prefix]
                remaining = ' '.join(words[:i] + words[i+1:]).strip()
                print(f"[NUM] Prefix: '{clean}' → {num}")
                return num, remaining

    return None, text


def _ensure_loaded():
    """Loads commands if they have not been loaded yet.
    Загружает команды если ещё не загружены."""
    global _trigger_index
    if _trigger_index is None:
        load_commands(_get_active_language())


def _find_command(clean):
    """
    Ищет команду по нормализованному тексту.
    Возвращает (trigger_text, action_dict) или (None, None).

    Приоритет:
    1. Точное совпадение
    2. Все слова триггера присутствуют в тексте (longest match)
    3. Fuzzy (Levenshtein ≤1, только для коротких текстов)
    """
    # 1. Точное
    if clean in _trigger_index:
        return clean, _trigger_index[clean]

    # 2. Subset match — все слова триггера есть в тексте
    best_trigger = None
    best_action = None
    best_len = -1

    text_words = set(clean.split())

    for trigger, action in _trigger_index.items():
        trigger_words = set(trigger.split())

        # Короткие триггеры (≤ 3 символа) — только точное совпадение
        if len(trigger) <= 3:
            continue

        if trigger_words.issubset(text_words):
            if len(trigger) > best_len:
                best_trigger = trigger
                best_action = action
                best_len = len(trigger)

    if best_trigger:
        return best_trigger, best_action

    # 3. Fuzzy — только для текста из 1-2 слов
    if len(clean.split()) <= 2:
        for trigger, action in _trigger_index.items():
            if len(trigger) <= 3:
                continue
            if _fuzzy_match(clean, trigger):
                return trigger, action

    return None, None



# ============================================================
#  ОБРАБОТЧИКИ КОМАНД — dispatch-таблица
# ============================================================

def _handle_paste(trigger, value, clean, text):
    return True, {"type": "paste", "value": value, "trigger": trigger}


def _handle_hotkey(trigger, value, clean, text):
    if value == "ctrl+c":
        t_copy = time.time()
        ok, method = _smart_copy(send_hotkey)
        elapsed_copy = time.time() - t_copy
        if elapsed_copy > 2.0:
            print(f"[CMD] ⚠️ smart_copy заняла {elapsed_copy:.2f}с!")
        print(f"[CMD] ⌨️ Выполнено: ctrl+c ({method})")
        return True, {"type": "hotkey", "value": f"ctrl+c ({method})", "trigger": trigger}
    send_hotkey(value)
    print(f"[CMD] ⌨️ Выполнено: {value}")
    return True, {"type": "hotkey", "value": value, "trigger": trigger}


def _handle_mouse_move(trigger, value, clean, text):
    mc = get_mouse_controller()
    step_num, _ = _parse_number_from_text(clean)
    if step_num is not None and step_num > 0:
        real_step = step_num * 10
        mc.move(value, step=real_step)
        return True, {"type": "mouse", "value": f"сдвиг {value} на {real_step}px (×10 от {step_num})", "trigger": trigger}
    mc.move(value)
    return True, {"type": "mouse", "value": f"сдвиг {value}", "trigger": trigger}


def _handle_mouse_continuous(trigger, value, clean, text):
    mc = get_mouse_controller()
    mc.start_continuous_move(value)
    return True, {"type": "mouse", "value": f"движение {value}", "trigger": trigger}


def _handle_mouse_stop(trigger, value, clean, text):
    mc = get_mouse_controller()
    stopped = mc.stop_move()
    if stopped:
        return True, {"type": "mouse", "value": "остановка", "trigger": trigger}
    print("[CMD] ⚠️ Курсор не двигался")
    return True, {"type": "none", "value": "", "trigger": trigger}


def _handle_mouse_click(trigger, value, clean, text):
    mc = get_mouse_controller()
    mc.click(value or "left")
    return True, {"type": "mouse", "value": f"клик {value}", "trigger": trigger}


def _handle_mouse_monitor(trigger, value, clean, text):
    mc = get_mouse_controller()
    mc.go_to_monitor(int(value))
    return True, {"type": "mouse", "value": f"монитор {value}", "trigger": trigger}


def _handle_mouse_scroll(trigger, value, clean, text):
    mc = get_mouse_controller()
    scroll_num, _ = _parse_number_from_text(clean)
    amount = scroll_num if scroll_num is not None and scroll_num > 0 else 3
    mc.scroll(value or "up", amount=amount)
    return True, {"type": "mouse", "value": f"scroll {value} x{amount}", "trigger": trigger}


def _handle_mouse_scroll_max(trigger, value, clean, text):
    mc = get_mouse_controller()
    mc.scroll_to_edge(value or "down")
    return True, {"type": "mouse", "value": f"scroll max {value}", "trigger": trigger}


def _handle_grid(trigger, value, clean, text):
    mc = get_mouse_controller()
    cell_num, _ = _parse_number_from_text(clean)
    if cell_num is None:
        cell_num, _ = _parse_number_from_text(text.lower())
    if cell_num is None:
        try:
            cell_num = int(value) if value else None
        except (ValueError, TypeError):
            cell_num = None
    if cell_num is not None and cell_num > 0:
        mc.grid_go(cell_num)
        return True, {"type": "grid", "value": f"ячейка {cell_num}", "trigger": trigger}
    print(f"[CMD] ⚠️ Не удалось определить номер ячейки из '{text}'")
    return True, {"type": "none", "value": "", "trigger": trigger}


def _handle_grid_zoom(trigger, value, clean, text):
    mc = get_mouse_controller()
    sub_num, _ = _parse_number_from_text(clean)
    if sub_num is None:
        try:
            sub_num = int(value)
        except (ValueError, TypeError):
            sub_num = None
    if sub_num is not None and 1 <= sub_num <= 9:
        mc.grid_zoom(sub_num)
        return True, {"type": "grid_zoom", "value": f"подячейка {sub_num}", "trigger": trigger}
    print(f"[CMD] ⚠️ Подячейка должна быть 1-9, получено '{clean}'")
    return True, {"type": "none", "value": "", "trigger": trigger}




def _handle_named_script(trigger, value, clean, text):
    """Запуск именованного скрипта по голосовому триггеру."""
    script_path = value  # value содержит путь к скрипту
    success, msg = run_named_script(script_path)
    if success:
        print(f"[CMD] 🚀 {msg}")
        return True, {"type": "script", "value": msg, "trigger": trigger}
    else:
        print(f"[CMD] ❌ {msg}")
        return True, {"type": "none", "value": msg, "trigger": trigger}


def _handle_focus_switch(trigger, value, clean, text):
    from focus_manager import switch_to_position
    slot_num, _ = _parse_number_from_text(clean)
    if slot_num is None:
        slot_num, _ = _parse_number_from_text(text.lower())
    if slot_num is None:
        try:
            slot_num = int(value) if value else None
        except (ValueError, TypeError):
            slot_num = None
    if slot_num is not None and 1 <= slot_num <= 99:
        t_start = time.time()
        success = switch_to_position(slot_num)
        elapsed = time.time() - t_start
        if elapsed > 1.0:
            print(f"[CMD] ⚠️ switch_to_position заняла {elapsed:.2f}с")
        if success:
            return True, {"type": "focus", "value": f"точка {slot_num}", "trigger": trigger}
        return True, {"type": "none", "value": "", "trigger": trigger}
    print(f"[CMD] ⚠️ Номер точки 1-9, получено '{clean}'")
    return True, {"type": "none", "value": "", "trigger": trigger}


def _handle_focus_save(trigger, value, clean, text):
    from focus_manager import save_current_position
    slot_num, _ = _parse_number_from_text(clean)
    if slot_num is None:
        slot_num, _ = _parse_number_from_text(text.lower())
    if slot_num is not None and 1 <= slot_num <= 99:
        save_current_position(slot_num)
        return True, {"type": "focus", "value": f"сохранена точка {slot_num}", "trigger": trigger}
    print(f"[CMD] ⚠️ Номер точки 1-9, получено '{clean}'")
    return True, {"type": "none", "value": "", "trigger": trigger}


def _handle_selection_more(trigger, value, clean, text):
    ok = _selection_more()
    if ok:
        return True, {"type": "selection", "value": "расширено", "trigger": trigger}
    return True, {"type": "none", "value": "", "trigger": trigger}


def _handle_selection_less(trigger, value, clean, text):
    ok = _selection_less()
    if ok:
        return True, {"type": "selection", "value": "сужено", "trigger": trigger}
    return True, {"type": "none", "value": "", "trigger": trigger}


def _handle_toggle_math_mode(trigger, value, clean, text):
    """Включает или выключает режим математики голосом."""
    if _math_mode_callback is None:
        print("[CMD] ⚠️ math_mode_callback не зарегистрирован")
        return True, {"type": "none", "value": "", "trigger": trigger}
    enable = value == "on"
    _math_mode_callback(enable)
    state = "ВКЛ" if enable else "ВЫКЛ"
    return True, {"type": "toggle_math_mode", "value": f"математика {state}", "trigger": trigger}    

_COMMAND_HANDLERS = {
    "paste": _handle_paste,
    "hotkey": _handle_hotkey,
    "mouse_move": _handle_mouse_move,
    "mouse_continuous": _handle_mouse_continuous,
    "mouse_stop": _handle_mouse_stop,
    "mouse_click": _handle_mouse_click,
    "mouse_monitor": _handle_mouse_monitor,
    "mouse_scroll": _handle_mouse_scroll,
    "mouse_scroll_max": _handle_mouse_scroll_max,
    "grid": _handle_grid,
    "grid_zoom": _handle_grid_zoom,
    "named_script": _handle_named_script,
    "focus_switch": _handle_focus_switch,
    "focus_save": _handle_focus_save,
    "selection_more": _handle_selection_more,
    "selection_less": _handle_selection_less,
    "toggle_math_mode": _handle_toggle_math_mode,
}   


def try_execute_command(text):
    """
    Проверяет: является ли текст командой.
    Возвращает (True, описание) если команда выполнена.
    Возвращает (False, None) если это обычный текст.
    """
    load_commands(_get_active_language())

    if not text:
        return False, None

    # Нормализуем текст
    clean = _normalize(text)

    # Убираем мусорные слова
    clean = _remove_fillers(clean)

    # Применяем алиасы
    clean = _apply_aliases(clean)

    # Быстрая проверка: начинается ли фраза с известного триггера?
    # Если нет — это обычный текст, не тратим время на полный поиск
    words = clean.split()
    if not words:
        return False, None

    # Длинный текст (4-5 слов): проверяем только если первое слово — триггер
    # Больше 5 слов — всегда текст
    if len(words) > 5:
        return False, None

    if len(words) > 3:
        first_word = words[0]
        has_matching_trigger = any(
            t == first_word or t.startswith(first_word + " ")
            for t in _trigger_index
        )
        if not has_matching_trigger:
            return False, None


    # === СКРИПТЫ: проверяем ДО обычных команд ===
    script = find_script_by_trigger(clean)
    if script:
        script_name = script["name"]
        script_path = script["path"]
        trigger_text = clean
        print(f"[CMD] 🎯 Скрипт: '{trigger_text}' → {script_name}")
        return _handle_named_script(trigger_text, script_path, clean, text)


    # === VOICE NAMES: голосовые имена точек фокуса ===
    from focus_manager import find_slot_by_voice_name
    voice_slot = find_slot_by_voice_name(clean)
    if voice_slot is not None:
        from focus_manager import switch_to_position
        print(f"[CMD] 🎯 Голосовое имя: '{clean}' → фокус {voice_slot}")
        t_start = time.time()
        success = switch_to_position(voice_slot)
        elapsed = time.time() - t_start
        if elapsed > 1.0:
            print(f"[CMD] ⚠️ switch_to_position заняла {elapsed:.2f}с")
        if success:
            return True, {"type": "focus", "value": f"точка {voice_slot}", "trigger": clean}
        return True, {"type": "none", "value": "", "trigger": clean}        

    # Нужен индекс триггеров для остальных проверок
    if not _trigger_index:
        return False, None

    # Специальный случай: ".XX", "0.XX" = grid XX
    text_lower = text.lower().strip()
    decimal_grid = re.search(r'^[0]?\s*\.\s*(\d+)\s*\.?$', text_lower)
    if decimal_grid:
        cell_num = int(decimal_grid.group(1))
        if cell_num > 0:
            mc = get_mouse_controller()
            mc.grid_go(cell_num)
            print(f"[CMD] 🎯 Команда: '.{cell_num}' → grid: ячейка {cell_num}")
            return True, {"type": "grid", "value": f"ячейка {cell_num}", "trigger": f".{cell_num}"}

    # Специальный случай: голое число = grid
    bare_num = re.search(r'^(\d+)\s*[,.]?\s*$', text_lower)
    if bare_num:
        cell_num = int(bare_num.group(1))
        mc = get_mouse_controller()
        grid_info = mc.get_grid_info()
        if 1 <= cell_num <= grid_info["total_cells"]:
            mc.grid_go(cell_num)
            print(f"[CMD] 🎯 Команда: '{cell_num}' → grid: ячейка {cell_num}")
            return True, {"type": "grid", "value": f"ячейка {cell_num}", "trigger": str(cell_num)}

    # Ищем команду
    trigger, action = _find_command(clean)

    if not action:
        return False, None

    cmd_type = action["type"]
    value = action.get("value", "")

    print(f"[CMD] 🎯 Команда: '{trigger}' → {cmd_type}: {value}")

    handler = _COMMAND_HANDLERS.get(cmd_type)
    if handler:
        return handler(trigger, value, clean, text)

    return False, None  


def _normalize(text):
    """Нормализация текста для сравнения."""
    text = text.lower().strip()
    text = text.replace('ё', 'е')
    # Дефисы и тире → пробел (чтобы "квн-логин" стало "квн логин")
    text = re.sub(r'[\-–—]', ' ', text)
    # Остальная пунктуация → удалить
    text = re.sub(r'[.,!?;:…\"\'«»()\[\]]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _fuzzy_match(text, trigger):
    """Нечёткое совпадение: Levenshtein с жёсткими ограничениями."""
    trigger_words = trigger.split()
    text_words = text.split()

    if len(trigger_words) >= 2:
        matched = 0
        for tw in trigger_words:
            for wd in text_words:
                if tw == wd or (len(tw) >= 4 and _levenshtein_distance(tw, wd) <= 1):
                    matched += 1
                    break
        return matched >= len(trigger_words)

    trigger_word = trigger_words[0]

    if len(trigger_word) < 4:
        return trigger_word in text_words

    if len(text_words) > 2:
        return trigger_word in text_words

    for word in text_words:
        if len(word) < 3:
            continue
        if word == trigger_word:
            return True
        if abs(len(word) - len(trigger_word)) <= 1:
            dist = _levenshtein_distance(word, trigger_word)
            if dist <= 1:
                return True

    return False


def _levenshtein_distance(s1, s2):
    """Расстояние Левенштейна между строками."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]





