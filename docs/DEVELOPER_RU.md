<!--
Copyright (C) 2026 Boris Shkylnikov
SPDX-License-Identifier: GPL-3.0-or-later

This file is part of Vox Bee.

Vox Bee is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3.

Vox Bee is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Vox Bee. If not, see <https://www.gnu.org/licenses/>.
-->
<h1 align="center">
  <strong><img src="../src/voxbee_full.png" width="64" alt="Vox Bee" valign="middle"> Vox Bee — Руководство разработчика</strong>
</h1>

<p align="center">
  <strong><a href="DEVELOPER.md">🇬🇧 Read in English</a></strong>
</p>

---

## 📋 Содержание

- [1. Требования](#1-требования)
- [2. Настройка окружения](#2-настройка-окружения)
- [3. Запуск из исходников](#3-запуск-из-исходников)
- [4. Архитектура проекта](#4-архитектура-проекта)
- [5. Система конфигурации](#5-система-конфигурации)
- [6. Система команд](#6-система-команд)
- [7. Отладка и логирование](#7-отладка-и-логирование)
- [8. Сборка EXE](#8-сборка-exe)
- [9. Сборка установщика](#9-сборка-установщика)
- [10. Участие в проекте](#10-участие-в-проекте)
- [11. Решение проблем разработки](#11-решение-проблем-разработки)

---

<a id="1-требования"></a>
## 🧰 1. Требования

| Компонент | Версия | Обязательно | Примечания |
|-----------|--------|-------------|------------|
| **Python** | 3.12.8 | ✅ | Протестированная версия. Другие 3.10+ могут работать |
| **Windows** | 10/11 64-bit | ✅ | Linux/macOS не поддерживаются |
| **VC++ Redistributable** | 2015-2022 | ✅ | Требуется для whisper.cpp DLL — [скачать](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| **Git** | Любая | ❌ | Для клонирования; можно скачать ZIP |
| **Inno Setup** | 6.x | ❌ | Только для сборки установщика |
| **NVIDIA GPU** | CUDA | ❌ | Для GPU-ускорения |

---

## ⚖️ Лицензирование репозитория

Для production-оформления на GitHub в этом проекте достаточно следующей схемы:

- **корневой файл `LICENSE`** — основной и единственный канонический текст лицензии GPLv3;
- **README-файлы** должны ссылаться именно на корневой `LICENSE`;
- дубли лицензии в `docs/` держать не нужно;
- отдельный `NOTICE` для GPLv3 в этом проекте не требуется;
- шапки лицензии в каждый `.py` файл добавлять необязательно, если в репозитории уже есть корректный корневой `LICENSE` и понятные ссылки из README.

Если позже потребуется строгая политика copyright headers, её лучше вводить отдельно и единообразно для всех исходников.

---

<a id="2-настройка-окружения"></a>
## 🛠️ 2. Настройка окружения

### 2.1. Установка Python

Скачайте **Python 3.12.8** с [python.org](https://www.python.org/downloads/release/python-3128/).
При установке отметьте **☑ Add Python to PATH**.

```bash
python --version
# Ожидается: Python 3.12.8
```

### 2.2. Клонирование и установка зависимостей

```bash
git clone https://github.com/YOUR_USERNAME/vox_bee.git
cd vox_bee

python -m venv venv
venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

**Проверка:**

```bash
python -c "import pynput, sounddevice, numpy, pystray; print('OK')"
```

### 2.3. Скачивание whisper.cpp и моделей

**Исполняемые файлы:** [whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases)

| Архив | Куда распаковать |
|-------|-----------------|
| `whisper-blas-bin-x64.zip` | `bin/cpu/` |
| `whisper-cublas-bin-x64.zip` | `bin/gpu/` (опционально, только NVIDIA) |

**Модели:** [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main) — скачайте хотя бы один `.bin` файл в `models/`.

### 2.4. Проверка структуры

```
vox_bee/
├── bin/
│   ├── cpu/
│   │   ├── whisper-cli.exe       ← обязательно
│   │   └── *.dll
│   └── gpu/                      ← опционально
│       └── *.exe, *.dll
├── models/
│   └── ggml-base.bin             ← минимум одна модель
├── src/
│   └── main.py                   ← точка входа
└── requirements.txt
```

`venv/` используется только локально в dev-среде и не считается частью GitHub-репозитория.

---

<a id="3-запуск-из-исходников"></a>
## ▶️ 3. Запуск из исходников

```bash
venv\Scripts\activate
python src/main.py
```

**CLI-аргументы:**

| Аргумент | Описание |
|----------|----------|
| `--select-mic` | Интерактивный выбор микрофона |
| `--select-model` | Интерактивный выбор модели |
| `--list-models` | Показать доступные модели и выйти |
| `--run-script <path>` | Выполнить `.py` скрипт и выйти (VoxBee как интерпретатор) |

**Ожидаемый вывод:**

```
[OK] whisper: whisper-cli.exe
[OK] модель:  ggml-base.bin (148 MB) — [рейтинг скорости]
[i]  Только CPU (это нормально!)

=======================================================
  VoxBee — голосовой ввод
  [PC]   Режим:       CPU
  [AI]   Модель:      auto
  [MIC]  Микрофон:    [имя микрофона]
  [EDIT] Исправление: ВКЛ
  [>]    Триггер:     Колёсико (средняя кнопка мыши)
  [DIR]  Данные:      C:\Users\...\AppData\Roaming\VoxBee
=======================================================
```

**Single Instance:** приложение использует Windows mutex (`Global\VoxBee_SingleInstance`). Второй экземпляр тихо завершится.

---

<a id="4-архитектура-проекта"></a>
## 🏗️ 4. Архитектура проекта

### 4.1. Структура каталогов

```
vox_bee/
├── src/                          # Исходный код и встроенные шаблоны
│   ├── main.py                   # Точка входа, инициализация, главный цикл, callbacks
│   ├── app_paths.py              # Пути dev/frozen, ROOT_DIR vs DATA_DIR
│   ├── config.py                 # Загрузка/сохранение конфигурации
│   ├── recorder.py               # Запись аудио
│   ├── stt.py                    # Распознавание речи через whisper.cpp
│   ├── inserter.py               # Вставка текста в активное окно
│   ├── input_sender.py           # Низкоуровневая отправка клавиш и текста
│   ├── active_text_field.py      # Определение активного текстового поля
│   ├── tray_icon.py              # Трей и его меню
│   ├── settings_window.py        # Окно настроек
│   ├── about_window.py           # Окно "О программе"
│   ├── ui_strings.py             # Локализованные строки интерфейса
│   ├── ui_copy_handler.py        # Работа с буфером обмена и copy-flow
│   ├── mouse_listener.py         # Слушатель мыши и клавиатуры
│   ├── mouse_controller.py       # Управление мышью, сетка, прокрутка, непрерывное движение
│   ├── selection_overlay.py      # Оверлей выделения и сетки
│   ├── command_executor.py       # Голосовые команды: сопоставление и выполнение
│   ├── script_manager.py         # Пользовательские скрипты и их запуск
│   ├── script_manager_ui.py      # GUI менеджера скриптов
│   ├── focus_manager.py          # Точки фокуса
│   ├── vad_detector.py           # Детектор голосовой активности
│   ├── noise_filter.py           # Шумоподавление
│   ├── text_fixer.py             # Постобработка распознанного текста
│   ├── math_converter.py         # Режим математики
│   ├── mic_selector.py           # Выбор микрофона
│   ├── model_selector.py         # Выбор модели
│   ├── autostart.py              # Автозапуск Windows
│   ├── commands_template.json    # Шаблон команд
│   ├── aliases_template.json     # Шаблон алиасов
│   ├── voxbee.ico                # Основная иконка
│   ├── voxbee_off.ico            # Иконка состояния OFF
│   ├── voxbee_recording.ico      # Иконка состояния RECORDING
│   └── voxbee_full.png           # PNG для окон интерфейса
├── bin/                          # whisper.cpp binaries (CPU/GPU)
├── models/                       # Модели Whisper GGML (.bin)
├── requirements.txt              # Зависимости Python
├── vox_bee.spec                  # Конфигурация PyInstaller
├── runtime_hook.py               # Runtime hook PyInstaller
├── LICENSE                       # Лицензия проекта
└── .gitignore                    # Исключения Git
```

**Опционально в полном локальном проекте, но не обязательно в GitHub-репозитории:**

- `scripts/` — примеры или локальные пользовательские скрипты;
- `build.bat` — локальный bat-сценарий сборки;
- `installer.iss` — сценарий сборки инсталлятора Inno Setup;
- `src/diagnose.py` — диагностический скрипт;
- `src/create_icon.py` — генератор иконок, не участвующий в runtime и сборке;
- локальные пользовательские файлы `config.json`, `commands.json`, `aliases.json`, `scripts.json`, `user_dictionary.json` — создаются и используются как данные, а не как часть исходников репозитория.

### 4.2. Поток данных


Микрофон → Recorder (sounddevice) → WAV-файл → STT (whisper.cpp subprocess)
  → сырой текст → TextFixer (5 этапов постобработки)
  → CommandExecutor (если совпал триггер) → hotkey / мышь / скрипт / фокус
  → Inserter (если обычный текст) → вставка в активное окно


### 4.3. Потоки

| Поток | Назначение | Модуль |
|-------|------------|--------|
| Main | `while True: sleep(1)`, обработка сигналов | `main.py` |
| pystray | Цикл иконки в трее | `tray_icon.py` |
| tk-ui | Mainloop tkinter (попапы, настройки) | `tray_icon.py` |
| ui-worker | Очередь обновлений иконки/меню | `tray_icon.py` |
| sounddevice | Callback аудио | `recorder.py` |
| mic-watchdog | Мониторинг подключения микрофона | `recorder.py` |
| stt | Распознавание (на каждый запрос) | `main.py` → `stt.py` |
| log-flush | Сброс лога в файл (каждые 3 мин) | `main.py` |
| focus-hotkey | Слушатель Alt+Shift+N | `focus_manager.py` |

### 4.4. Ключевые архитектурные решения

- **whisper.cpp как subprocess** — без Python-биндингов; WAV → stdout. Легко обновлять версии.
- **Серверный режим** — whisper-cli как постоянный процесс (`--keep-context`). Откат на одноразовый subprocess при ошибке.
- **Конфиг в AppData** — `%APPDATA%\VoxBee\` для пользовательских данных. В dev-режиме — корень проекта.
- **Файлы-шаблоны** — `commands_template.json`, `aliases_template.json` в `src/` → копируются в AppData при первом запуске.
- **Единый Tk-поток** — все tkinter-операции через выделенный поток с очередью.

### 4.5. Правила потокобезопасности

- **НЕ вызывать tkinter** из любого потока, кроме tk-ui. Использовать `tray._run_in_tk()`.
- **save_config()** — потокобезопасен (внутренний `threading.Lock`).
- **НЕ использовать pyautogui** из callback sounddevice — блокировка ввода.
- **VAD-обработка** защищена `_vad_lock` — предотвращает параллельный запуск STT.

---

<a id="5-система-конфигурации"></a>
## ⚙️ 5. Система конфигурации

**Пути (определяются в `app_paths.py`):**

| Переменная | Dev-режим | Frozen (PyInstaller) |
|------------|-----------|----------------------|
| `ROOT_DIR` | Корень проекта | Папка с `.exe` |
| `DATA_DIR` | Корень проекта | `%APPDATA%\VoxBee\` |
| `BIN_DIR` | `<root>/bin/` | `<root>/bin/` |
| `LOGS_DIR` | `<root>/logs/` | `%APPDATA%\VoxBee\logs\` |
| `CONFIG_PATH` | `<root>/config.json` | `%APPDATA%\VoxBee\config.json` |

**Ключевые поля конфига** (полный список — `DEFAULT_CONFIG` в `config.py`):

| Поле | По умолчанию | Описание |
|------|--------------|----------|
| `model_name` | `"auto"` | Имя модели или `"auto"` (выбор лучшей) |
| `use_gpu` | `false` | GPU (CUDA) режим |
| `vad_mode` | `false` | Авто-определение речи |
| `trigger_button` | `"middle"` | Кнопка триггера записи |
| `warmup_on_start` | `true` | Держать модель в памяти (серверный режим) |
| `log_enabled` | `false` | Запись логов в файл |
| `log_directory` | `""` | Папка логов (пустая = `LOGS_DIR`) |

**Формат:** JSON UTF-8. Запись через `save_config()` с `threading.Lock`.

---

<a id="6-система-команд"></a>
## 🗣️ 6. Система команд

**Файлы (в AppData):**

| Файл | Назначение |
|------|------------|
| `commands.json` | Триггеры → действия |
| `aliases.json` | Фонетические алиасы: ошибка STT → правильное слово |
| `scripts.json` | Скрипты с триггерами |

**Формат команды:**

```json
{
    "command_id": {
        "triggers": {
            "ru": ["фраза 1", "фраза 2"],
            "en": ["phrase 1", "phrase 2"]
        },
        "type": "тип_действия",
        "value": "параметр"
    }
}
```

`triggers` также поддерживает legacy-формат списка, но актуальный формат для репозитория — языковые блоки `ru/en/common`.

**Типы действий:** `paste`, `hotkey`, `mouse_move`, `mouse_continuous`, `mouse_stop`, `mouse_click`, `mouse_scroll`, `mouse_scroll_max`, `mouse_monitor`, `grid`, `grid_zoom`, `focus_switch`, `focus_save`, `selection_more`, `selection_less`, `toggle_math_mode`.

**Отдельно о скриптах:** пользовательские скрипты не описываются типом внутри `commands.json`; они регистрируются через `scripts.json` и разрешаются через `script_manager.py`.

Реализация — см. `command_executor.py`.

**Поток разрешения алиасов:**

```
Сырой текст → lowercase → слова → замена через aliases.json → сопоставление с триггерами
```

---

<a id="7-отладка-и-логирование"></a>
## 🐞 7. Отладка и логирование

### 7.1. Логирование

Приложение логирует через `print()`. Все сообщения автоматически получают временну́ю метку `[HH:MM:SS]`.

**Логирование в файл:**

- Включается через `log_enabled: true` в конфиге (или через трей/настройки).
- Файлы: `voice_input_YYYYMMDD_HHMMSS.log` в `LOGS_DIR` (или `log_directory`).
- Буферизация: сброс в файл каждые 3 минуты (`_PeriodicFileSink`).
- При включённом файловом логе — вывод идёт одновременно в консоль и файл (`_TeeStream`).
- Кодировка: Эмодзи заменяются на ASCII-эквиваленты (✅ → [OK]) для совместимости с cp1251.

### 7.2. Запуск с консолью (dev)

При запуске через `python src/main.py` консоль всегда доступна.

Для сборки с консолью — см. раздел 8.

### 7.3. Тестирование отдельных модулей

**Подготовка тестового аудио:**

Перед тестированием STT нужен WAV-файл с речью.

**Запись через встроенный рекордер:**

1. Узнайте номер микрофона:

```bash
cd src
python -c "from mic_selector import list_microphones; mics = list_microphones(); [print(f'[{m[\"index\"]}] {m[\"name\"]}') for m in mics]"
```

2. Запомните номер нужного микрофона (например, `1`), затем запишите:

```bash
python -c "from recorder import AudioRecorder; import time; r = AudioRecorder(device_index=1); r.start_listening(); print('Говорите 3 сек...'); r.start_capture(); time.sleep(3); r.stop_capture(); r.save_to_wav('../test.wav'); r.stop_listening(); print('Готово: test.wav')"
cd ..
```

> ⚠️ **Замените `device_index=1` на ваш номер микрофона.**

**Альтернатива** — любой WAV-файл:

Скопируйте любой WAV с речью в корень проекта как `test.wav`. Формат 16kHz mono идеален, но другие тоже работают.

---

**whisper-cli напрямую (без Python):**

Распознавание через CPU:

```bash
bin\cpu\whisper-cli.exe -m models\ggml-large-v3-turbo.bin -f test.wav -l ru
```

Распознавание через GPU (требуется NVIDIA):

```bash
bin\gpu\whisper-cli.exe -m models\ggml-large-v3-turbo.bin -f test.wav -l ru
```

---

**Диагностика системы:**

```bash
python src/diagnose.py
```

### 7.4. Тестирование

Автоматических тестов нет. Тестирование ручное.

**Минимальный чеклист:**

1. Запуск → иконка в трее появляется
2. Средняя кнопка мыши → запись → отпускание → текст вставляется
3. VAD-режим → речь распознаётся автоматически
4. Смена микрофона/модели через трей
5. Голосовые команды (если `commands_enabled`)
6. Выключение через трей → процесс завершается чисто

---

<a id="8-сборка-exe"></a>
## 📦 8. Сборка EXE

**Полная сборка (EXE + установщик, с очисткой):**

```bash
venv\Scripts\activate
build.bat
```

`build.bat` выполняет: очистка `build/`, `dist/` → PyInstaller → создание папок (`bin`, `models`, `scripts`) → сборка установщика (если `iscc` доступен).

**Только EXE (без очистки и установщика):**

```bash
venv\Scripts\activate
pyinstaller vox_bee.spec
```

Результат: `dist/VoxBee/VoxBee.exe`

**Ключевые настройки в `vox_bee.spec`:**

- `console=False` — без окна консоли в релизе
- `runtime_hooks` → `runtime_hook.py`
- `hiddenimports` — pynput, pystray, win32, sounddevice, noisereduce и др.
- `excludes` → matplotlib (не нужен в runtime)
- ICO-файлы и JSON-шаблоны упаковываются как data

**Отладочная сборка:** измените `console=False` на `console=True` в `vox_bee.spec` (строка 98).

> ⚠️ При `console=True` закрытие окна консоли убивает приложение.

---

<a id="9-сборка-установщика"></a>
## 🧱 9. Сборка установщика

**Требования:** Inno Setup 6 ([jrsoftware.org](https://jrsoftware.org/isinfo.php)) + собранный EXE в `dist/VoxBee/`.

```bash
iscc installer.iss
# Результат: installer_output/VoxBee_Setup_X.Y.Z.exe
```

**Возможности установщика** (определены в `installer.iss`):

- Кастомная страница расположения файлов (модели, CPU, GPU с автодетектом)
- Опциональная установка VC++ Runtime
- Ярлык на рабочем столе, автозапуск
- Деинсталляция с опцией удаления `%APPDATA%\VoxBee\`

**Чеклист обновления версии:**

При выпуске нового релиза версию нужно обновить **во всех местах**, иначе пользователь увидит разные номера:

| Файл | Строка | Что изменить |
|------|--------|--------------|
| `installer.iss` | 4 | `#define MyAppVersion "1.0.1"` → `"1.0.2"` |
| `installer.iss` | 35 | `VersionInfoVersion=1.0.1.0` → `1.0.2.0` |
| `README_RU.md` | 8 | `Version-1.0.1-green` → `Version-1.0.2-green` |
| `README_RU.md` | 38 | `VoxBee_Setup_1.0.1.exe` → `VoxBee_Setup_1.0.2.exe` |
| `README.md` | — | То же самое (бейдж + ссылка на установщик) |

**Быстрая проверка перед релизом:**

```bash
grep -rn "1.0.1" README*.md installer.iss
```

---

<a id="10-участие-в-проекте"></a>
## 🤝 10. Участие в проекте

**Что нужнее всего:**

1. Тестирование на разном оборудовании (CPU, GPU, микрофоны) — результаты в issues
2. Баг-репорты с характеристиками оборудования и шагами воспроизведения
3. Переводы команд/триггеров для других языков

**Стиль кода:**

- Python 3.12, UTF-8
- Комментарии на русском или английском
- Логирование через `print()` (без модуля `logging` — намеренно)
- Аннотации типов не обязательны

**Формат коммитов:**

```
Add: описание новой функции
Fix: описание бага
Refactor: что было изменено
Docs: изменения в документации
```

---

<a id="11-решение-проблем-разработки"></a>
## 🚑 11. Решение проблем разработки

**`ModuleNotFoundError: No module named 'win32gui'`**

`pywin32` есть в requirements.txt, но это особенный пакет — он содержит DLL, которые нужно зарегистрировать в Windows. Иногда `pip install` устанавливает файлы, но не регистрирует DLL (особенно в venv или при конфликте с Anaconda).

**Решение:**

```bash
# Переустановка с принудительной регистрацией DLL
pip install --force-reinstall pywin32==311
python venv/Scripts/pywin32_postinstall.py -install
```

**`whisper-cli.exe` не запускается** → установите VC++ Redistributable.

**Второй экземпляр не запускается** → Windows mutex. Завершите первый:

```bash
taskkill /f /im python.exe
```

**Сборка PyInstaller падает:**

```bash
rmdir /s /q build dist
pyinstaller vox_bee.spec
# или просто: build.bat (сам очищает перед сборкой)
```

**Кодировка в консоли** — символы `?` вместо эмодзи нормальны на cp1251. Используйте Windows Terminal или `chcp 65001`.

---

## 🔗 Ссылки

| Ресурс | URL |
|--------|-----|
| whisper.cpp releases | https://github.com/ggml-org/whisper.cpp/releases |
| Модели Whisper | https://huggingface.co/ggerganov/whisper.cpp |
| Python 3.12.8 | https://www.python.org/downloads/release/python-3128/ |
| VC++ Redistributable | https://aka.ms/vs/17/release/vc_redist.x64.exe |
| Inno Setup | https://jrsoftware.org/isinfo.php |
| PyInstaller | https://pyinstaller.org |
