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
Single source of truth for application directories.
Единая точка определения директорий приложения.

Работает и при запуске из исходников, и из собранного PyInstaller exe.
Works both from source and from the packaged PyInstaller executable.

ROOT_DIR is the application directory (exe, bin/, models/) and may be read-only.
ROOT_DIR — директория программы (exe, bin/, models/) и может быть только для чтения.

DATA_DIR stores user data (config, logs, scripts) and must always be writable.
DATA_DIR — директория пользовательских данных (config, logs, scripts), она всегда должна быть доступна на запись.
"""

import os
import sys
from pathlib import Path


def get_root() -> Path:
    """
    Returns the application root directory:
    - Development: <project>/src/app_paths.py -> <project>
    - PyInstaller --onedir: <dist>/VoxBee.exe -> <dist>

    Возвращает корневую директорию приложения:
    - Разработка: <project>/src/app_paths.py -> <project>
    - PyInstaller --onedir: <dist>/VoxBee.exe -> <dist>
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """
    Returns the user-data directory.
    - Development: the project root
    - PyInstaller: %APPDATA%/VoxBee (always writable)

    Возвращает директорию пользовательских данных.
    - Разработка: совпадает с корнем проекта
    - PyInstaller: %APPDATA%/VoxBee (всегда writable)
    """
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))
        data_dir = Path(appdata) / 'VoxBee'
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    return Path(__file__).parent.parent


# The application directory may be read-only, for example under Program Files.
# Директория программы может быть только для чтения, например в Program Files.
ROOT_DIR = get_root()
BIN_DIR = ROOT_DIR / "bin"
MODELS_DIR = ROOT_DIR / "models"

# User data always goes to a writable directory.
# Пользовательские данные всегда хранятся в каталоге с правом записи.
DATA_DIR = get_data_dir()
SCRIPTS_DIR = DATA_DIR / "scripts"
LOGS_DIR = DATA_DIR / "logs"
CONFIG_PATH = DATA_DIR / "config.json"
COMMANDS_PATH = DATA_DIR / "commands.json"
ALIASES_PATH = DATA_DIR / "aliases.json"
SCRIPTS_JSON_PATH = DATA_DIR / "scripts.json"
USER_DICT_PATH = DATA_DIR / "user_dictionary.json"


def get_template_path(filename: str) -> Path:
    """
    Returns the path to a template file bundled with the application.
    Dev:    src/<filename>
    Frozen: _MEIPASS/<filename> -> next to the exe

    Возвращает путь к файлу-шаблону, встроенному в приложение.
    Dev:    src/<filename>
    Frozen: _MEIPASS/<filename> -> рядом с exe
    """
    if getattr(sys, 'frozen', False):
        meipass = Path(getattr(sys, '_MEIPASS', ''))
        if meipass and (meipass / filename).exists():
            return meipass / filename
        return Path(sys.executable).parent / filename
    return Path(__file__).parent / filename
