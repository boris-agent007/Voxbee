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
Mouse listener with a custom trigger.
Слушатель мыши с кастомным триггером.

The user assigns the button/combination through the tray.
Пользователь сам назначает кнопку/комбинацию через трей.
"""

import ctypes
from pynput import mouse

# --- Modifier virtual-key codes ---
# --- Коды модификаторов ---
VK_CONTROL = 0x11
VK_ALT = 0x12
VK_SHIFT = 0x10

# Human-readable mouse button labels.
# Человекочитаемые имена кнопок мыши
BUTTON_LABELS = {
    "ru": {
        "left": "ЛКМ",
        "right": "ПКМ",
        "middle": "Колёсико",
        "x1": "Боковая ◀",
        "x2": "Боковая ▶",
    },
    "en": {
        "left": "LMB",
        "right": "RMB",
        "middle": "Middle Mouse",
        "x1": "Side ◀",
        "x2": "Side ▶",
    },
}

MODIFIER_LABELS = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
}

# Human-readable keyboard key labels.
# Человекочитаемые имена клавиш клавиатуры
KEY_LABELS = {
    "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4",
    "f5": "F5", "f6": "F6", "f7": "F7", "f8": "F8",
    "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
    "insert": "Insert", "delete": "Delete", "home": "Home", "end": "End",
    "page_up": "Page Up", "page_down": "Page Down",
    "pause": "Pause", "scroll_lock": "Scroll Lock",
    "num_lock": "Num Lock", "caps_lock": "Caps Lock",
    "print_screen": "Print Screen",
}

# Virtual-key codes for keys, used to check the pressed state.
# VK-коды для клавиш (для проверки нажатия)
KEY_VK_CODES = {
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "page_up": 0x21, "page_down": 0x22,
    "pause": 0x13, "scroll_lock": 0x91,
    "num_lock": 0x90, "caps_lock": 0x14,
    "print_screen": 0x2C,
    **{chr(c).lower(): c for c in range(0x41, 0x5B)},
    **{str(i): 0x30 + i for i in range(10)},
}



def is_key_pressed(vk_code):
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


def get_current_modifiers():
    """Returns the list of modifiers currently being held.
    Возвращает список зажатых модификаторов прямо сейчас."""
    mods = []
    if is_key_pressed(VK_CONTROL):
        mods.append("ctrl")
    if is_key_pressed(VK_ALT):
        mods.append("alt")
    if is_key_pressed(VK_SHIFT):
        mods.append("shift")
    return mods


def get_button_name(button):
    """Safely returns the mouse button name.
    Безопасно получить имя кнопки мыши."""
    return getattr(button, 'name', str(button))


def trigger_to_label(trigger, language="ru"):
    """Formats a trigger for UI display.
    Форматирует триггер для отображения в интерфейсе."""
    if not trigger:
        return "Not assigned" if language == "en" else "Не назначена"

    btn = trigger.get("button", "middle")
    mods = trigger.get("modifiers", [])

    parts = []
    for m in mods:
        parts.append(MODIFIER_LABELS.get(m, m))

    # Keyboard trigger in the "key:f2" format.
    # Если это клавиша клавиатуры (формат "key:f2")
    if btn.startswith("key:"):
        key_name = btn[4:]
        parts.append(KEY_LABELS.get(key_name, key_name.upper()))
    else:
        labels = BUTTON_LABELS.get(language, BUTTON_LABELS["ru"])
        parts.append(labels.get(btn, btn))

    return " + ".join(parts)


def trigger_to_config(trigger):
    """Converts a trigger dict into a config.json string.
    Превращает trigger dict в строку для config.json."""
    if not trigger:
        return "middle"
    btn = trigger.get("button", "middle")
    mods = trigger.get("modifiers", [])
    if mods:
        return "+".join(mods) + "+" + btn
    return btn


def config_to_trigger(config_str):
    """Parses a stored trigger string from config.json.
    Разбирает строковое представление триггера из config.json."""
    if not config_str:
        return {"button": "middle", "modifiers": []}

    parts = config_str.split("+")
    button = parts[-1]
    modifiers = parts[:-1]

    return {"button": button, "modifiers": modifiers}


def check_trigger_press(button, trigger):
    """Checks a mouse-button press, not a keyboard trigger.
    Проверяет нажатие кнопки мыши (не клавиатуры)."""
    btn = get_button_name(button)
    expected_btn = trigger.get("button", "middle")
    expected_mods = trigger.get("modifiers", [])

    # Do not check mouse state when the trigger is keyboard-based.
    # Если триггер — клавиша клавиатуры, мышь не проверяем
    if expected_btn.startswith("key:"):
        return False

    if btn != expected_btn:
        return False

    for mod in expected_mods:
        if mod == "ctrl" and not is_key_pressed(VK_CONTROL):
            return False
        if mod == "alt" and not is_key_pressed(VK_ALT):
            return False
        if mod == "shift" and not is_key_pressed(VK_SHIFT):
            return False

    return True


def check_trigger_release(button, trigger):
    """Checks mouse-button release.
    Проверяет отпускание кнопки мыши."""
    btn = get_button_name(button)
    expected_btn = trigger.get("button", "middle")

    if expected_btn.startswith("key:"):
        return False

    return btn == expected_btn

def check_key_trigger_press(key, trigger):
    """Checks a keyboard key press used as a trigger.
    Проверяет нажатие клавиши клавиатуры как триггера."""
    expected_btn = trigger.get("button", "middle")
    expected_mods = trigger.get("modifiers", [])

    if not expected_btn.startswith("key:"):
        return False

    key_name = expected_btn[4:]
    vk_code = KEY_VK_CODES.get(key_name)
    if not vk_code:
        return False

    # Ensure that this exact key is currently pressed.
    # Проверяем что именно эта клавиша нажата
    if not is_key_pressed(vk_code):
        return False

    # Verify the pynput key identity as well.
    # Проверяем pynput key
    pressed_name = _get_key_name(key)
    if pressed_name != key_name:
        return False

    for mod in expected_mods:
        if mod == "ctrl" and not is_key_pressed(VK_CONTROL):
            return False
        if mod == "alt" and not is_key_pressed(VK_ALT):
            return False
        if mod == "shift" and not is_key_pressed(VK_SHIFT):
            return False

    return True


def check_key_trigger_release(key, trigger):
    """Checks release of a keyboard trigger key.
    Проверяет отпускание клавиши-триггера."""
    expected_btn = trigger.get("button", "middle")

    if not expected_btn.startswith("key:"):
        return False

    key_name = expected_btn[4:]
    released_name = _get_key_name(key)
    return released_name == key_name


def _get_key_name(key):
    """Extracts the key name from a pynput key object.
    Извлекает имя клавиши из pynput key объекта."""
    from pynput import keyboard
    if hasattr(key, 'name'):
        # Key.f1 -> "f1", Key.insert -> "insert".
        # Key.f1 → "f1", Key.insert → "insert"
        return key.name.lower()
    if hasattr(key, 'vk'):
        # Fall back to lookup by virtual-key code.
        # По VK-коду ищем
        for name, vk in KEY_VK_CODES.items():
            if key.vk == vk:
                return name
    return None



# Virtual-key code for V.
# VK-код для V
_VK_V = 0x56


def check_paste_dictated_hotkey(key):
    """
    Checks whether Ctrl+Alt+V was pressed to paste dictated text.
    Проверяет, нажата ли комбинация Ctrl+Alt+V (вставка надиктованного).
    Returns True if the hotkey matches.
    Возвращает True если хоткей совпал.
    """
    # Determine whether the pressed key is V.
    # Определяем: нажата ли клавиша V
    pressed_name = _get_key_name(key)
    is_v = False
    if pressed_name == 'v':
        is_v = True
    else:
        char = getattr(key, 'char', None)
        if char and char.lower() == 'v':
            is_v = True
        else:
            vk = getattr(key, 'vk', None)
            if vk == _VK_V:
                is_v = True

    if not is_v:
        return False

    # Ctrl+Alt must be pressed while Shift must stay released.
    # Ctrl+Alt зажаты, Shift НЕ зажат
    if not is_key_pressed(VK_CONTROL):
        return False
    if not is_key_pressed(VK_ALT):
        return False
    if is_key_pressed(VK_SHIFT):
        return False

    return True


class MouseListener:
    """Owns pynput mouse and optional keyboard listeners.
    Владеет pynput-слушателями мыши и, при необходимости, клавиатуры."""
    def __init__(self, mouse_callback, key_callback=None):
        self.mouse_callback = mouse_callback
        self.key_callback = key_callback
        self.mouse_listener = None
        self.key_listener = None

    def on_click(self, x, y, button, pressed):
        try:
            self.mouse_callback(x, y, button, pressed)
        except Exception as e:
            print(f"[MOUSE ERROR] {e}")

    def on_key_press(self, key):
        try:
            if self.key_callback:
                self.key_callback(key, True)
        except Exception as e:
            print(f"[KEY ERROR] {e}")

    def on_key_release(self, key):
        try:
            if self.key_callback:
                self.key_callback(key, False)
        except Exception as e:
            print(f"[KEY ERROR] {e}")

    def start(self):
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.mouse_listener.start()

        if self.key_callback:
            from pynput import keyboard
            self.key_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release,
            )
            self.key_listener.start()

    def stop(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.key_listener:
            self.key_listener.stop()
