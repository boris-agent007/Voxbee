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
  <strong><img src="../src/voxbee_full.png" width="64" alt="Vox Bee" valign="middle"> Vox Bee Scripts Guide</strong>
</h1>

<p align="center">
  <strong><a href="SCRIPTS_GUIDE.md">🇷🇺 Читать на русском</a></strong>
</p>

---

This guide describes how Vox Bee currently runs user scripts, what the security restrictions are, and how to write examples that actually match the app behavior.

It only applies to user scripts added through the script manager. It does not describe the project's internal Python modules.

## ⚠️ What matters first

- This guide is about scripts added through `Tray -> Scripts -> Script manager`.
- Vox Bee only runs supported file types: `.py`, `.bat`, `.cmd`, `.ps1`, `.exe`, `.sh`.
- Execution is only allowed from trusted folders:
  - the built-in project `scripts/` folder
  - the writable user-data `scripts/` folder created by the app
- If you add a file from another directory through the script manager, Vox Bee copies it into the trusted `scripts/` folder first, then saves and runs it.
- Unsupported file types are no longer opened via the OS shell.
- PowerShell scripts are no longer launched with `ExecutionPolicy Bypass`.

Important: after you add an external file, Vox Bee does not run the original file from that arbitrary folder. It runs the saved copy inside the trusted `scripts/` folder.

## ▶️ How Vox Bee runs scripts

Actual runtime behavior:

| Parameter | Behavior |
|---|---|
| `.py` interpreter | the same Python used by Vox Bee |
| Working directory | the script's own folder |
| Console window | none |
| Output | `stdout` and `stderr` are written into the Vox Bee log |
| Output encoding | Vox Bee reads output as UTF-8 |
| Wait timeout | 30 seconds |
| After timeout | Vox Bee stops waiting, but the child process may continue |
| Recognition blocking | no; the launch runs in a separate thread |

Exact launch commands:

| Format | Command |
|---|---|
| `.py` | `python script.py` or `VoxBee.exe --run-script script.py` in packaged builds |
| `.bat` | `cmd /c script.bat` |
| `.cmd` | `cmd /c script.cmd` |
| `.ps1` | `powershell -NoProfile -NonInteractive -File script.ps1` |
| `.exe` | direct execution |
| `.sh` | `bash script.sh` |

Unsupported extensions fail with an error instead of being opened by file association.

## 🛡️ Guarantees and limits

Vox Bee only guarantees this runtime contract:

- it launches a supported script in the allowed way;
- it writes `stdout` and `stderr` into the Vox Bee log;
- it waits for completion for up to 30 seconds;
- it does not block recognition while the launch is in progress.

The limits are just as important:

- after the timeout, Vox Bee stops waiting, but the child process may continue running;
- Vox Bee does not turn an interactive script into a proper UI flow;
- Vox Bee does not bypass PowerShell system policy;
- Vox Bee does not resolve arbitrary file types through the Windows shell.

## 🔒 Trusted folders and security

This is one of the most important current rules.

- A script cannot be launched directly from an arbitrary folder.
- If the selected path is already inside a trusted folder, it is stored as is.
- If you pick an external file through the script manager, Vox Bee copies it into the user `scripts/` folder.
- If a file with the same name already exists there, a suffix is added, for example `tool_1.py`.
- If the file does not exist, the UI shows a validation error before saving.

Practical implications:

- keep real working scripts in `scripts/` if you want predictable behavior;
- if you edit the original external file later, Vox Bee will still run the copied trusted version;
- after changing the external original, re-add it or update the trusted copy manually.

## 📖 What this guide covers

This guide describes scripts added through the tray script manager.

