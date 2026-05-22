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

# runtime_hook.py
"""PyInstaller runtime hook — добавляет путь к модулям."""
import sys
import os

# В frozen режиме модули лежат в _MEIPASS (temp) или рядом с exe
if getattr(sys, 'frozen', False):
    # PyInstaller распаковывает в sys._MEIPASS
    base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    src_path = os.path.join(base, 'src_modules')
    if os.path.exists(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)
