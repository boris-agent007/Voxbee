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
Application configuration storage.
Конфигурация приложения.

Stores settings in config.json near the executable or source tree.
Сохраняет настройки в config.json рядом с exe или исходниками.
"""

import json
import threading
from app_paths import CONFIG_PATH

_config_lock = threading.Lock()

DEFAULT_CONFIG = {
    "microphone_index": None,
    "microphone_name": "",
    "use_gpu": False,
    "model_name": "auto",
    "language": "ru",
    "threads": 0,
    "vad_aggressiveness": 1,
    "vad_silence_duration": 0.8,
    "vad_accept_short_speech": True,
    "vad_mode": False,                    
    "warmup_on_start": True,
    "pre_buffer_sec": 0.5,
    "max_duration_sec": 180,
    "mouse_step": 150,
    "noise_filter_enabled": True,
    "log_enabled": False,
    "log_directory": "",
    "trigger_button": "middle",
    # Text-fixing options control which post-processing stages are enabled.
    # Параметры исправления текста управляют включёнными этапами постобработки.
    "text_fix_enabled": True,
    "text_fix_hallucinations": True,
    "text_fix_dictionary": True,
    "text_fix_punctuation": True,
    "text_fix_repetitions": True,
    "text_fix_user_dict": True,
    "show_recognition_result": True,
    "math_mode": False,

}


def load_config():
    config = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            config.update(saved)
            print(f"[CONFIG] Загружен: {CONFIG_PATH}")
        except Exception as e:
            print(f"[CONFIG] Ошибка чтения: {e}, используем дефолт")
    else:
        save_config(config)
        print(f"[CONFIG] Создан новый: {CONFIG_PATH}")
    return config


def save_config(config):
    with _config_lock:
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[CONFIG ERROR] {e}")
