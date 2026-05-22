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

# src/input_sender.py
"""
Низкоуровневая отправка клавиш через Win32 API.
Общий модуль для command_executor и других потребителей.
"""

import ctypes
import time


def send_hotkey(hotkey_str):
    """Отправляет комбинацию клавиш. Формат: 'ctrl+s', 'ctrl+shift+p'"""
    VK_MAP = {
        'ctrl': 0x11, 'control': 0x11,
        'alt': 0x12, 'menu': 0x12,
        'shift': 0x10,
        'win': 0x5B, 'windows': 0x5B,
        'enter': 0x0D, 'return': 0x0D,
        'tab': 0x09,
        'escape': 0x1B, 'esc': 0x1B,
        'space': 0x20,
        'backspace': 0x08,
        'delete': 0x2E, 'del': 0x2E,
        'home': 0x24,
        'end': 0x23,
        'pageup': 0x21,
        'pagedown': 0x22,
        'up': 0x26, 'down': 0x28,
        'left': 0x25, 'right': 0x27,
        'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
        'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
        'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    }

    SCAN_MAP = {
        0x0D: 0x1C, 0x11: 0x1D, 0x10: 0x2A, 0x12: 0x38,
        0x09: 0x0F, 0x1B: 0x01, 0x20: 0x39, 0x08: 0x0E,
        0x2E: 0x53, 0x24: 0x47, 0x23: 0x4F, 0x21: 0x49,
        0x22: 0x51, 0x26: 0x48, 0x28: 0x50, 0x25: 0x4B,
        0x27: 0x4D, 0x5B: 0x5B,
        0x70: 0x3B, 0x71: 0x3C, 0x72: 0x3D, 0x73: 0x3E,
        0x74: 0x3F, 0x75: 0x40, 0x76: 0x41, 0x77: 0x42,
        0x78: 0x43, 0x79: 0x44, 0x7A: 0x57, 0x7B: 0x58,
    }

    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_EXTENDEDKEY = 0x0001

    EXTENDED_VKS = frozenset({
        0x21, 0x22,  # PageUp, PageDown
        0x23, 0x24,  # End, Home
        0x25, 0x26, 0x27, 0x28,  # Left, Up, Right, Down
        0x2E,  # Delete
        0x5B,  # Win
    })

    keys = [k.strip().lower() for k in hotkey_str.split('+')]
    vk_codes = []

    for key in keys:
        if key in VK_MAP:
            vk_codes.append(VK_MAP[key])
        elif len(key) == 1:
            vk_codes.append(ord(key.upper()))
        else:
            print(f"[HOTKEY] ⚠️ Неизвестная клавиша: {key}")
            return

    for vk in vk_codes:
        scan = SCAN_MAP.get(vk, user32.MapVirtualKeyW(vk, 0))
        flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0
        user32.keybd_event(vk, scan, flags, 0)
        time.sleep(0.01)

    for vk in reversed(vk_codes):
        scan = SCAN_MAP.get(vk, user32.MapVirtualKeyW(vk, 0))
        flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0)
        user32.keybd_event(vk, scan, flags, 0)
        time.sleep(0.01)

    print(f"[HOTKEY] ⌨️ {hotkey_str}")
