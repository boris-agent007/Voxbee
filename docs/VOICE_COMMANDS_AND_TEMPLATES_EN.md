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
  <strong><img src="../src/voxbee_full.png" width="64" alt="Vox Bee" valign="middle"> Vox Bee: advanced command and alias setup</strong>
</h1>

<p align="center">
  <strong><a href="VOICE_COMMANDS_AND_TEMPLATES.md">🇷🇺 Читать на русском</a></strong>
</p>

---

This document is not needed for most users.

If you only want to use the app, start with [README.md](README.md).  
Use this guide only if you want to manually edit commands, aliases, or command templates.

---

## рџ'Ґ Who this is for

- **Regular users**: usually do not need this document
- **Advanced users**: useful if you want to edit commands and aliases manually
- **Developers**: useful for understanding templates and first-run behavior

---

## ⚙️ What is configured here

Vox Bee uses three main runtime files:

- `commands.json` — voice commands
- `aliases.json` — corrections for recurring recognition mistakes
- `scripts.json` — script trigger bindings

In the installed version they are stored in:

```text
%APPDATA%\VoxBee\
```

Open that folder from the tray:

```text
tray -> right click -> Commands -> Settings folder
```

---

## ✋ When not to edit files manually

Do not edit JSON files if you only need to:

- choose a microphone
- enable or disable commands
- enable VAD
- enable `math mode`
- enable logging
- change the interface language

Those actions are already available through the tray menu and settings window.

---

## 🧩 `commands.json`

### What it is

This file stores spoken phrases that trigger actions.

If the recognized phrase matches a trigger, Vox Bee executes the command.  
If it does not match, the phrase is treated as regular dictation.

### Supported formats

#### Legacy format

```json
"save_file": {
  "triggers": ["save", "save file"],
  "type": "hotkey",
  "value": "ctrl+s"
}
```

#### Multilingual format

```json
"save_file": {
  "triggers": {
    "ru": ["сохрани", "сохранить"],
    "en": ["save file"],
    "common": ["save"]
  },
  "type": "hotkey",
  "value": "ctrl+s"
}
```

### Field meaning

- `triggers` — phrases that activate the command
- `type` — action type
- `value` — action parameter

### Common action types

| `type` | What it does |
|--------|---------------|
| `paste` | inserts text |
| `hotkey` | presses a key combination |
| `mouse_click` | performs a mouse click |
| `mouse_move` | moves the cursor one step |
| `mouse_continuous` | starts continuous cursor movement |
| `mouse_stop` | stops movement |
| `mouse_scroll` | scrolls the page |
| `grid` | moves by screen grid |
| `grid_zoom` | refines grid position |
| `focus_switch` | jumps to a focus point |
| `focus_save` | saves a focus point |

---

## 🔁 `aliases.json`

### What it is

This file stores replacements for cases where Whisper consistently hears a word incorrectly.

Example:

```json
{
  "great": "grid",
  "clip": "click"
}
```

Multilingual format is also supported:

```json
{
  "ru": {
    "светка": "сетка"
  },
  "en": {
    "copi": "copy"
  }
}
```

### When to use aliases

Use `aliases.json` when the problem affects a command trigger or another short control phrase.

If you want to fix a normal dictated word in final text, use the user dictionary instead.

---

## 📄 Where templates come from

On first launch, Vox Bee creates user files from built-in templates:

- `src/commands_template.json`
- `src/aliases_template.json`

This matters for developers:

- templates update the starting configuration for new installations
- existing user files must not be overwritten

---

## 🛡️ Safe workflow for manual editing

1. Make a backup copy of the file.
2. Open the JSON file in an editor with syntax highlighting.
3. Make the change.
4. Save the file.
5. In the tray, choose `Reload commands and aliases`.

If commands stop working after that, the most likely cause is invalid JSON syntax.

---

## ⚠️ Common mistakes

| Mistake | Result |
|---------|--------|
| missing comma | file will not load |
| single quotes instead of double quotes | file will not load |
| extra comma before `}` | file will not load |
| file changed but not reloaded | app keeps using the previous version |

---

## 🧠 Developer-related notes

If you need implementation details for loading paths, templates, runtime config, or builds, see:

- [DEVELOPER.md](DEVELOPER.md)
- [DEVELOPER_RU.md](DEVELOPER_RU.md)
