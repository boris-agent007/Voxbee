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

import win32gui


def get_active_edit_handle():
    """
    Возвращает HWND активного окна.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            print(f"[FIELD] Активное окно: '{title}' ({class_name})")
            return hwnd
        return 0
    except Exception as e:
        print(f"[FIELD ERROR] {e}")
        return 0
