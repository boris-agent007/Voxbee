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
# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для Vox Bee.
PyInstaller spec for Vox Bee.

Сборка: pyinstaller vox_bee.spec --noconfirm
Build: pyinstaller vox_bee.spec --noconfirm
"""

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)
SRC = ROOT / 'src'

# Копируем Python-модули из `src/` как данные, чтобы приложение могло читать их во время выполнения.
# Copy Python modules from `src/` as data so the application can read them at runtime.
src_modules = []
for py_file in SRC.glob('*.py'):
    src_modules.append((str(py_file), 'src_modules'))


# Иконки трея для всех состояний приложения.
# Tray icons for all application states.
ico_datas = [
    (str(SRC / 'voxbee.ico'), '.'),
    (str(SRC / 'voxbee_off.ico'), '.'),
    (str(SRC / 'voxbee_recording.ico'), '.'),
]  

png_icon_datas = [
(str(SRC / 'voxbee_full.png'), '.'),
]

# Шаблоны JSON, из которых создаются пользовательские файлы при первом запуске.
# JSON templates used to create user files on first launch.
template_datas = [
    (str(SRC / 'commands_template.json'), '.'),
    (str(SRC / 'aliases_template.json'), '.'),
]

a = Analysis(
    [str(SRC / 'main.py')],
    pathex=[str(SRC), str(ROOT)],
    binaries=[],
    datas=src_modules + ico_datas + png_icon_datas + template_datas,
    hiddenimports=[
        'pynput.mouse._win32',
        'pynput.keyboard._win32',
        'pystray._win32',
        'sounddevice',
        '_sounddevice_data',
        'numpy',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'win32gui',
        'win32con',
        'win32api',
        'win32process',
        'win32com',
        'win32com.client',
        'pythoncom',
        'pywintypes',
        'requests',
        'urllib3',
        'charset_normalizer',
        'certifi',
        'idna',
        'noisereduce',
        'scipy',
        'scipy.signal',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / 'runtime_hook.py')],
    excludes=[
        'matplotlib', 'tkinter.test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VoxBee',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SRC / 'voxbee.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VoxBee',
)
