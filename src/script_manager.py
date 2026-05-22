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
Voice-script manager.
Менеджер голосовых скриптов.

Handles CRUD operations, trigger lookup, and execution.
Выполняет CRUD-операции, поиск по триггерам и запуск.

Scripts are stored in scripts.json.
Скрипты хранятся в scripts.json.
"""

import json
import subprocess
import sys
import re
import os
import shutil
from pathlib import Path


from app_paths import get_root, SCRIPTS_JSON_PATH, SCRIPTS_DIR

SCRIPTS_PATH = SCRIPTS_JSON_PATH

# Trigger cache: {trigger_normalized: {"id": ..., "name": ..., "path": ..., "triggers": [...]}}.
# Кэш триггеров: {trigger_normalized: {"id": ..., "name": ..., "path": ..., "triggers": [...]}}.
_script_index = None
_scripts_raw = None


def _is_relative_to(path, base):
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _get_allowed_script_roots():
    return [SCRIPTS_DIR.resolve(), (get_root() / "scripts").resolve()]


def _is_allowed_script_path(path):
    resolved = Path(path).resolve()
    return any(_is_relative_to(resolved, root) for root in _get_allowed_script_roots())


def _prepare_script_path(path):
    ensure_scripts_dir()
    src_path = Path(path).expanduser()
    if not src_path.is_absolute():
        src_path = (get_root() / src_path).resolve()
    else:
        src_path = src_path.resolve()

    if not src_path.exists():
        return None, f"Файл не найден: {src_path}"

    if _is_allowed_script_path(src_path):
        return src_path, None

    target = (SCRIPTS_DIR / src_path.name).resolve()
    counter = 1
    while target.exists():
        try:
            if src_path.samefile(target):
                return target, None
        except Exception:
            pass
        target = (SCRIPTS_DIR / f"{src_path.stem}_{counter}{src_path.suffix}").resolve()
        counter += 1

    try:
        shutil.copy2(src_path, target)
    except Exception as e:
        return None, f"Не удалось скопировать скрипт в {SCRIPTS_DIR}: {e}"

    print(f"[SCRIPTS] Скопирован в доверенную папку: {target.name}")
    return target, None


def _normalize(text):
    """Normalizes text for matching, similar to command_executor.
    Нормализует текст для сравнения, по аналогии с command_executor."""
    text = text.lower().strip()
    text = text.replace('ё', 'е')
    text = re.sub(r'[.,!?;:…\-–—\"\'«»()\[\]]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def ensure_scripts_dir():
    """Creates the scripts/ directory if it does not exist.
    Создаёт папку scripts/, если её ещё нет."""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def load_scripts():
    """Loads scripts from disk and rebuilds the trigger index.
    Загружает скрипты с диска и перестраивает индекс триггеров."""
    global _script_index, _scripts_raw
    _script_index = {}
    _scripts_raw = {}

    if not SCRIPTS_PATH.exists():
        _save_scripts_raw({})
        return _script_index

    try:
        with open(SCRIPTS_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception as e:
        print(f"[SCRIPTS] Ошибка загрузки: {e}")
        return _script_index

    _scripts_raw = {k: v for k, v in raw.items()
                    if not k.startswith("_") and isinstance(v, dict)}

    for script_id, script in _scripts_raw.items():
        if not script.get("enabled", True):
            continue
        triggers = script.get("triggers", [])
        for trigger in triggers:
            norm = _normalize(trigger)
            if norm:
                _script_index[norm] = {
                    "id": script_id,
                    "name": script.get("name", script_id),
                    "path": script.get("path", ""),
                    "triggers": triggers,
                }

    print(f"[SCRIPTS] Загружено: {len(_scripts_raw)} скриптов, {len(_script_index)} триггеров")
    return _script_index


def reload_scripts():
    """Reloads scripts from disk.
    Перезагружает скрипты с диска."""
    global _script_index, _scripts_raw
    _script_index = None
    _scripts_raw = None
    load_scripts()
    print("[SCRIPTS] ✅ Скрипты перезагружены")


def _ensure_loaded():
    if _script_index is None:
        load_scripts()


def _save_scripts_raw(data):
    """Persists the raw scripts dictionary to disk.
    Сохраняет сырой словарь скриптов на диск."""
    global _scripts_raw
    to_save = {
        "_comment": "Голосовые скрипты: triggers[] → запуск файла",
        "_comment2": "Управление: трей → Скрипты → Управление скриптами",
    }
    to_save.update(data)
    try:
        with open(SCRIPTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[SCRIPTS] Ошибка сохранения: {e}")


def get_all_scripts():
    """Returns all scripts without metadata comments.
    Возвращает все скрипты без служебных комментариев."""
    _ensure_loaded()
    return dict(_scripts_raw) if _scripts_raw else {}


def get_scripts_count():
    """Returns the number of stored scripts.
    Возвращает количество сохранённых скриптов."""
    _ensure_loaded()
    return len(_scripts_raw) if _scripts_raw else 0


def get_scripts_dir():
    """Returns the scripts directory path.
    Возвращает путь к папке со скриптами."""
    return SCRIPTS_DIR


def add_script(script_id, name, path, triggers, enabled=True):
    """Adds a new script or updates an existing one.
    Добавляет новый скрипт или обновляет существующий."""
    _ensure_loaded()
    prepared_path, error = _prepare_script_path(path)
    if error:
        raise ValueError(error)

    stored_path = str(prepared_path)
    builtin_dir = (get_root() / "scripts").resolve()
    if _is_relative_to(prepared_path, builtin_dir):
        stored_path = str(prepared_path.relative_to(get_root().resolve()))

    _scripts_raw[script_id] = {
        "name": name,
        "path": stored_path,
        "triggers": triggers,
        "enabled": enabled,
    }
    _save_scripts_raw(_scripts_raw)
    reload_scripts()
    print(f"[SCRIPTS] ✅ Добавлен: '{name}' ({len(triggers)} триггеров)")


def delete_script(script_id):
    """Deletes a script entry.
    Удаляет запись о скрипте."""
    _ensure_loaded()
    if script_id in _scripts_raw:
        name = _scripts_raw[script_id].get("name", script_id)
        del _scripts_raw[script_id]
        _save_scripts_raw(_scripts_raw)
        reload_scripts()
        print(f"[SCRIPTS] 🗑️ Удалён: '{name}'")
        return True
    return False


def toggle_script(script_id, enabled):
    """Enables or disables a script.
    Включает или выключает скрипт."""
    _ensure_loaded()
    if script_id in _scripts_raw:
        _scripts_raw[script_id]["enabled"] = enabled
        _save_scripts_raw(_scripts_raw)
        reload_scripts()


def find_script_by_trigger(text):
    """
    Finds a script by normalized text.
    Ищет скрипт по нормализованному тексту.

    Возвращает dict {id, name, path, triggers} или None.
    Возвращает dict {id, name, path, triggers} или None.

    Priority:
    1. Exact trigger match
    2. All trigger words are present in the text (longest match)

    Приоритет:
    1. Точное совпадение триггера
    2. Все слова триггера есть в тексте (longest match)
    """
    _ensure_loaded()
    if not _script_index:
        return None

    clean = _normalize(text)
    if not clean:
        return None

    # First try an exact trigger match.
    # Сначала пробуем точное совпадение триггера.
    if clean in _script_index:
        return _script_index[clean]

    # Then fall back to subset matching against all trigger words.
    # Затем используем совпадение по подмножеству слов триггера.
    text_words = set(clean.split())
    best = None
    best_len = -1

    for trigger, script_info in _script_index.items():
        trigger_words = set(trigger.split())
        if len(trigger) <= 3:
            continue
        if trigger_words.issubset(text_words):
            if len(trigger) > best_len:
                best = script_info
                best_len = len(trigger)

    return best


def run_script(script_path):
    """
    Runs a script. Supported types: .py, .bat, .cmd, .ps1, .exe, .sh.
    Waits up to 30 seconds in a background thread and logs the output.
    Returns (success, output_or_error).

    Запускает скрипт. Поддержка: .py, .bat, .cmd, .ps1, .exe, .sh.
    Ждёт завершения до 30 секунд в фоновом потоке и логирует вывод.
    Возвращает (success, output_or_error).
    """
    import threading

    path = Path(script_path)

    # Resolve relative paths from the project root for consistency.
    # Относительные пути резолвим от корня проекта для единообразия.
    if not path.is_absolute():
        path = get_root() / path

    if not path.exists():
        msg = f"Файл не найден: {path}"
        print(f"[SCRIPTS] ❌ {msg}")
        return False, msg

    if not _is_allowed_script_path(path):
        msg = f"Запуск вне доверенных папок запрещён: {path}"
        print(f"[SCRIPTS] ❌ {msg}")
        return False, msg

    ext = path.suffix.lower()

    try:
        if ext == '.py':
            if getattr(sys, 'frozen', False):
                # Frozen builds route Python scripts back through the packaged executable.
                # В frozen-сборке Python-скрипты запускаются через встроенный режим exe.
                cmd = [sys.executable, "--run-script", str(path)]
            else:
                # Development mode uses the active Python interpreter directly.
                # В режиме разработки используем текущий интерпретатор Python напрямую.
                cmd = [sys.executable, str(path)]
        elif ext in ('.bat', '.cmd'):
            cmd = ['cmd', '/c', str(path)]
        elif ext == '.ps1':
            cmd = ['powershell', '-NoProfile', '-NonInteractive', '-File', str(path)]
        elif ext == '.exe':
            cmd = [str(path)]
        elif ext == '.sh':
            cmd = ['bash', str(path)]
        else:
            msg = f"Неподдерживаемый тип скрипта: {ext or '<без расширения>'}"
            print(f"[SCRIPTS] ❌ {msg}")
            return False, msg

        print(f"[SCRIPTS] 🚀 Запуск: {path.name}")
        print(f"[SCRIPTS]    Команда: {' '.join(cmd)}")
        print(f"[SCRIPTS]    Рабочая папка: {path.parent}")

        def _run_and_log():
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    cwd=str(path.parent),
                    timeout=30,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )

                if result.stdout and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        print(f"[SCRIPTS]    📤 {line}")

                if result.stderr and result.stderr.strip():
                    for line in result.stderr.strip().split('\n'):
                        print(f"[SCRIPTS]    ⚠️ {line}")

                if result.returncode == 0:
                    print(f"[SCRIPTS] ✅ Завершён: {path.name} (код: 0)")
                else:
                    print(f"[SCRIPTS] ⚠️ Завершён: {path.name} (код: {result.returncode})")

            except subprocess.TimeoutExpired:
                print(f"[SCRIPTS] ⏰ Таймаут 30с: {path.name} — процесс продолжает работать")
            except Exception as e:
                print(f"[SCRIPTS] ❌ Ошибка выполнения: {e}")

        # Run asynchronously so recognition stays responsive.
        # Запускаем асинхронно, чтобы не блокировать распознавание.
        threading.Thread(target=_run_and_log, daemon=True, name=f"script-{path.stem}").start()

        return True, f"Запущен: {path.name}"

    except Exception as e:
        msg = f"Ошибка запуска: {e}"
        print(f"[SCRIPTS] ❌ {msg}")
        return False, msg


def generate_script_id(name):
    """Generates a script id from a display name.
    Генерирует идентификатор скрипта из его имени."""
    clean = re.sub(r'[^a-zA-Zа-яА-Я0-9\s]', '', name)
    clean = re.sub(r'\s+', '_', clean).strip('_').lower()
    if not clean:
        clean = "script"
    # Transliteration keeps the generated id ASCII-safe.
    # Транслитерация делает сгенерированный идентификатор безопасным для ASCII.
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l',
        'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's',
        'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
        'ю': 'yu', 'я': 'ya', 'ё': 'yo',
    }
    result = ''
    for ch in clean:
        result += translit.get(ch, ch)
    # Ensure uniqueness among existing script ids.
    # Проверяем уникальность среди уже существующих идентификаторов.
    _ensure_loaded()
    base = result
    counter = 1
    while result in _scripts_raw:
        result = f"{base}_{counter}"
        counter += 1
    return result
