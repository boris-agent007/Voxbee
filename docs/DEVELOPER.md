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
  <strong><img src="../src/voxbee_full.png" width="64" alt="Vox Bee" valign="middle"> Vox Bee — Developer Guide</strong>
</h1>

<p align="center">
  <strong><a href="DEVELOPER_RU.md">🇷🇺 Читать на русском</a></strong>
</p>

---

## 📋 Table of Contents

- [1. Prerequisites](#1-prerequisites)
- [2. Setting Up Development Environment](#2-setting-up-development-environment)
- [3. Running from Source](#3-running-from-source)
- [4. Project Architecture](#4-project-architecture)
- [5. Configuration System](#5-configuration-system)
- [6. Command System](#6-command-system)
- [7. Debugging and Logging](#7-debugging-and-logging)
- [8. Building EXE](#8-building-exe)
- [9. Building Installer](#9-building-installer)
- [10. Contributing](#10-contributing)
- [11. Development Troubleshooting](#11-development-troubleshooting)

---

<a id="1-prerequisites"></a>
## 🧰 1. Prerequisites

| Component | Version | Required | Notes |
|-----------|---------|----------|-------|
| **Python** | 3.12.8 | ✅ Yes | Tested version. Other 3.10+ may work |
| **Windows** | 10/11 64-bit | ✅ Yes | Linux/macOS not supported |
| **VC++ Redistributable** | 2015-2022 | ✅ Yes | Required for whisper.cpp DLLs — [download](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| **Git** | Any | ❌ Optional | For cloning; can download ZIP instead |
| **Inno Setup** | 6.x | ❌ Optional | Only for building installer |
| **NVIDIA GPU** | CUDA-compatible | ❌ Optional | For GPU acceleration |

---

## ⚖️ Repository Licensing

For production setup on GitHub, the following scheme is sufficient for this project:

- **root `LICENSE` file** — the main and only canonical text of the GPLv3 license;
- **README files** must link specifically to the root `LICENSE`;
- duplicates of the license in `docs/` are not needed;
- a separate `NOTICE` for GPLv3 is not required in this project;
- adding license headers to every `.py` file is optional, if the repository already has a correct root `LICENSE` and clear links from the README.

If a strict copyright headers policy is required later, it's better to introduce it separately and uniformly for all source files.

---

<a id="2-setting-up-development-environment"></a>
## 🛠️ 2. Setting Up Development Environment

### 2.1. Install Python

Download **Python 3.12.8** from [python.org](https://www.python.org/downloads/release/python-3128/).
During installation, check **☑ Add Python to PATH**.

```bash
python --version
# Expected: Python 3.12.8
```

### 2.2. Clone and Install Dependencies

```bash
git clone https://github.com/YOUR_USERNAME/vox_bee.git
cd vox_bee

python -m venv venv
venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

**Verify:**

```bash
python -c "import pynput, sounddevice, numpy, pystray; print('OK')"
```

### 2.3. Download whisper.cpp and Models

**Executable files:** [whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases)

| Archive | Extract to |
|-------|-----------------|
| `whisper-blas-bin-x64.zip` | `bin/cpu/` |
| `whisper-cublas-bin-x64.zip` | `bin/gpu/` (optional, NVIDIA only) |

**Models:** [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main) — download at least one `.bin` file into `models/`.

### 2.4. Verify Directory Structure

```
vox_bee/
├── bin/
│   ├── cpu/
│   │   ├── whisper-cli.exe       ← required
│   │   └── *.dll
│   └── gpu/                      ← optional
│       └── *.exe, *.dll
├── models/
│   └── ggml-base.bin             ← at least one model
├── src/
│   └── main.py                   ← entry point
└── requirements.txt
```

`venv/` is local to the development environment and is not considered part of the GitHub repository.

---

<a id="3-running-from-source"></a>
## ▶️ 3. Running from Source

```bash
venv\Scripts\activate
python src/main.py
```

**CLI Arguments:**

| Argument | Description |
|----------|-------------|
| `--select-mic` | Interactive microphone selection |
| `--select-model` | Interactive model selection |
| `--list-models` | Show available models and exit |
| `--run-script <path>` | Execute a `.py` script and exit (VoxBee as an interpreter) |

**Expected Console Output:**

```text
[OK] whisper: whisper-cli.exe
[OK] model:   ggml-base.bin (148 MB) — [speed rating]
[i]  CPU only (this is normal!)

=======================================================
  VoxBee — voice input
  [PC]   Mode:        CPU
  [AI]   Model:       auto
  [MIC]  Microphone:  [mic name]
  [EDIT] Correction:  ON
  [>]    Trigger:     Wheel (middle mouse button)
  [DIR]  Data:        C:\Users\...\AppData\Roaming\VoxBee
=======================================================
```

**Single Instance:** The application uses a Windows mutex (`Global\VoxBee_SingleInstance`). A second instance will terminate silently.

---

<a id="4-project-architecture"></a>
## 🏗️ 4. Project Architecture

### 4.1. Directory Structure

```text
vox_bee/
├── src/                          # Source code and bundled templates
│   ├── main.py                   # Entry point, initialization, main loop, callbacks
│   ├── app_paths.py              # Dev/frozen paths, ROOT_DIR vs DATA_DIR
│   ├── config.py                 # Configuration load/save
│   ├── recorder.py               # Audio recording
│   ├── stt.py                    # Speech recognition via whisper.cpp
│   ├── inserter.py               # Text insertion into the active window
│   ├── input_sender.py           # Low-level key and text sending
│   ├── active_text_field.py      # Active text field detection
│   ├── tray_icon.py              # Tray icon and menu
│   ├── settings_window.py        # Settings window
│   ├── about_window.py           # About window
│   ├── ui_strings.py             # Localized UI strings
│   ├── ui_copy_handler.py        # Clipboard and copy-flow helpers
│   ├── mouse_listener.py         # Mouse and keyboard listener
│   ├── mouse_controller.py       # Mouse control, grid, scrolling, continuous movement
│   ├── selection_overlay.py      # Selection/grid overlay
│   ├── command_executor.py       # Voice command matching and execution
│   ├── script_manager.py         # User scripts and script launching
│   ├── script_manager_ui.py      # Script manager GUI
│   ├── focus_manager.py          # Focus points
│   ├── vad_detector.py           # Voice activity detection
│   ├── noise_filter.py           # Noise suppression
│   ├── text_fixer.py             # Recognized-text post-processing
│   ├── math_converter.py         # Math mode
│   ├── mic_selector.py           # Microphone selection
│   ├── model_selector.py         # Model selection
│   ├── autostart.py              # Windows autostart
│   ├── commands_template.json    # Command template
│   ├── aliases_template.json     # Alias template
│   ├── voxbee.ico                # Main icon
│   ├── voxbee_off.ico            # OFF-state icon
│   ├── voxbee_recording.ico      # RECORDING-state icon
│   └── voxbee_full.png           # PNG used by UI windows
├── bin/                          # whisper.cpp binaries (CPU/GPU)
├── models/                       # Whisper GGML models (.bin)
├── requirements.txt              # Python dependencies
├── vox_bee.spec                  # PyInstaller configuration
├── runtime_hook.py               # PyInstaller runtime hook
├── LICENSE                       # Project license
└── .gitignore                    # Git exclusions
```

**Optional in a full local workspace, but not required in the GitHub repository:**

- `scripts/` — sample or local user scripts;
- `build.bat` — local batch build script;
- `installer.iss` — Inno Setup installer script;
- `src/diagnose.py` — diagnostic utility;
- `src/create_icon.py` — icon generator not used in runtime or build;
- local user-data files `config.json`, `commands.json`, `aliases.json`, `scripts.json`, `user_dictionary.json` — generated and used as data, not as repository source files.

### 4.2. Data Flow

```text
Microphone → Recorder (sounddevice) → WAV file → STT (whisper.cpp subprocess)
  → raw text → TextFixer (5 stages of post-processing)
  → CommandExecutor (if trigger matches) → hotkey / mouse / script / focus
  → Inserter (if plain text) → insertion into active window
```

### 4.3. Threading Model

| Thread | Purpose | Module |
|--------|---------|--------|
| Main | Main loop (`while True: sleep(1)`), signal handling | `main.py` |
| pystray | System tray icon run loop | `tray_icon.py` |
| tk-ui | Tkinter mainloop for popups, settings, dialogs | `tray_icon.py` |
| ui-worker | Queue-based tray icon/menu updates | `tray_icon.py` |
| sounddevice | Audio callback (recording) | `recorder.py` |
| mic-watchdog | Monitors microphone connection | `recorder.py` |
| stt | Speech recognition (per-request) | `main.py` → `stt.py` |
| log-flush | Periodic log file flush (every 3 min) | `main.py` |
| focus-hotkey | `Alt+Shift+N` hotkey listener | `focus_manager.py` |

### 4.4. Key Design Decisions

- **whisper.cpp as subprocess** — no Python bindings; WAV → stdout. Easy to update versions.
- **Server mode** — whisper-cli as a persistent process (`--keep-context`). Fallback to one-time subprocess on error.
- **Config in AppData** — `%APPDATA%\VoxBee\` for user data. In dev mode — project root.
- **Template files** — `commands_template.json`, `aliases_template.json` in `src/` → copied to AppData on first launch.
- **Dedicated UI thread** — all tkinter operations via a dedicated thread with a queue.

### 4.5. Thread Safety Rules

- **DO NOT call tkinter** from any thread other than tk-ui. Use `tray._run_in_tk()`.
- **save_config()** is thread-safe (internal `threading.Lock`).
- **DO NOT use pyautogui** from the sounddevice callback — it blocks input.
- **VAD processing** is protected by `_vad_lock` — prevents parallel STT execution.

---

<a id="5-configuration-system"></a>
## ⚙️ 5. Configuration System

**Paths (defined in `app_paths.py`):**

| Variable | Dev mode | Frozen (PyInstaller) |
|------------|-----------|----------------------|
| `ROOT_DIR` | Project root | Folder with `.exe` |
| `DATA_DIR` | Project root | `%APPDATA%\VoxBee\` |
| `BIN_DIR` | `<root>/bin/` | `<root>/bin/` |
| `LOGS_DIR` | `<root>/logs/` | `%APPDATA%\VoxBee\logs\` |
| `CONFIG_PATH` | `<root>/config.json` | `%APPDATA%\VoxBee\config.json` |

**Key config fields** (full list — `DEFAULT_CONFIG` in `config.py`):

| Field | Default | Description |
|-------|---------|-------------|
| `model_name` | `"auto"` | Model name or `"auto"` (select best) |
| `use_gpu` | `false` | GPU (CUDA) mode |
| `vad_mode` | `false` | Auto-detect speech (VAD) |
| `trigger_button` | `"middle"` | Record trigger button |
| `warmup_on_start` | `true` | Keep model in memory (server mode) |
| `log_enabled` | `false` | Enable logging to file |
| `log_directory` | `""` | Log folder (empty = `LOGS_DIR`) |

**Format:** UTF-8 JSON. Written via `save_config()` with `threading.Lock`.

---

<a id="6-command-system"></a>
## 🗣️ 6. Command System

**Files (in AppData):**

| File | Purpose |
|------|---------|
| `commands.json` | Triggers → Actions |
| `aliases.json` | Phonetic aliases: STT error → Correct word |
| `scripts.json` | Scripts with triggers |

**Command format:**

```json
{
    "command_id": {
        "triggers": {
            "ru": ["фраза 1", "фраза 2"],
            "en": ["phrase 1", "phrase 2"]
        },
        "type": "action_type",
        "value": "parameter"
    }
}
```

`triggers` also supports the legacy list format, but the current repository format is the multilingual `ru/en/common` object.

**Action types:** `paste`, `hotkey`, `mouse_move`, `mouse_continuous`, `mouse_stop`, `mouse_click`, `mouse_scroll`, `mouse_scroll_max`, `mouse_monitor`, `grid`, `grid_zoom`, `focus_switch`, `focus_save`, `selection_more`, `selection_less`, `toggle_math_mode`.

**Scripts are handled separately:** user scripts are not declared as a `commands.json` action type; they are registered via `scripts.json` and resolved through `script_manager.py`.

Implementation — see `command_executor.py`.

**Alias resolution flow:**

```text
Raw STT text → lowercase → words → replacement via aliases.json → matching with triggers
```

---

<a id="7-debugging-and-logging"></a>
## 🐞 7. Debugging and Logging

### 7.1. Logging

The application logs via `print()`. All messages automatically receive a timestamp `[HH:MM:SS]`.

**File Logging:**

- Enabled via `log_enabled: true` in config (or through tray/settings).
- Files: `voice_input_YYYYMMDD_HHMMSS.log` in `LOGS_DIR` (or `log_directory`).
- Buffering: flushed to file every 3 minutes (`_PeriodicFileSink`).
- When file logging is enabled, output goes simultaneously to console and file (`_TeeStream`).
- Encoding: Emojis are replaced with ASCII equivalents (✅ → [OK]) for cp1251 compatibility.

### 7.2. Running with Console (Dev)

When launched via `python src/main.py`, the console is always available.

For building with a console — see Section 8.

### 7.3. Testing Individual Modules

**Preparing test audio:**

Before testing STT, you need a WAV file with speech.

**Recording via built-in recorder:**

1. Find out the microphone index:

```bash
cd src
python -c "from mic_selector import list_microphones; mics = list_microphones(); [print(f'[{m[\"index\"]}] {m[\"name\"]}') for m in mics]"
```

2. Note the index of the required microphone (e.g., `1`), then record:

```bash
python -c "from recorder import AudioRecorder; import time; r = AudioRecorder(device_index=1); r.start_listening(); print('Speak for 3 secs...'); r.start_capture(); time.sleep(3); r.stop_capture(); r.save_to_wav('../test.wav'); r.stop_listening(); print('Done: test.wav')"
cd ..
```

> ⚠️ **Replace `device_index=1` with your microphone index.**

**Alternative** — any WAV file:

Copy any WAV file with speech to the project root as `test.wav`. 16kHz mono format is ideal, but others work too.

---

**whisper-cli directly (without Python):**

Recognition via CPU:

```bash
bin\cpu\whisper-cli.exe -m models\ggml-large-v3-turbo.bin -f test.wav -l ru
```

Recognition via GPU (NVIDIA required):

```bash
bin\gpu\whisper-cli.exe -m models\ggml-large-v3-turbo.bin -f test.wav -l ru
```

---

**System Diagnostics:**

```bash
python src/diagnose.py
```

### 7.4. Testing

There are no automated tests. Testing is manual.

**Minimal Checklist:**

1. Launch → tray icon appears
2. Middle mouse button → record → release → text is inserted
3. VAD mode → speech is recognized automatically
4. Change microphone/model via tray
5. Voice commands (if `commands_enabled`)
6. Exit via tray → process terminates cleanly

---

<a id="8-building-exe"></a>
## 📦 8. Building EXE

**Full build (EXE + installer, with cleanup):**

```bash
venv\Scripts\activate
build.bat
```

`build.bat` performs: cleaning `build/`, `dist/` → PyInstaller → creating folders (`bin`, `models`, `scripts`) → building installer (if `iscc` is available).

**EXE only (no cleanup, no installer):**

```bash
venv\Scripts\activate
pyinstaller vox_bee.spec
```

Result: `dist/VoxBee/VoxBee.exe`

**Key settings in `vox_bee.spec`:**

- `console=False` — no console window in release
- `runtime_hooks` → `runtime_hook.py`
- `hiddenimports` — pynput, pystray, win32, sounddevice, noisereduce, etc.
- `excludes` → matplotlib (not needed in runtime)
- ICO files and JSON templates are packaged as data

**Debug build:** change `console=False` to `console=True` in `vox_bee.spec` (line 98).

> ⚠️ With `console=True`, closing the console window kills the application.

---

<a id="9-building-installer"></a>
## 🧱 9. Building Installer

**Requirements:** Inno Setup 6 ([jrsoftware.org](https://jrsoftware.org/isinfo.php)) + built EXE in `dist/VoxBee/`.

```bash
iscc installer.iss
# Result: installer_output/VoxBee_Setup_X.Y.Z.exe
```

**Installer features** (defined in `installer.iss`):

- Custom file location page (models, CPU, GPU with auto-detect)
- Optional VC++ Runtime installation
- Desktop shortcut, autostart
- Uninstallation with an option to remove `%APPDATA%\VoxBee\`

**Release checklist:**

When releasing a new version, update the version number **everywhere**, otherwise the user will see inconsistent numbers:

| File | Line | What to update |
|------|------|----------------|
| `installer.iss` | 4 | `#define MyAppVersion "1.0.1"` → `"1.0.2"` |
| `installer.iss` | 35 | `VersionInfoVersion=1.0.1.0` → `1.0.2.0` |
| `README_RU.md` | 8 | `Version-1.0.1-green` → `Version-1.0.2-green` |
| `README_RU.md` | 38 | `VoxBee_Setup_1.0.1.exe` → `VoxBee_Setup_1.0.2.exe` |
| `README.md` | — | The same (badge + installer setup link) |

**Quick check before release:**

```bash
grep -rn "1.0.1" README*.md installer.iss
```

---

<a id="10-contributing"></a>
## 🤝 10. Contributing

**Most useful contributions:**

1. Hardware testing on different CPUs, GPUs, and microphones — post results in issues
2. Bug reports with hardware details and reproduction steps
3. Command/trigger translations for other languages

**Code style:**

- Python 3.12, UTF-8
- Comments in Russian or English
- Logging via `print()` (no `logging` module — intentional)
- Type annotations are optional

**Commit format:**

```
Add: description of new feature
Fix: description of bug
Refactor: what was changed
Docs: documentation changes
```

---

<a id="11-development-troubleshooting"></a>
## рџљ' 11. Development Troubleshooting

**`ModuleNotFoundError: No module named 'win32gui'`**

`pywin32` is in requirements.txt, but it's a special package — it contains DLLs that must be registered in Windows. Sometimes `pip install` installs the files but doesn't register the DLLs (especially in a venv or when conflicting with Anaconda).

**Solution:**

```bash
# Reinstall with forced DLL registration
pip install --force-reinstall pywin32==311
python venv/Scripts/pywin32_postinstall.py -install
```

**`whisper-cli.exe` does not start** → install VC++ Redistributable.

**Second instance will not start** → Windows mutex. Terminate the first one:

```bash
taskkill /f /im python.exe
```

**PyInstaller build fails:**

```bash
rmdir /s /q build dist
pyinstaller vox_bee.spec
# or simply: build.bat (cleans before building)
```

**Console encoding** — `?` symbols instead of emojis are normal in cp1251. Use Windows Terminal or `chcp 65001`.

---

## 🔗 References

| Resource | URL |
|--------|-----|
| whisper.cpp releases | https://github.com/ggml-org/whisper.cpp/releases |
| Whisper models | https://huggingface.co/ggerganov/whisper.cpp |
| Python 3.12.8 | https://www.python.org/downloads/release/python-3128/ |
| VC++ Redistributable | https://aka.ms/vs/17/release/vc_redist.x64.exe |
| Inno Setup | https://jrsoftware.org/isinfo.php |
| PyInstaller | https://pyinstaller.org |
