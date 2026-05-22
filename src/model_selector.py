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
Scans the models/ directory and reports available models
with speed and quality hints.
Сканирует папку models/ и показывает доступные модели
с подсказками по скорости и качеству.
"""

from pathlib import Path
from app_paths import MODELS_DIR

# Model metadata indexed by filename.
# Справочник метаданных моделей по имени файла.
MODEL_INFO = {
    "ggml-tiny.bin": {
        "label": "Tiny",
        "size_mb": 75,
        "speed": "⚡⚡⚡ Мгновенно",
        "quality": "★☆☆☆☆ Низкая",
        "cpu": "Любой (Celeron, Atom)",
        "ram": "~200 MB",
    },
    "ggml-tiny-q5_1.bin": {
        "label": "Tiny Q5",
        "size_mb": 45,
        "speed": "⚡⚡⚡ Мгновенно",
        "quality": "★☆☆☆☆ Низкая",
        "cpu": "Любой",
        "ram": "~150 MB",
    },
    "ggml-base.bin": {
        "label": "Base",
        "size_mb": 142,
        "speed": "⚡⚡ Быстро",
        "quality": "★★☆☆☆ Нормальная",
        "cpu": "i3 / Ryzen 3",
        "ram": "~400 MB",
    },
    "ggml-base-q5_1.bin": {
        "label": "Base Q5",
        "size_mb": 90,
        "speed": "⚡⚡ Быстро",
        "quality": "★★☆☆☆ Нормальная",
        "cpu": "i3 / Ryzen 3",
        "ram": "~300 MB",
    },
    "ggml-small.bin": {
        "label": "Small",
        "size_mb": 466,
        "speed": "⚡ Средне",
        "quality": "★★★☆☆ Хорошая",
        "cpu": "i5 / Ryzen 5",
        "ram": "~1 GB",
    },
    "ggml-small-q5_1.bin": {
        "label": "Small Q5",
        "size_mb": 300,
        "speed": "⚡ Средне",
        "quality": "★★★☆☆ Хорошая",
        "cpu": "i5 / Ryzen 5",
        "ram": "~700 MB",
    },
    "ggml-medium.bin": {
        "label": "Medium",
        "size_mb": 1500,
        "speed": "🐢 Медленно",
        "quality": "★★★★☆ Высокая",
        "cpu": "i7 / Ryzen 7",
        "ram": "~2.5 GB",
    },
    "ggml-medium-q5_0.bin": {
        "label": "Medium Q5",
        "size_mb": 950,
        "speed": "🐢 Медленно",
        "quality": "★★★★☆ Высокая",
        "cpu": "i7 / Ryzen 7",
        "ram": "~1.5 GB",
    },
    "ggml-large-v2.bin": {
        "label": "Large v2",
        "size_mb": 3100,
        "speed": "🐌 Очень медленно",
        "quality": "★★★★★ Максимальная",
        "cpu": "i9 / Ryzen 9 или GPU",
        "ram": "~5 GB",
    },
    "ggml-large-v3.bin": {
        "label": "Large v3",
        "size_mb": 3100,
        "speed": "🐌 Очень медленно",
        "quality": "★★★★★ Максимальная",
        "cpu": "i9 / Ryzen 9 или GPU",
        "ram": "~5 GB",
    },
    "ggml-large-v3-turbo.bin": {
        "label": "Large v3 Turbo",
        "size_mb": 1600,
        "speed": "🐢 Медленно (быстрее Large)",
        "quality": "★★★★★ Максимальная",
        "cpu": "i7+ или GPU",
        "ram": "~3 GB",
    },
    "ggml-large-v3-turbo-q5_0.bin": {
        "label": "Large v3 Turbo Q5",
        "size_mb": 1100,
        "speed": "🐢 Средне-медленно",
        "quality": "★★★★☆ Очень высокая",
        "cpu": "i7+ или GPU",
        "ram": "~2 GB",
    },
}

# Preference order from best to worst for auto-selection.
# Порядок от лучшей к худшей для режима auto.
MODEL_PRIORITY = [
    "ggml-large-v3-turbo.bin",
    "ggml-large-v3.bin",
    "ggml-large-v3-turbo-q5_0.bin",
    "ggml-large-v2.bin",
    "ggml-medium.bin",
    "ggml-medium-q5_0.bin",
    "ggml-small.bin",
    "ggml-small-q5_1.bin",
    "ggml-base.bin",
    "ggml-base-q5_1.bin",
    "ggml-tiny.bin",
    "ggml-tiny-q5_1.bin",
]


def scan_models(models_dir=None):
    """
    Scans models/ and returns the list of available models.
    Each item looks like {name, path, size_mb, label, speed, quality, ...}.

    Сканирует папку models/ и возвращает список доступных моделей.
    Каждый элемент имеет вид {name, path, size_mb, label, speed, quality, ...}.
    """
    if models_dir is None:
        models_dir = MODELS_DIR
    else:
        models_dir = Path(models_dir)

    found = []
    bins = list(models_dir.glob("ggml-*.bin"))

    for bin_path in bins:
        name = bin_path.name
        size_mb = bin_path.stat().st_size / (1024 * 1024)

        info = MODEL_INFO.get(name, None)

        if info:
            entry = {
                "name": name,
                "path": str(bin_path),
                "size_mb": size_mb,
                "label": info["label"],
                "speed": info["speed"],
                "quality": info["quality"],
                "cpu": info["cpu"],
                "ram": info["ram"],
            }
        else:
            # Unknown models get a best-effort description based on the filename and size.
            # Для неизвестной модели описание подбирается по имени файла и размеру.
            label = name.replace("ggml-", "").replace(".bin", "").title()
            speed, quality, cpu = _guess_model_info(name, size_mb)
            entry = {
                "name": name,
                "path": str(bin_path),
                "size_mb": size_mb,
                "label": label,
                "speed": speed,
                "quality": quality,
                "cpu": cpu,
                "ram": f"~{int(size_mb * 2)} MB",
            }

        found.append(entry)

    # Keep the strongest known models at the top for auto mode.
    # Сортируем по приоритету, чтобы лучшие модели были сверху для auto.
    def sort_key(m):
        try:
            return MODEL_PRIORITY.index(m["name"])
        except ValueError:
            return 999

    found.sort(key=sort_key)
    return found


def _guess_model_info(name, size_mb):
    """Guesses the profile of an unknown model from its size.
    Подбирает характеристики неизвестной модели по её размеру."""
    if size_mb < 100:
        return "⚡⚡⚡ Мгновенно", "★☆☆☆☆", "Любой"
    elif size_mb < 200:
        return "⚡⚡ Быстро", "★★☆☆☆", "i3+"
    elif size_mb < 600:
        return "⚡ Средне", "★★★☆☆", "i5+"
    elif size_mb < 1800:
        return "🐢 Медленно", "★★★★☆", "i7+"
    else:
        return "🐌 Очень медленно", "★★★★★", "i9+ / GPU"


def find_best_model(models_dir=None):
    """Returns the best available model for auto mode.
    Возвращает лучшую доступную модель для режима auto."""
    models = scan_models(models_dir)
    if models:
        return models[0]
    return None


def find_model_by_name(model_name, models_dir=None):
    """Finds a specific model by filename.
    Ищет конкретную модель по имени файла."""
    if models_dir is None:
        models_dir = MODELS_DIR
    else:
        models_dir = Path(models_dir)

    path = models_dir / model_name
    if path.exists():
        info = MODEL_INFO.get(model_name, {})
        size_mb = path.stat().st_size / (1024 * 1024)
        return {
            "name": model_name,
            "path": str(path),
            "size_mb": size_mb,
            "label": info.get("label", model_name),
        }
    return None


def print_models(models=None):
    """Prints the model list in a readable format.
    Выводит список моделей в удобном для чтения виде."""
    if models is None:
        models = scan_models()

    print("\n" + "=" * 65)
    print("  🧠 ДОСТУПНЫЕ МОДЕЛИ WHISPER")
    print("=" * 65)

    if not models:
        print("  ❌ Модели не найдены в папке models/")
        print("  Скачайте: https://huggingface.co/ggerganov/whisper.cpp/tree/main")
        return

    for i, m in enumerate(models):
        marker = "→ " if i == 0 else "  "
        print(f"\n  {marker}📦 {m['name']}")
        print(f"     Размер:   {m['size_mb']:.0f} MB")
        print(f"     Скорость: {m['speed']}")
        print(f"     Качество: {m['quality']}")
        print(f"     CPU:      {m['cpu']}")
        print(f"     RAM:      {m['ram']}")

    print()
    print(f"  → = лучшая доступная (используется при auto)")
    print("=" * 65)


def select_model_interactive():
    """Interactive model selection in the console.
    Интерактивный выбор модели в консоли."""
    models = scan_models()
    print_models(models)

    if not models:
        return "auto"

    print("\nВведите имя файла модели (или Enter для auto):")

    while True:
        try:
            choice = input("\n> ").strip()

            if choice == "" or choice.lower() == "auto":
                best = models[0]
                print(f"[MODEL] Auto → {best['name']}")
                return "auto"

            # Allow numeric selection by list index.
            # Разрешаем выбор по номеру из списка.
            try:
                idx = int(choice)
                if 0 <= idx < len(models):
                    m = models[idx]
                    print(f"[MODEL] ✅ Выбрана: {m['name']}")
                    return m['name']
            except ValueError:
                pass

            # Fallback to substring matching by filename or label.
            # Если номер не подошёл, ищем по части имени или label.
            match = None
            for m in models:
                if choice in m['name'] or choice.lower() in m['label'].lower():
                    match = m
                    break

            if match:
                print(f"[MODEL] ✅ Выбрана: {match['name']}")
                return match['name']

            print(f"Модель '{choice}' не найдена. Доступные:")
            for i, m in enumerate(models):
                print(f"  [{i}] {m['name']}")

        except KeyboardInterrupt:
            print("\nОтмена — используем auto")
            return "auto"
