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
Manages application autostart through the Windows registry.
Управление автозапуском приложения через реестр Windows.

HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
"""

import sys
import winreg
from pathlib import Path
from app_paths import get_root

APP_NAME = "VoxBee"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_exe_path() -> str:
    """Returns the executable path or the Python entry command in development mode.
    Возвращает путь к exe или команду запуска через Python в режиме разработки."""
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).resolve())
    # Development mode starts the app through the Python interpreter.
    # В режиме разработки приложение запускается через интерпретатор Python.
    main_path = (get_root() / "src" / "main.py").resolve()
    return f'"{Path(sys.executable).resolve()}" "{main_path}"'


def is_autostart_enabled() -> bool:
    """Checks whether autostart is enabled.
    Проверяет, включён ли автозапуск."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable_autostart():
    """Adds the application to autostart.
    Добавляет приложение в автозагрузку."""
    exe_path = _get_exe_path()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        print(f"[AUTOSTART] ✅ Добавлено: {exe_path}")
        return True
    except OSError as e:
        print(f"[AUTOSTART] ❌ Ошибка: {e}")
        return False


def disable_autostart():
    """Removes the application from autostart.
    Удаляет приложение из автозагрузки."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        print("[AUTOSTART] ✅ Удалено из автозагрузки")
        return True
    except FileNotFoundError:
        return True  # уже нет
    except OSError as e:
        print(f"[AUTOSTART] ❌ Ошибка: {e}")
        return False


def toggle_autostart(enable: bool):
    """Enables or disables autostart.
    Включает или выключает автозапуск."""
    if enable:
        return enable_autostart()
    else:
        return disable_autostart()