## 🐍 Recommended Python template

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Short description of what the script does.
"""

import io
import sys

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main():
    print("[MY_SCRIPT] Start")

    try:
        # your code
        print("[MY_SCRIPT] Done")
        return 0
    except Exception as e:
        print(f"[MY_SCRIPT] ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

## ✍️ What to keep in Python scripts

Recommended minimum:

- UTF-8 wrapper for `stdout/stderr` on Windows;
- `main()` with explicit `return 0/1`;
- `if __name__ == "__main__": sys.exit(main())`;
- readable log prefixes like `[OPEN_APP]` or `[BACKUP]`;
- explicit error handling.

Why:

- the Vox Bee log stays readable;
- exit codes are visible in logs;
- the script behaves the same when run manually and through Vox Bee.

## 🚫 What to avoid

- Do not use `input()`: there is no normal interactive console.
- Do not design the integration as an interactive console flow: `input()` and waiting for console input are the wrong model here.
- Do not assume the working directory is the Vox Bee root.
- Do not assume arbitrary file types will be opened by Windows: that behavior is gone.
- Do not rely on PowerShell execution policy being bypassed: if the system blocks `.ps1`, that is not a Vox Bee bug.
- Do not keep long blocking work inline if it can be moved to `subprocess.Popen()` or another non-blocking launch pattern.

## 📁 Paths and files

The script starts with `cwd` set to the script's own folder. Even so, explicit paths are better:

```python
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
```

## 📦 Dependencies

Python scripts run in the same Python environment as Vox Bee.

That means:

- the Python standard library is available;
- third-party packages must actually exist in the exact Python environment where Vox Bee runs;
- if an example needs `pywin32`, that should be stated clearly.

If a dependency is missing, fail with a readable message:

```python
try:
    import win32gui
except ImportError:
    print("[MY_SCRIPT] ERROR: pywin32 is required")
    sys.exit(1)
```

## 🧪 Examples in the `scripts/` folder

The repository currently includes these examples:

- `scripts/open_notepad.py`
  - working minimal example that starts `notepad.exe`;
  - a good starting template.
- `scripts/open_app.py`
  - application-launch dictionary example;
  - useful as a base for your own app mappings;
  - fixed to handle wildcard paths like `app-*`.
- `scripts/create_folder.py`
  - Explorer automation example using `pywin32`;
  - Windows-only and requires `pywin32`;
  - normalized to use proper `return` and `sys.exit`.
- `scripts/close_window.py`
  - window automation example for the window under the mouse cursor;
  - also Windows-only and depends on `pywin32`;
  - description cleaned up so it matches what it actually does.
- `scripts/test_echo.bat`
  - minimal `.bat` example;
  - now explicitly switches to UTF-8 with `chcp 65001`.

## 📄 Example `.bat`

```bat
@echo off
chcp 65001 >nul
echo [TEST] Script started
mkdir "%~dp0output" 2>nul
echo done > "%~dp0output\result.txt"
exit /b 0
```

## 📄 Example `.ps1`

```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Write-Output "[TEST] PowerShell script started"
exit 0
```

Important:

- PowerShell is launched as `-NoProfile -NonInteractive -File`;
- if your system execution policy blocks `.ps1`, Vox Bee does not bypass it.

## 🐞 Debugging

1. Run the script manually first.

```text
cd C:\path\to\script
python my_script.py
```

2. Then add it through the script manager.

3. Enable logging in the tray and inspect lines like:

```text
[SCRIPTS] 🚀 Запуск: my_script.py
[SCRIPTS]    Команда: ...
[SCRIPTS]    Рабочая папка: ...
[SCRIPTS]    📤 ...
[SCRIPTS]    ⚠️ ...
[SCRIPTS] ✅ Завершён: my_script.py (код: 0)
```

4. If the file was added from outside the trusted folders, debug the copied trusted version, not the original source file.

The normal debugging order is:

- manual run;
- run through Vox Bee;
- inspect the Vox Bee log;
- inspect the trusted copy in `scripts/` if the source file was added from outside.

## рџљ' Common problems

| Problem | Cause | What to do |
|---|---|---|
| `File not found` | saved path is wrong or file was removed | verify the stored path in the manager |
| `Execution outside trusted folders is forbidden` | file lives outside trusted directories | add it through the manager so it is copied into `scripts/` |
| `Unsupported script type` | extension is not on the allow-list | use `.py`, `.bat`, `.cmd`, `.ps1`, `.exe`, or `.sh` |
| `UnicodeEncodeError` or broken text | script is not writing UTF-8 safely | add the UTF-8 wrapper |
| `ModuleNotFoundError` | dependency is missing in the Vox Bee environment | install it there or rewrite the script |
| changes to the external original do nothing | Vox Bee runs the trusted copy | update the file inside `scripts/` or re-add it |
| `.ps1` does not start | PowerShell policy blocks it | sign the script, change system policy, or use another format |
| script appears stuck | `input()` or a long blocking call is used | remove interactivity, use `Popen()` for long-lived processes |

## ✅ Checklist before adding a script

- the file is in a trusted folder or will be copied there through the manager;
- the extension is supported;
- Python scripts are saved as UTF-8;
- `stdout/stderr` are wrapped for UTF-8 on Windows;
- there is a `main()` and `sys.exit(main())`;
- errors are logged clearly;
- there is no `input()` or other console interaction;
- long-running tasks are launched non-blocking when needed;
- the script was tested manually before connecting it to Vox Bee.
