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
Named focus points bound to windows.
Система именованных точек фокуса с привязкой к окнам.

Stores coordinates, window identity (class, exe, title), and relative position.
Запоминает координаты, окно (класс, exe, заголовок) и относительную позицию.

On activation it finds the window, brings it forward, recalculates the target, and clicks.
При активации находит окно, поднимает его, пересчитывает цель и кликает.

Hotkeys: Alt+Shift+1..9 save the current cursor position.
Горячие клавиши: Alt+Shift+1..9 сохраняют текущую позицию курсора.

Voice examples: "focus 1" by slot number, or a custom voice label like "google".
Голосовые примеры: «фокус 1» по номеру слота или пользовательское имя вроде «гугл».
"""

import ctypes
import ctypes.wintypes
import os
import time
import threading


# Stored focus slots: slot_number -> {...}.
# Хранилище точек фокуса: slot_number -> {...}.
_focus_slots = {}  # Valid slot range: 1..99. / Допустимый диапазон слотов: 1..99.

# Callback used to notify main.py that focus points changed.
# Callback для уведомления main.py об изменении точек фокуса.
_on_change_callback = None


def set_on_change_callback(cb):
    """Registers callback(positions_dict) for focus-position updates.
    Устанавливает callback(positions_dict), вызываемый при изменении точек."""
    global _on_change_callback
    _on_change_callback = cb


def _notify_change():
    """Notifies main.py so the updated positions can be persisted to config.
    Уведомляет main.py, чтобы обновлённые точки сохранились в конфиг."""
    if _on_change_callback:
        _on_change_callback(get_positions_for_save())


# === Window information helpers ===
# === Вспомогательные функции по окну ===

def _get_window_exe(hwnd):
    """Returns the executable name for a window handle.
    Возвращает имя exe-файла по HWND окна."""
    try:
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = ctypes.wintypes.DWORD(512)
            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, buf, ctypes.byref(size)
            )
            if ok and buf.value:
                return os.path.basename(buf.value).lower()
            return ""
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return ""


def _get_window_class(hwnd):
    """Returns the window class name for a handle.
    Возвращает имя класса окна по HWND."""
    try:
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
        return buf.value
    except Exception:
        return ""


def _get_window_title(hwnd):
    """Returns the window title for a handle.
    Возвращает заголовок окна по HWND."""
    try:
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value
    except Exception:
        return ""


def _get_window_rect(hwnd):
    """Returns (left, top, right, bottom) for the window or None.
    Возвращает (left, top, right, bottom) окна или None."""
    try:
        rect = ctypes.wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    return None


def _find_window_by_info(window_exe, window_class, window_title="", saved_hwnd=None):
    """
    Finds the best visible window candidate.
    Search priority:
    1. saved_hwnd if it is still valid and belongs to the same exe
    2. exe + class + title using exact and fuzzy matching

    Ищет подходящее видимое окно.
    Приоритет поиска:
    1. saved_hwnd, если он ещё жив и принадлежит тому же exe
    2. exe + class + title с точным и fuzzy-сопоставлением
    
    Exact title matching matters for apps with many windows like VS Code or Chrome,
    because every window shares the same exe and class.

    Для приложений с несколькими окнами, вроде VS Code или Chrome, критично
    точное совпадение title, потому что exe и class у всех окон одинаковые.
    """
    user32 = ctypes.windll.user32

    # First try the saved hwnd for a fast exact restore.
    # Сначала пробуем сохранённый hwnd для быстрого точного восстановления.
    if saved_hwnd:
        if user32.IsWindow(saved_hwnd) and user32.IsWindowVisible(saved_hwnd):
            # Verify the executable too because Windows may recycle hwnd values.
            # Дополнительно проверяем exe, потому что Windows может переиспользовать hwnd.
            if window_exe:
                current_exe = _get_window_exe(saved_hwnd)
                if current_exe == window_exe:
                    return saved_hwnd
            else:
                return saved_hwnd

    # Fall back to a scored search over exe, class, and title.
    # Если hwnd не подошёл, переходим к поиску по exe, class и title с оценкой кандидатов.
    results = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    # Normalize the full saved title once and compare against it everywhere.
    # Один раз нормализуем полный сохранённый title и сравниваем все окна с ним.
    full_title = window_title.strip().lower() if window_title else ""

    def callback(hwnd, lParam):
        if not user32.IsWindowVisible(hwnd):
            return True
        cls = _get_window_class(hwnd)
        exe = _get_window_exe(hwnd)
        title = _get_window_title(hwnd)
        title_lower = title.strip().lower()
        score = 0

        if window_exe and exe == window_exe:
            score += 2
        if window_class and cls == window_class:
            score += 1

        if full_title and title_lower:
            # Exact title match gets the highest possible score.
            # Точное совпадение полного title получает максимальный приоритет.
            if title_lower == full_title:
                score += 100
            # Containment in either direction is still a strong match.
            # Если один title содержит другой, это тоже сильное совпадение.
            elif full_title in title_lower or title_lower in full_title:
                # Longer overlap is rewarded more heavily.
                # Чем длиннее совпадение, тем больше бонус.
                match_len = min(len(full_title), len(title_lower))
                score += 10 + match_len // 5
            # Otherwise score shared meaningful words.
            # Иначе оцениваем совпадение по общим значимым словам.
            else:
                saved_words = set(full_title.split())
                current_words = set(title_lower.split())
                common = saved_words & current_words
                # Ignore short/common words that create noisy matches.
                # Исключаем короткие и общие слова, которые дают шумные совпадения.
                meaningful = {w for w in common if len(w) > 2}
                if meaningful:
                    score += len(meaningful) * 2

        if score > 0:
            results.append((score, hwnd, title))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)

    if not results:
        return None

    results.sort(key=lambda x: -x[0])

    # Log near-ties to make ambiguous window restores debuggable.
    # Логируем неоднозначность, чтобы было проще разбирать спорные восстановления окна.
    if len(results) > 1 and results[0][0] - results[1][0] < 5:
        print(f"[FOCUS] ⚠️ Неоднозначный матч для '{window_exe}':")
        for score, hwnd, title in results[:3]:
            short = title[:60] if title else "?"
            print(f"[FOCUS]   score={score} hwnd={hwnd} '{short}'")

    return results[0][1]


def _force_foreground(hwnd):
    """Brings a window to the foreground while working around Windows restrictions.
    Поднимает окно на передний план с обходом ограничений Windows."""
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    # Release stuck modifiers before changing foreground focus.
    # Перед активацией окна сбрасываем залипшие модификаторы.
    _release_all_modifiers()

    # Use AttachThreadInput instead of synthetic Alt presses to satisfy SetForegroundWindow.
    # Используем AttachThreadInput вместо эмуляции Alt, чтобы обойти ограничение SetForegroundWindow.
    current_tid = user32.GetWindowThreadProcessId(
        user32.GetForegroundWindow(), None
    )
    target_tid = user32.GetWindowThreadProcessId(hwnd, None)
    attached = False
    if current_tid != target_tid and current_tid and target_tid:
        attached = bool(user32.AttachThreadInput(current_tid, target_tid, True))

    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)

    if attached:
        user32.AttachThreadInput(current_tid, target_tid, False)



def _release_all_modifiers():
    """Force-releases Alt, Ctrl, Shift, and Win through SendInput.
    Принудительно отпускает Alt, Ctrl, Shift и Win через SendInput."""
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _fields_ = [
            ("type", ctypes.c_ulong),
            ("_input", _INPUT),
        ]

    modifiers = [
        (0x12, 0x38),  # Alt,   scan=0x38
        (0x10, 0x2A),  # Shift, scan=0x2A
        (0x11, 0x1D),  # Ctrl,  scan=0x1D
        (0x5B, 0x5B),  # Win,   scan=0x5B
    ]

    inputs = []
    for vk, scan in modifiers:
        ki = KEYBDINPUT(
            wVk=vk, wScan=scan, dwFlags=KEYEVENTF_KEYUP,
            time=0, dwExtraInfo=None
        )
        inp = INPUT(type=INPUT_KEYBOARD)
        inp._input.ki = ki
        inputs.append(inp)

    if inputs:
        arr = (INPUT * len(inputs))(*inputs)
        ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

# === Core operations ===
# === Основные операции ===

def save_current_position(slot):
    """
    Saves the current cursor position and window metadata into a slot.
    Called from Alt+Shift+<slot> hotkeys or from voice commands.

    Сохраняет текущую позицию курсора и метаданные окна в слот.
    Вызывается по горячей клавише Alt+Shift+<slot> или голосом.
    """
    if slot < 1 or slot > 99:
        print(f"[FOCUS] ❌ Слот {slot} вне диапазона 1-99")
        return False

    user32 = ctypes.windll.user32
    point = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    x, y = point.x, point.y

    hwnd = user32.GetForegroundWindow()
    window_class = _get_window_class(hwnd)
    window_exe = _get_window_exe(hwnd)
    window_title = _get_window_title(hwnd)

    # Store relative coordinates too so the target can be reconstructed after window moves.
    # Сохраняем и относительные координаты, чтобы восстановить цель после перемещения окна.
    rel_x, rel_y = 0.5, 0.5
    rect = _get_window_rect(hwnd)
    if rect:
        wl, wt, wr, wb = rect
        ww = wr - wl
        wh = wb - wt
        if ww > 0 and wh > 0:
            rel_x = (x - wl) / ww
            rel_y = (y - wt) / wh

    description = window_title[:50] if window_title else f"({x}, {y})"

    # Preserve voice labels when an existing slot is overwritten.
    # Если слот уже существовал, сохраняем его голосовые имена.
    old_voice_names = []
    if slot in _focus_slots:
        old_voice_names = _focus_slots[slot].get("voice_names", [])

    _focus_slots[slot] = {
        "x": x,
        "y": y,
        "rel_x": round(rel_x, 4),
        "rel_y": round(rel_y, 4),
        "hwnd": hwnd,
        "window_class": window_class,
        "window_exe": window_exe,
        "window_title": window_title,
        "description": description,
        "voice_names": old_voice_names,
    }
    short_desc = description[:30] + "…" if len(description) > 30 else description
    exe_info = f" [{window_exe}]" if window_exe else ""
    print(f"[FOCUS] 📌 Точка {slot}: ({x}, {y}){exe_info} — '{short_desc}'")
    if old_voice_names:
        print(f"[FOCUS]    Голосовые имена: {', '.join(old_voice_names)}")

    _notify_change()
    _show_focus_beacon(x, y)
    return True


def switch_to_position(slot):
    """
    Switches to a saved focus point.
    Resolves the target window by hwnd -> title -> exe+class, brings it forward, and clicks.

    Переключается на сохранённую точку фокуса.
    Ищет окно по hwnd -> title -> exe+class, поднимает его и кликает.
    """
    if slot not in _focus_slots:
        print(f"[FOCUS] ❌ Точка {slot} не сохранена")
        print(f"[FOCUS] Доступные: {sorted(_focus_slots.keys())}")
        return False

    info = _focus_slots[slot]
    desc = info.get("description", "")
    result = [False]
    actual_pos = [info["x"], info["y"]]

    def _do_switch():
        try:
            user32 = ctypes.windll.user32
            window_exe = info.get("window_exe", "")
            window_class = info.get("window_class", "")
            window_title = info.get("window_title", "")
            saved_hwnd = info.get("hwnd")
            saved_x = info["x"]
            saved_y = info["y"]
            target_x = saved_x
            target_y = saved_y

            if window_exe or window_class or saved_hwnd:
                hwnd = _find_window_by_info(
                    window_exe, window_class, window_title, saved_hwnd
                )

                if hwnd:
                    found_title = _get_window_title(hwnd)
                    used_saved = (hwnd == saved_hwnd)
                    
                    # Refresh the cached hwnd so the next restore can use the fast path.
                    # Обновляем hwnd в слоте, чтобы в следующий раз сработал быстрый путь.
                    info["hwnd"] = hwnd
                    # If the window was found by search, refresh the title as well.
                    # Если окно нашли поиском, обновляем и title, потому что он мог измениться.
                    if not used_saved and found_title:
                        info["window_title"] = found_title
                    
                    _force_foreground(hwnd)
                    time.sleep(0.15)

                    rect = _get_window_rect(hwnd)
                    if rect:
                        wl, wt, wr, wb = rect
                        if wl <= saved_x <= wr and wt <= saved_y <= wb:
                            target_x = saved_x
                            target_y = saved_y
                        else:
                            rel_x = info.get("rel_x", 0.5)
                            rel_y = info.get("rel_y", 0.5)
                            ww = wr - wl
                            wh = wb - wt
                            if ww > 0 and wh > 0:
                                target_x = int(wl + rel_x * ww)
                                target_y = int(wt + rel_y * wh)

                    method = "hwnd" if used_saved else "search"
                    short_title = found_title[:40] if found_title else "?"
                    print(f"[FOCUS] 🪟 Окно ({method}): {window_exe} '{short_title}' → ({target_x}, {target_y})")
                else:
                    print(f"[FOCUS] ⚠️ Окно не найдено — fallback ({target_x}, {target_y})")

            actual_pos[0] = target_x
            actual_pos[1] = target_y

            user32.SetCursorPos(target_x, target_y)
            time.sleep(0.05)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.03)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            result[0] = True
        except Exception as e:
            print(f"[FOCUS] ❌ Ошибка переключения: {e}")

    t = threading.Thread(target=_do_switch, daemon=True)
    t.start()
    t.join(timeout=5.0)

    if t.is_alive():
        print(f"[FOCUS] ⚠️ Таймаут 5с при переключении на точку {slot}")
        return False

    short_desc = desc[:30] + "…" if len(desc) > 30 else desc
    print(f"[FOCUS] ➡️ Точка {slot}: '{short_desc}'")
    threading.Thread(
        target=_show_focus_beacon,
        args=(actual_pos[0], actual_pos[1]),
        daemon=True
    ).start()
    return result[0]

# === Voice labels ===
# === Голосовые имена ===

def find_slot_by_voice_name(text):
    """
    Finds a slot by its voice label.
    Ищет слот по голосовому имени.

    text — нормализованный текст (lowercase, без пунктуации).
    text — нормализованный текст (lowercase, без пунктуации).

    Возвращает номер слота или None.
    Возвращает номер слота или None.

    Ограничение: текст не длиннее 3 слов (защита от ложных срабатываний).
    Ограничение: текст не длиннее 3 слов для защиты от ложных срабатываний.
    """
    text_clean = text.strip().lower().replace('ё', 'е')
    text_words = text_clean.split()

    if not text_words or len(text_words) > 3:
        return None

    best_slot = None
    best_len = -1
    text_word_set = set(text_words)

    for slot, info in _focus_slots.items():
        voice_names = info.get("voice_names", [])
        for name in voice_names:
            name_clean = name.strip().lower().replace('ё', 'е')
            if not name_clean or len(name_clean) < 2:
                continue
            # Exact name match wins immediately.
            # Точное совпадение имени побеждает сразу.
            if text_clean == name_clean:
                return slot
            # Otherwise prefer the longest label whose words are all present.
            # Иначе выбираем самое длинное имя, все слова которого есть в тексте.
            name_words = set(name_clean.split())
            if name_words.issubset(text_word_set) and len(name_clean) > best_len:
                best_slot = slot
                best_len = len(name_clean)

    return best_slot


def set_voice_names(slot, names):
    """Assigns voice labels to a slot.
    Назначает голосовые имена слоту."""
    if slot not in _focus_slots:
        return False
    _focus_slots[slot]["voice_names"] = names
    print(f"[FOCUS] 🏷️ Точка {slot}: имена = {names}")
    _notify_change()
    return True


def get_voice_names(slot):
    """Returns the voice labels for a slot.
    Возвращает голосовые имена слота."""
    if slot not in _focus_slots:
        return []
    return _focus_slots[slot].get("voice_names", [])


def delete_position(slot):
    """Deletes a focus point by slot number.
    Удаляет точку по номеру слота."""
    if slot in _focus_slots:
        desc = _focus_slots[slot].get("description", "?")
        del _focus_slots[slot]
        print(f"[FOCUS] 🗑️ Точка {slot} удалена: '{desc[:30]}'")
        _notify_change()
        return True
    return False


def clear_all_positions():
    """Deletes all focus points.
    Удаляет все точки."""
    _focus_slots.clear()
    print("[FOCUS] 🗑️ Все точки удалены")
    _notify_change()


def get_positions_for_save():
    """Returns the serialized form stored in config.json.
    Возвращает сериализованное представление для config.json."""
    result = {}
    for slot, info in _focus_slots.items():
        hwnd_val = info.get("hwnd")
        result[str(slot)] = {
            "x": info["x"],
            "y": info["y"],
            "rel_x": info.get("rel_x", 0.5),
            "rel_y": info.get("rel_y", 0.5),
            "hwnd": int(hwnd_val) if hwnd_val else None,
            "window_class": info.get("window_class", ""),
            "window_exe": info.get("window_exe", ""),
            "window_title": info.get("window_title", ""),
            "description": info.get("description", ""),
            "voice_names": info.get("voice_names", []),
        }
    return result


def get_positions_for_tray():
    """
    Returns the tray-friendly representation.
    Format: {"[1] Description": {"pos": [x, y], "voice_names": [...], "slot": N}, ...}

    Возвращает представление для трея.
    Формат: {"[1] Описание": {"pos": [x, y], "voice_names": [...], "slot": N}, ...}
    """
    result = {}
    for slot, info in sorted(_focus_slots.items()):
        desc = info.get("description", f"({info['x']}, {info['y']})")
        short_desc = desc[:25] + "…" if len(desc) > 25 else desc
        voice_names = info.get("voice_names", [])
        if voice_names:
            names_str = ", ".join(voice_names)
            if len(names_str) > 20:
                names_str = names_str[:17] + "…"
            label = f"[{slot}] {short_desc} 🏷️{names_str}"
        else:
            label = f"[{slot}] {short_desc}"
        result[label] = {
            "pos": [info["x"], info["y"]],
            "voice_names": voice_names,
            "slot": slot,
        }
    return result


def load_positions_from_config(positions_dict):
    """Loads saved positions from config.json on startup with backward compatibility.
    Загружает позиции из config.json при старте с обратной совместимостью."""
    global _focus_slots
    _focus_slots.clear()

    if not positions_dict:
        return

    user32 = ctypes.windll.user32

    for key, val in positions_dict.items():
        if key.isdigit():
            slot = int(key)
            if 1 <= slot <= 99 and isinstance(val, dict):
                # Restore the saved hwnd only if it still points to the expected window.
                # Восстанавливаем HWND только если он всё ещё указывает на ожидаемое окно.
                saved_hwnd = val.get("hwnd")
                validated_hwnd = None
                if saved_hwnd is not None:
                    try:
                        saved_hwnd = int(saved_hwnd)
                        if user32.IsWindow(saved_hwnd) and user32.IsWindowVisible(saved_hwnd):
                            # Match the executable too because Windows may recycle hwnd values.
                            # Проверяем и exe, потому что Windows может переиспользовать hwnd.
                            expected_exe = val.get("window_exe", "")
                            if expected_exe:
                                actual_exe = _get_window_exe(saved_hwnd)
                                if actual_exe == expected_exe:
                                    validated_hwnd = saved_hwnd
                            else:
                                validated_hwnd = saved_hwnd
                    except (ValueError, TypeError):
                        pass

                hwnd_status = "✅" if validated_hwnd else "🔄"
                _focus_slots[slot] = {
                    "x": val.get("x", 0),
                    "y": val.get("y", 0),
                    "rel_x": val.get("rel_x", 0.5),
                    "rel_y": val.get("rel_y", 0.5),
                    "hwnd": validated_hwnd,
                    "window_class": val.get("window_class", ""),
                    "window_exe": val.get("window_exe", ""),
                    "window_title": val.get("window_title", ""),
                    "description": val.get("description", f"({val.get('x', 0)}, {val.get('y', 0)})"),
                    "voice_names": val.get("voice_names", []),
                }
        else:
            # Support the legacy format: {"window_title": [x, y]}.
            # Поддерживаем старый формат: {"window_title": [x, y]}.
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                hwnd_status = "🔄"
                for s in range(1, 100):
                    if s not in _focus_slots:
                        _focus_slots[s] = {
                            "x": val[0],
                            "y": val[1],
                            "rel_x": 0.5,
                            "rel_y": 0.5,
                            "hwnd": None,
                            "window_class": "",
                            "window_exe": "",
                            "window_title": key,
                            "description": key,
                            "voice_names": [],
                        }
                        break

    if _focus_slots:
        print(f"[FOCUS] Загружено {len(_focus_slots)} точек:")
        for slot, info in sorted(_focus_slots.items()):
            d = info['description'][:30]
            names = info.get('voice_names', [])
            names_str = f" 🏷️[{', '.join(names)}]" if names else ""
            exe = info.get('window_exe', '')
            exe_str = f" ({exe})" if exe else ""
            hwnd = info.get('hwnd')
            hwnd_str = f" hwnd={hwnd}✅" if hwnd else " hwnd=🔄"
            print(f"  [{slot}] ({info['x']}, {info['y']}){exe_str}{hwnd_str} — '{d}'{names_str}")


def get_slot_count():
    """Returns the number of saved focus points.
    Возвращает количество сохранённых точек."""
    return len(_focus_slots)


def _show_focus_beacon(x, y):
    """Shows a visual beacon when focus jumps to a saved point.
    Показывает визуальный маячок при переключении на сохранённую точку."""
    try:
        from mouse_controller import _flash_cursor_beacon
        _flash_cursor_beacon(x, y, radius=50, flashes=2)
    except Exception:
        pass


# === Hotkeys: Alt+Shift+1..9 ===
# === Горячие клавиши: Alt+Shift+1..9 ===

_hotkey_thread = None
_hotkey_running = False


def start_hotkey_listener():
    """Starts the background Alt+Shift+1..9 hotkey listener.
    Запускает фоновый слушатель горячих клавиш Alt+Shift+1..9."""
    global _hotkey_thread, _hotkey_running
    if _hotkey_running:
        return
    _hotkey_running = True
    _hotkey_thread = threading.Thread(target=_hotkey_loop, daemon=True)
    _hotkey_thread.start()
    print("[FOCUS] ⌨️ Горячие клавиши: Alt+Shift+1..9 для сохранения точек")


def stop_hotkey_listener():
    """Stops the hotkey listener.
    Останавливает слушатель горячих клавиш."""
    global _hotkey_running
    _hotkey_running = False


def _hotkey_loop():
    """Polling loop for Alt+Shift+1..9 hotkeys.
    Цикл опроса горячих клавиш Alt+Shift+1..9."""
    user32 = ctypes.windll.user32
    VK_SHIFT = 0x10
    VK_MENU = 0x12
    VK_1 = 0x31
    cooldown = {}

    while _hotkey_running:
        shift = user32.GetAsyncKeyState(VK_SHIFT) & 0x8000
        alt = user32.GetAsyncKeyState(VK_MENU) & 0x8000
        if shift and alt:
            for i in range(9):
                vk = VK_1 + i
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    slot = i + 1
                    now = time.time()
                    if now - cooldown.get(slot, 0) > 0.5:
                        cooldown[slot] = now
                        save_current_position(slot)
        time.sleep(0.05)
