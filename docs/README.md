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
  <strong><img src="../src/voxbee_full.png" width="64" alt="Vox Bee" valign="middle"> Vox Bee</strong>
</h1>

<p align="center">
  <strong><a href="README_RU.md">🇷🇺 Читать на русском</a></strong>
</p>

---

**Free open-source voice input software for Windows.**  
Type with your voice anywhere — in any application, any text field.

Powered by [whisper.cpp](https://github.com/ggml-org/whisper.cpp) — fast local speech recognition.

![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey.svg)
![Version](https://img.shields.io/badge/Version-1.0.1-green.svg)
![Status: Public Beta](https://img.shields.io/badge/Status-Public%20Beta-orange.svg)

> **🚀 [Quick Start](#-quick-start)** — 3-step installation, start here.

> **⚠️ PUBLIC BETA**  
> This software is in early public beta. Development and testing were conducted on a single hardware configuration only. Behavior on other systems may vary. Please read the [Test Hardware](#️-test-hardware) section before downloading.

---

## 📖 Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| 📗 **[User Guide](#-table-of-contents)** | All users | Installation, first launch, core features, troubleshooting |
| 📙 **[Advanced command setup](VOICE_COMMANDS_AND_TEMPLATES.md)** | Advanced users | Manual editing of `commands.json`, `aliases.json`, and templates |
| 📙 **[Scripts Guide](SCRIPTS_GUIDE.md)** | Advanced users | Rules and examples for user scripts |
| 📘 **[Developer Guide](DEVELOPER.md)** | Developers | Building from source, architecture, contributing |

---

## 🚀 Quick Start

### Requirements
- Windows 10 or 11 (64-bit)
- Microphone (any)
- 500 MB disk space

### If you're new — start here

If you don't want to read the full manual yet, do only these steps:

1. Install the program
2. Download **`ggml-base.bin` model** and **CPU engine `whisper-blas-bin-x64.zip`**
3. On first launch, choose your **microphone** and set model to **Auto**
4. Close the settings window
5. Put the cursor into any text field
6. **Hold the mouse wheel** → say a phrase → **release the wheel**


### 3-Step Installation

**Step 1.** Download and run the installer: **[VoxBee_Setup_1.0.1.exe](../../releases)**

**Step 2.** Download additional files:
- **Recognition model:** [ggml-base.bin](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-base.bin) (148 MB)
- **Engine (CPU):** [whisper-blas-bin-x64.zip](https://github.com/ggml-org/whisper.cpp/releases) — find this file in the list

**Step 3.** During installation, specify the folders with downloaded files — or place them in the program folder after installation (see [detailed instructions](#-installation)).

### Done!

Press **mouse wheel** → speak → text appears in the active window.

---

- > 📖 **[Detailed installation instructions](#-installation)** — if something doesn't work
- > 🎮 **[Have an NVIDIA GPU?](#-installation)** — speed up recognition 5-30x
- > ⚠️ **[Important to read](#%EF%B8%8F-important-notice)** — software is in beta

---

## ⚠️ Important Notice

This project is a **public beta**. Please keep the following in mind:

- The software was tested on **only one computer** (specs below)
- Compatibility with other configurations **has not been verified**
- Recognition quality heavily depends on your **microphone**
- Performance depends on your **CPU, GPU, and RAM**
- Bugs, crashes, and unexpected behavior are possible
- **No warranties** — use at your own risk

If you encounter issues, please [create an issue](../../issues) and include your computer specifications.

---

## ✨ Features

- 🎙️ **Voice Input** — press a hotkey, speak, text appears in any text field
- 🖥️ **Fully Offline** — all processing happens locally, no internet required
- ⚡ **CPU and GPU** — runs faster with NVIDIA CUDA
- 🌍 **Multilingual** — supports all Whisper model languages
- 📝 **Custom Commands** — create voice commands for actions
- 🔤 **Custom Dictionary** — add your own words and corrections
- 🔗 **Aliases** — replace recognized phrases with desired text
- 📜 **Scripts** — run custom scripts by voice
- 🔧 **System Tray** — works quietly in the background
- 🆓 **100% Free** — no ads, subscriptions, or data collection

---

## 🖥️ Test Hardware

The software was developed and tested **exclusively** on the following configuration:

| Component | Specification |
|-----------|---------------|
| **CPU** | Intel Core i5-11400F |
| **GPU** | NVIDIA GeForce RTX 3080 (10 GB VRAM) |
| **RAM** | 32 GB |
| **OS** | Windows 11 (64-bit) |
| **Microphone 1** | Samsung Galaxy Buds (Bluetooth) |
| **Microphone 2** | Hollyland Lark M1 Mini Duo (USB-C, via USB-A adapter) |

### What This Means for You

- **Different CPU** — will likely work, but recognition speed will vary. Significantly slower on older/weaker CPUs.
- **Different GPU** — CUDA mode requires an NVIDIA GPU. AMD and Intel GPUs are not supported for GPU acceleration — the software will run on CPU. *(whisper.cpp supports AMD via Vulkan, but this feature is not implemented in Vox Bee)*
- **Less RAM** — in CPU mode, large models (medium, large) may not fit in memory. Use tiny/base/small models. With GPU (NVIDIA), the model loads into VRAM, not RAM — RAM requirements are reduced.
- **Different microphone** — recognition quality heavily depends on microphone quality. Among available test devices, the Hollyland Lark M1 Mini Duo lavalier mic (USB-C) showed the best results — there may be better options, but this was optimal among those tested. Bluetooth microphones (Samsung Galaxy Buds) also work fine — may add slight delay and somewhat affect recognition quality, but overall not critical, comfortable to use. Built-in laptop microphones, cheap headsets, or noisy environments may produce poor results.
- **Different OS** — only Windows 10/11 64-bit is supported. Linux and macOS are not supported.

### Approximate Model Requirements

| Model | File Size | RAM Usage | Notes |
|-------|-----------|-----------|-------|
| **tiny** | 75 MB | ~273 MB | Fastest, low quality |
| **base** | 142 MB | ~388 MB | Reasonable balance |
| **small** | 465 MB | ~852 MB | Good quality |
| **medium** | 1.5 GB | ~2.1 GB | High quality |
| **large-v3** | 2.9 GB | ~3.9 GB | Best quality, slow on CPU |
| **large-v3-turbo** | 1.6 GB | ~2.1 GB* | Faster than large-v3, high quality |

> **Sources:** File sizes from [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main), RAM usage from [official whisper.cpp documentation](https://github.com/ggml-org/whisper.cpp).
>
> \* **large-v3-turbo:** RAM usage is estimated (model not listed in official whisper.cpp table).

---

## 📋 System Requirements

- **OS:** Windows 10 / 11 (64-bit). Linux and macOS are not supported.
- **GPU acceleration:** only NVIDIA (CUDA). **Only CUDA is supported in Vox Bee.** AMD and Intel GPUs are not supported for GPU acceleration — the software will run on CPU. *(whisper.cpp supports AMD via Vulkan, but this feature is not implemented in Vox Bee)*
- **RAM:** depends on chosen model (see table above)

> **Important:** The software was tested on only one configuration (see [Test Hardware](#️-test-hardware)). Operation on other hardware is not guaranteed. If the software works or doesn't work on your PC — please report in [issues](../../issues).

---

## 🚀 Installation

### Step 1. Download the installer

Download `VoxBee_Setup_1.0.1.exe` from [Releases](../../releases).

---

### Step 2. Download files

**📥 Quick links:**

| What | Where to download |
|------|-------------------|
| **Whisper Models** | [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main) |
| **whisper.cpp** | [GitHub Releases](https://github.com/ggml-org/whisper.cpp/releases) |

**Which file to download from the releases page:**

**CPU version (required for everyone):**
- Download `whisper-blas-bin-x64.zip`

**GPU version (only if you have NVIDIA):**
- Download `whisper-cublas-XX.X.X-bin-x64.zip`
- The releases page will have several files with different CUDA version numbers (e.g.: `12.2.0`, `12.4.0`, `11.8.0`)
- **How to find your CUDA version:**
  1. Open Command Prompt (Win + R → `cmd` → Enter)
  2. Type: `nvidia-smi`
  3. In the upper right corner of the output, find the line `CUDA Version: XX.X`
  4. Download the file with the nearest compatible version (e.g., CUDA 12.6 → download `12.4.0` or newer)

> **💡 If `nvidia-smi` doesn't work** — NVIDIA drivers are not installed. First install the driver from [nvidia.com/drivers](https://www.nvidia.com/en-us/drivers/), then try again. If you don't have an NVIDIA GPU — download only the CPU version.

**What you should have before installation:**

- `VoxBee_Setup_1.0.1.exe`
- at least one model, for example `ggml-base.bin`
- CPU archive `whisper-blas-bin-x64.zip`
- if you have NVIDIA, optionally GPU archive `whisper-cublas-XX.X.X-bin-x64.zip`

**Minimum setup to get started without GPU:**

- installer `VoxBee_Setup_1.0.1.exe`
- model `ggml-base.bin`
- archive `whisper-blas-bin-x64.zip`

That is enough to run Vox Bee on CPU.

---

### Step 2.1. Check the Windows runtime dependency

`whisper-cli.exe` requires **Microsoft Visual C++ Redistributable**. In most cases you do not need to download it separately: it is already bundled into the Vox Bee `exe` installer.

- If it is already installed in Windows, the installer just continues normally.
- If it is missing, the Vox Bee installer will automatically offer to install it from the bundled file.
- If you skipped that step and later see missing DLL or C++ runtime errors, run the installer again and confirm the runtime installation.

---

### Step 3. Run the installer

1. Run `VoxBee_Setup_1.0.1.exe`
2. Click **Next**
3. Choose installation folder (default `C:\Program Files\Vox Bee`)
4. Select additional tasks:
   - ☑ **Create desktop shortcut** (optional)
   - ☑ **Start with Windows** (recommended)

---

### Step 4. Specify file folders 

A **"File Locations"** window will open:

**Three fields to specify folders:**

1. **Models folder** — specify the folder with `.bin` files (e.g., `ggml-base.bin`)
2. **CPU folder** — specify the folder with `whisper-cli.exe` and DLLs (from extracted `whisper-blas-bin-x64.zip`)
3. **GPU folder** — specify the folder with `whisper-cli.exe` and DLLs (from extracted `whisper-cublas-bin-x64.zip`)

> **💡 Auto-detect:** If you downloaded files and placed `models/`, `cpu/`, `gpu/` folders **next to the installer** — they will be detected automatically!

**Example structure next to the installer:**
```
📁 Installer folder/
├── VoxBee_Setup_1.0.1.exe    ← installer
├── models/                    ← models folder
│   └── ggml-base.bin
├── cpu/                       ← CPU version of whisper.cpp
│   ├── whisper-cli.exe
│   └── *.dll
└── gpu/                       ← GPU version (if you have NVIDIA)
    ├── whisper-cli.exe
    └── *.dll    
```

**All fields are optional!** You can leave them empty and configure later.

> **💡 If you left fields empty:**
> After installation, place files in the program folder:
> ```
> 📁 C:\Program Files\Vox Bee\
> ├── models/              ← put .bin files here
> │   └── ggml-base.bin
> └── bin/
>     ├── cpu/             ← put files from whisper-blas-bin-x64.zip here
>     │   ├── whisper-cli.exe
>     │   └── *.dll
>     └── gpu/             ← put files from whisper-cublas-bin-x64.zip here (if you have NVIDIA)
>         ├── whisper-cli.exe
>         └── *.dll
> ```

---

### Step 5. Complete installation

1. Click **Install**
2. Wait for file copying
3. ☑ **Launch Vox Bee** (leave checked)
4. Click **Finish**

The program will launch and open the **settings window** (see [First Launch](#first-launch)).

---

## 🎯 Usage

### First Launch

On first launch, the settings window will open. You need to configure:

- **Microphone** — select your microphone from the list (🔄 button refreshes the list)
- **Model** — select the downloaded model from the list, for example:
  - **Auto** — automatically selects the best available model
  - **ggml-base (148MB)** — reasonable balance of speed and quality
  - **ggml-small (466MB)** — good recognition quality
  - **ggml-medium (1536MB)** — high quality
  - **ggml-large-v3 (3100MB)** — best quality, requires lots of memory
  - **ggml-large-v3-turbo (1620MB)** — faster than large-v3, high quality
- **Auto-mode (VAD)** — enable if you want the program to automatically detect speech start (no need to hold a button)
- **GPU (CUDA)** — enable if you have an NVIDIA GPU for faster recognition
- **Record button** — click "Assign..." and press the desired key or mouse button (default — mouse wheel)
- **Short speech** — enable if you need to recognize very short phrases (1-2 words)
- **Keep model in memory** — enable for faster recognition (model stays loaded in memory)
- **Noise suppression** — enable to filter background noise

All changes apply instantly — no "Save" button required.

After configuration, click **Close** — the program will minimize to the system tray.

### 1-minute setup

If you just want the fastest working setup:

1. Choose your **microphone**
2. Set **Model** to **Auto**
3. If you don't have NVIDIA — **leave GPU off**
4. If the room is noisy — enable **Noise suppression**
5. Click **Close**
6. Open any text field
7. Hold the **mouse wheel**, speak, release

That's enough for the first real use case.

### Basic Operation

1. Press the hotkey (or mouse wheel, if configured)
2. Speak into the microphone
3. Release the key — recognized text is typed into the active window

---

## 📁 Configuration Files

Settings and service files are stored in `%APPDATA%\VoxBee\`.

Most users do not need to open this folder manually:

- Microphone, model, language, VAD, `math mode` and logging are changed via the settings window and tray menu
- Commands, aliases and dictionary should only be touched if you really want advanced manual configuration

If you need manual configuration, use:

- [Advanced command setup](VOICE_COMMANDS_AND_TEMPLATES.md)
- [Scripts Guide](SCRIPTS_GUIDE.md)

---

## 📖 User Guide

Detailed instructions for configuring and using the voice input software.

> **Installation:** If you haven't installed the program yet, see [installation instructions](#-installation).

---

## 📋 Table of Contents

- [1. First Launch](#1-first-launch)
- [2. How to Use](#2-how-to-use)
  - [2.1. Button Mode (default)](#21-button-mode-default)
  - [2.2. Auto-mode (VAD)](#22-auto-mode-vad)
- [3. Program Settings](#3-program-settings)
  - [3.1. Settings Window](#31-settings-window)
  - [3.2. System Tray Menu](#32-system-tray-menu)
- [4. Voice Commands](#4-voice-commands)
  - [4.1. Built-in Commands](#41-built-in-commands)
  - [4.2. How to Add Custom Commands](#42-how-to-add-custom-commands)
  - [4.3. How Short Commands Work](#43-how-short-commands-work)
- [5. Aliases — Fixing Recognition Errors](#5-aliases--fixing-recognition-errors)
- [6. Custom Dictionary](#6-custom-dictionary)
- [7. Voice Mouse Control](#7-voice-mouse-control)
- [8. Focus Points](#8-focus-points)
- [9. Scripts](#9-scripts)
- [10. Hotkeys](#10-hotkeys)
- [11. Where Settings Are Stored](#11-where-settings-are-stored)
- [12. Troubleshooting](#12-troubleshooting)

---

## 1. First Launch

After installing and launching Vox Bee:

1. **Tray icon** — <img src="../assets/bee_yellow.png" width="16"> a bee icon will appear in the lower right corner of the screen (near the clock). If you don't see it — click the ▲ arrow near the clock, the icon may be hidden.

2. **Settings window** — on first launch, the settings window will automatically open. Minimum required:
   - **Microphone** — select your microphone from the dropdown list
   - **Model** — select a recognition model (recommended **Auto**)

3. **Close the window** — click the "Close" button at the bottom. The program will continue running in the background, the tray icon will turn yellow (ready to work).

> **Important:** All settings apply instantly. No "Save" button needed — changes are saved automatically.

### Tray Icon States

| Icon | State | Meaning |
|------|-------|---------|
| 🐝 gray | Off | Program is running but not listening to microphone |
| 🐝 yellow | Ready | Microphone active, program waiting for your speech |
| 🐝 blue | Recording | Recording voice, speak now |

---

## 2. How to Use

Vox Bee works in two modes. Choose whichever is more convenient.

### 2.1. Button Mode (default)

You hold a button — speak — release. Text appears.

**Step by step:**

1. Open any application (browser, Word, messenger, code editor)
2. Place cursor in the text field where you want to insert text
3. **Hold** the record button (default — **mouse wheel**, middle button)
4. Icon turns blue 🔵 — **speak** into the microphone
5. **Release** the button — the program recognizes speech and inserts text

> **Tip:** Speak clearly, at normal pace. Don't rush. Make a small pause before releasing the button.

> **Important:** While you are speaking, do not switch windows or move cursor elsewhere. Text will be inserted where the input field was active at the moment recording started.

### 2.2. Auto-mode (VAD)

The program automatically detects when you start and stop speaking. No need to hold anything.

**How to enable:**
- Right-click tray icon → "Auto-mode (VAD)"
- Or in settings window: check "Auto-mode (VAD)"

**How it works:**

1. The program constantly listens to the microphone (but doesn't record)
2. When it detects your speech — starts recording (icon turns blue)
3. When you stop speaking (~0.8 sec of silence) — sends recording for recognition
4. Recognized text is inserted into the active window

> **Recommendation:** In auto-mode, enable **noise suppression** so background sounds (fan, AC, traffic) don't cause false triggers.

### 2.3. Important to know before you start

- The program works only on **Windows 10/11 64-bit**
- **GPU acceleration works only with NVIDIA GPUs**
- Without a GPU, the program will still work — but slower on the **CPU**
- Recognition quality depends heavily on your **microphone** and background noise level
- **Bluetooth microphones** are supported but may sometimes introduce additional delay
- If a command doesn't trigger, enable **"Show recognized"** and check exactly what the program heard

---

## 3. Program Settings

You can configure Vox Bee in two ways:
- **Settings window** — all parameters in one place
- **Tray menu** — quick access to main features by right-clicking the icon

### 3.1. Settings Window

**How to open:** right-click the <img src="../assets/bee_yellow.png" width="16"> icon in tray → **⚙️ Settings...**

The sections below belong specifically to the **settings window**. In the **tray menu**, the same functions are split across separate items and submenus, so section names like `Interface` or `System` do not appear there.

#### Recognition Section

| Parameter | What it does | When to enable |
|-----------|--------------|----------------|
| **Auto-mode (VAD)** | Program automatically detects speech start and end, no button holding needed | If you want to just speak without pressing anything |
| **GPU (CUDA)** | Uses NVIDIA GPU for faster recognition (5-30x faster) | If you have an NVIDIA GPU and files exist in `bin/gpu/` |
| **Microphone** | Select recording device from list. 🔄 button refreshes list (useful when connecting new microphone) | Select your primary microphone |
| **Model** | Whisper recognition model. Larger model = more accurate but slower | **Auto** — automatically selects best from downloaded models |
| **Short speech** | Allows recognizing very short phrases of 1-2 words ("yes", "no", "okay", "stop"). [More details](#43-how-short-commands-work) | If you use short voice commands |
| **Keep model in memory** | Model stays loaded between recognitions — faster response but uses memory | Enable if you have enough RAM/VRAM |
| **Noise suppression** | Filters background noise before recognition | Enable in noisy environment or in auto-mode |

#### Which Model to Choose

| Model | Size | Quality | Speed | For whom |
|--------|--------|----------|----------|----------|
| **ggml-tiny** | 75 MB | Basic | Very fast | Weak PC, quick short phrases |
| **ggml-base** | 148 MB | Normal | Fast | Regular PC without GPU |
| **ggml-small** | 465 MB | Good | Medium | PC with 8+ GB RAM |
| **ggml-medium** | 1.5 GB | High | Slow on CPU | PC with GPU or powerful CPU |
| **ggml-large-v3** | 2.9 GB | Best | Slow | Only with GPU |
| **ggml-large-v3-turbo** | 1.6 GB | High | Faster than large-v3 | PC with GPU |

> **Tip:** Start with **Auto** — the program will automatically select the best from downloaded models. If quality is unsatisfactory — download a larger model.

#### Text Fixing Section

| Parameter | What it does |
|----------|------------|
| **Fix text (all)** | Master switch. Disables all corrections at once |
| **Remove hallucinations** | Whisper sometimes outputs repetitive nonsense text during silence. This filter removes such garbage |
| **Term dictionary (built-in)** | Fixes common errors: technical terms, abbreviations |
| **User dictionary** | Your own word replacements ([more details](#6-custom-dictionary)) |
| **Remove duplicates** | Removes accidentally duplicated words and phrases |
| **Punctuation and capitalization** | Adds capital letters after periods, corrects punctuation |

#### Commands


| Parameter | What it does | Where to find it |
|----------|------------|------------------|
| **Recognize commands** | Enables voice commands ([more details](#4-voice-commands)). If disabled, short words are inserted as normal text instead of being executed as commands | In tray: **🎯 Commands** submenu.|
| **Reload commands and aliases** | Reloads `commands.json` and `aliases.json` without restarting the program | In tray: **🎯 Commands** → **🔄 Reload commands and aliases**. In settings window: a separate button below the commands toggle |

#### Interface Section

| Parameter | What it does |
|----------|------------|
| **Show recognized text** | After each recognition, shows a popup with the result. Useful for debugging — shows what exactly the program heard |
| **Mouse step (px)** | Distance in pixels the cursor moves with "right" / "left" / "up" / "down" commands |
| **Record button** | Which mouse button or key starts recording. Click "Assign..." and press the desired button |

#### System Section

| Parameter | What it does |
|----------|------------|
| **Write log** | Saves all program messages to a text file. Useful for diagnosing problems |
| **Log folder** | Where to save log files. Default — `logs/` in program folder |
| **Start with Windows** | Program will automatically start when logging into Windows |

### 3.2. System Tray Menu

**How to open:** right-click the 🐝 icon in tray (area near the clock in lower right corner of screen).

| Menu item | What it does |
|------------|------------|
| 🎤 **Enable** / ⏹ **Disable** | Turn microphone on or off. Also toggleable by **clicking** the icon |
| **Auto-mode (VAD)** | Toggle between button mode and auto-mode |
| 🎯 **Record button** | Submenu: assign or reset record button |
| 🎤 **Microphone** | Submenu: microphone selection, refresh list |
| 🧠 **Model** | Submenu: recognition model selection |
| **GPU (CUDA)** | Enable/disable GPU acceleration |
| **Short speech** | Recognition of short phrases (1-2 words) |
| **Model in memory** | Keep model loaded in memory for fast response |
| **Noise suppression** | Background noise filtering |
| **Math mode** | Spoken numbers and operations are converted to digits and symbols |
| **Show recognized** | Popup window with recognition result |
| **Show grid** | Screen overlay grid for voice mouse navigation |
| ✏️ **Text correction** | Submenu: text processing settings, dictionary |
| 🎯 **Commands** | Submenu: voice commands, reload, settings folder |
| 🖱️ **Mouse step** | Submenu: cursor movement distance selection (50-500 px) |
| 🚀 **Scripts** | Submenu: script manager, scripts folder |
| 📍 **Focus points** | Submenu: saved window positions |
| 📝 **Logging** | Submenu: log writing, folder selection |
| 🌐 **Language** | Submenu: switch the interface language |
| ⚙️ **Settings...** | Open full settings window |
| ℹ️ **About** | Open the program information window |
| **Autostart** | Start program when Windows starts |
| ❌ **Exit** | Close program completely |

---

### Math Mode

`Math mode` is meant for formulas, numbers and short math expressions.

How it works:

- numbers and operations are converted to digits and symbols
- `equals` finishes the expression and may calculate the result
- digit sequences can be dictated directly: `one two three` -> `123`
- if you start speaking a normal sentence while math mode is enabled, it is still inserted as regular text

Examples:

- `two plus two` -> `2+2`
- `equals` -> `2 + 2 = 4`
- `one two three four` -> `1234`
- `now let's write some normal text` -> inserted as regular phrase, not as formula

If you are not dictating formulas, keep this mode off.

---

## 4. Voice Commands

Vox Bee can not only type text but also perform actions via voice commands: press keys, move mouse, insert text templates.

**How it works:** the program first checks if the spoken phrase is a command. If yes — performs the action. If no — inserts the text as regular voice input.

If `Recognize commands` is enabled, a short phrase that matches a command or alias will be executed as a command instead of being inserted as text.

### 4.1. Built-in Commands

#### ⌨️ Text Editing

| Say | What happens | Keyboard equivalent |
|---------|----------------|----------------|
| "save" | Save file | Ctrl+S |
| "undo" | Undo last action | Ctrl+Z |
| "redo" | Redo undone action | Ctrl+Y |
| "copy" | Copy selection | Ctrl+C |
| "paste" | Paste from clipboard | Ctrl+V |
| "cut" | Cut selection | Ctrl+X |
| "delete" | Delete character before cursor | Backspace |
| "delete line" | Delete current line (app-dependent) | Ctrl+U |
| "clear" | Clear (app-dependent) | Ctrl+L |
| "select all" | Select all text | Ctrl+A |
| "enter" / "submit" / "okay" | Press Enter | Enter |
| "tab" | Tabulation | Tab |

#### ✂️ Text Selection

| Say | What happens |
|---------|----------------|
| "select to start" | Select from cursor to line start |
| "select to end" / "select line" | Select from cursor to line end |
| "select left" / "word left" | Select one word to the left |
| "select right" / "word right" | Select one word to the right |
| "more" | Expand current selection |
| "less" | Shrink current selection |

#### 📜 Page Scrolling

| Say | What happens |
|---------|----------------|
| "scroll up" | Scroll page up |
| "scroll down" | Scroll page down |
| "to the top" / "page start" | Go to page start |
| "to the bottom" / "page end" | Go to page end |

#### 🖱️ Mouse Control

| Say | What happens |
|---------|----------------|
| "right" | Move cursor right one step (150 px default) |
| "left" | Move cursor left |
| "up" | Move cursor up |
| "down" | Move cursor down |
| "right 5" | Move cursor right 50 px (number × 10). Works for all directions |
| "move right" | Start smooth continuous movement right |
| "move left" | Start smooth continuous movement left |
| "move up" | Start smooth continuous movement up |
| "move down" | Start smooth continuous movement down |
| "stop" | Stop continuous movement |
| "click" | Left mouse click |
| "right click" | Right mouse click |
| "double click" / "open" | Double click (open file/folder) |
| "monitor 1" / "first monitor" | Move cursor to 1st monitor |
| "monitor 2" / "second monitor" | Move cursor to 2nd monitor |
| "grid 15" | Move cursor to grid cell 15 |
| "refine 3" | Refine position to subsector 3 |

#### 📍 Focus

| Say | What happens |
|---------|----------------|
| "focus 1" / "switch 1" | Switch to saved focus point 1 |
| "remember point 1" | Save current position as focus point 1 |

#### 📋 Text Insertion

| Say | What's inserted |
|---------|---------------|
| "git status" | `git status` |
| "git push" | `git push` |
| "run program" | `source venv/Scripts/activate && python src/main.py` |

> These are examples. You can add your own text insertion commands (see below).

### 4.2. How to Add Custom Commands

For most users, built-in commands are enough.

If you need more, there are three options:

- configure your own voice commands manually
- fix recognition via aliases and dictionary

But this is already **advanced customization**, not basic usage.

Detailed manual configuration is moved to a separate document:

📖 [Advanced command setup](VOICE_COMMANDS_AND_TEMPLATES.md)


### 4.3. How Short Commands Work

Recognizing short phrases ("save", "stop", "grid 15") is technically challenging. Whisper is optimized for long speech and with short recordings may:

- Add filler words: "um save well" instead of "save"
- Distort words: "sweat" instead of "set", "clip" instead of "click"
- Misrecognize numbers: "won" instead of "one"

The program uses several layers of protection:

**1. Model prompt**

For short recordings (<6 seconds), the program sends Whisper a list of all registered commands and numbers. This hints to the model what words to expect and significantly improves accuracy.

**2. Filler word removal**

Words like "um", "uh", "well", "like", "just", "so" and others are automatically removed from recognized text before command search. "Um well save" → "save" → command found.

**3. Aliases**

If Whisper consistently mishears a word, use aliases. Details and format are in:

📖 [Advanced command setup](VOICE_COMMANDS_AND_TEMPLATES.md)

**4. Fuzzy matching**

If no exact match exists, the program checks similar words (1 letter difference). "sav" → finds "save". Only works for 1-2 word phrases.

**5. Robust number recognition**

Numbers are recognized in any form:

- **Digits:** "grid 15"
- **Words:** "grid fifteen"
- **With errors:** "grid fiveteen" → 15
- **Compound:** "right twenty five" → 25

#### What to do if a command doesn't trigger

- **Enable "Show recognized"** (tray → right-click) — you'll see what exactly the program hears
- **If a word is distorted** — add an alias using the advanced guide
- **If command is too short** (1-2 letters) — use a longer trigger
- **Enable "Short speech"** in settings — this allows VAD detector to accept very short recordings

> **Tip:** Long phrases (more than 5 words) are never considered commands — the program immediately inserts them as text. This protects against accidental command triggers during regular dictation.
>
> **Important:** Short phrases work the other way around. If you say a short word or short phrase that matches a command or one of its aliases, the program treats it as a command and does not insert it as normal text. For example, a word like `save`, `stop`, or another short command will be executed instead of typed.
>
> **If short words should be inserted as normal text instead:** disable `Recognize commands` in the settings window or in the tray menu under `🎯 Commands`.


### 5. Aliases — Fixing Recognition Errors

Aliases are needed when Whisper consistently confuses a short word or command.

Examples:

- instead of `grid` it hears `great`
- instead of `click` it hears `clip`

What to do:

1. Enable `Show recognized`
2. See what the app actually hears
3. If the mistake repeats constantly, add an alias

Full manual instructions:

📖 [Advanced command setup](VOICE_COMMANDS_AND_TEMPLATES.md)

Important:

- aliases are best used for commands and short triggers
- for regular words in text, use the user dictionary instead

### 6. Custom Dictionary

The dictionary allows automatic word replacement in recognized text. Useful for:

- **Names:** john smith → John Smith
- **Brands:** google → Google, telegram → Telegram
- **Terms:** python → Python, linux → Linux
- **Slang and abbreviations:** btw → by the way

#### Where It's Stored

File `user_dictionary.json` in folder `%APPDATA%\VoxBee\`.

#### How to Add a Word

The user dictionary is edited manually and is needed for finer tuning.

If you really want to configure it manually:

1. Open the settings folder
2. Find `user_dictionary.json`
3. After changes, reload the dictionary via tray

But usually it's better to first check:

- if the correct microphone is selected
- if the selected model is suitable
- if `Show recognized` is enabled

### 7. Voice Mouse Control

Vox Bee allows full voice control of the mouse cursor. Convenient for people with disabilities or when working at a distance from the computer.

#### If you are using mouse control for the first time

Start with the simplest scenario:

1. Say **"right"**, **"left"**, **"up"** or **"down"** — the cursor will move one step
2. If you need more precision — say, for example, **"right 3"** or **"up 2"**
3. When the cursor is over the desired spot, say **"click"**

For quick jumps across the screen, use the **grid**:

1. Enable **"Show Grid"** in the tray
2. Say **"grid 15"** — the cursor will jump to the corresponding cell
3. For fine-tuning say **"refine 3"**
4. Then say **"click"**

If you need to move the cursor smoothly without jerking, use continuous movement: **"move right"** → **"stop"**.

#### Single Step Movement

Commands "right", "left", "up", "down" move cursor a fixed distance.

Step size is configurable: tray → right-click → Mouse step → select value (50-500 px).


#### Precise Movement with Number

You can add a number to a direction command — it sets distance in units, each unit = 10 pixels.

| You say | Cursor shift |
|-------------|---------------|
| "right" (no number) | 150 px ("Mouse step" value) |
| "right 1" | 10 px — fine adjustment |
| "right 5" | 50 px — small shift |
| "right 10" | 100 px — medium shift |
| "right 15" | 150 px |
| "right 50" | 500 px — large shift |

Works for all directions: "right", "left", "up", "down".

Numbers can be spoken as words: "right ten" = "right 10" = shift 100 px.

> **Tip:** For rough positioning use grid ("grid 15"), then fine-tune: "right 3", "up 2".

#### Continuous Movement

Say "move right" — cursor will start smoothly moving right. Say "stop" — cursor stops.

The program automatically compensates for reaction time: cursor returns slightly to where you said "stop".

#### Grid Navigation

Grid is the fastest way to move cursor to the desired screen location.

- Say "grid 15" — cursor moves to cell 15 (screen divided into 24 cells, 6 columns × 4 rows)
- For refinement say "refine 3" — selected cell divides into 9 subsectors, cursor shifts to subsector 3
- Visual grid: tray → right-click → "Show grid" — semi-transparent grid with cell numbers appears on screen. Close: repeat in tray.

#### Clicks

| Say | Action |
|---------|----------|
| "click" | Regular left click |
| "right click" | Context menu |
| "double click" / "open" | Open file / folder |

#### Practical Example: Opening a file by voice

1. Say **"grid 12"** or move the cursor using **"right / left / up / down"** commands
2. If necessary, refine the position: **"refine 5"** or **"right 2"**
3. When the cursor is over the file or button — say **"double click"** or **"open"**

#### If the mouse moves too crudely or too precisely

Open: **Tray → Mouse step** and choose a suitable value:

- **50–100 px** — for precision work
- **150 px** — universal default mode
- **300–500 px** — for fast movement on a large screen

### 8. Focus Points

Focus points are saved cursor positions in different windows. Allow instant voice switching between applications.

**Usage example:** you work with browser and messenger. Save point 1 in browser and point 2 in messenger. Now command "focus 1" switches you to browser, and "focus 2" — to messenger.

#### How to Save a Point

**Method 1 — keyboard:**

1. Open desired window and place cursor in desired location
2. Press Alt + Shift + digit (1-9)

**Method 2 — voice:**

1. Open desired window
2. Say "remember point 1"

#### How to Switch to a Point

Say "focus 1" — cursor moves to saved position, and window comes to foreground.

#### Voice Names

To use words instead of numbers:

1. Tray → right-click → Focus points
2. Select point → "🏷️ Voice names..."
3. Enter names separated by comma, e.g.: chat, telegram
4. Click "Save"

Now you can say "focus chat" or "focus telegram" instead of number.

#### Managing Points

Tray → right-click → Focus points:

- **Go to** — switch to point
- **Voice names** — set/change voice names
- **Delete** — delete one point
- **Reset all points** — delete all saved points

### 9. Scripts

Vox Bee can run scripts and programs by voice command.

#### Script Manager

For multiple scripts with different voice triggers:

1. Tray → right-click → Scripts → "⚙️ Manage scripts..."
2. In manager you can add scripts with custom triggers, enable/disable them
3. Tray → Scripts → "📂 Scripts folder" — open scripts folder

### How to Write Scripts

Scripts for Vox Bee have specifics: they run without console window, with 30-second timeout, and require UTF-8 encoding.

📖 **Full guide:** [Script Guide](SCRIPTS_GUIDE.md) — template, rules and examples.

### 10. Hotkeys

| Keys | Action |
|---------|----------|
| Mouse wheel (hold and release) | Start and stop voice recording (can assign different button) |
| Ctrl + Alt + V | Re-insert last dictated text (works even when microphone is off) |
| Alt + Shift + 1..9 | Save current cursor position as focus point |
| Click on tray icon | Quick microphone on/off toggle |

#### Assigning Record Button

Record button can be changed to any mouse button or keyboard key:

1. Tray → right-click → Record button → "Assign button..."
2. In opened window press desired mouse button or key
3. Click "Save"

You can use combinations with modifiers: Ctrl + mouse button, Alt + key, etc.

To return to wheel: "Reset to wheel".

### 11. Where Settings Are Stored

All configuration files are in folder:

```text
%APPDATA%\VoxBee\
```

How to open this folder:

Press Win + R, type `%APPDATA%\VoxBee` and press Enter
Or: tray → right-click → Commands → "Settings folder"

Most users only need to know this:

- all user data is stored in `%APPDATA%\VoxBee\`
- settings are changed through the tray menu and settings window
- you only need to open this folder for advanced manual customization

If you do want manual setup for commands, aliases, or scripts:

- [Advanced command setup](VOICE_COMMANDS_AND_TEMPLATES.md)
- [Scripts Guide](SCRIPTS_GUIDE.md)

### 12. Troubleshooting

#### Program Won't Start

| Cause | Solution |
|---------|---------|
| Program already running | Vox Bee allows only one instance. Check tray icon (may be hidden behind ▲) |
| No models | Download a model and place in `models/` folder — [instructions](#-installation) |
| No whisper-cli.exe | Download whisper.cpp and place in `bin/cpu/` — [instructions](#-installation) |
| Visual C++ error | Run the Vox Bee installer again and confirm installation of the bundled Microsoft Visual C++ Redistributable |

#### Microphone Not Detected

| Solution | How to do |
|---------|-------------|
| Refresh list | Tray → Microphone → 🔄 Refresh list |
| Check in Windows | Windows → System → Sound → Input → ensure microphone is enabled |
| Bluetooth microphone | Ensure device is connected and working. After connecting click "Refresh list" |

#### Poor Recognition Quality

| Problem | Solution |
|----------|---------|
| Recognizes with errors | Try a larger model: small → medium → large |
| Background noise interferes | Enable noise suppression in settings |
| Quiet microphone | Speak closer to microphone or increase volume in Windows settings |
| Built-in laptop microphone | Use external microphone or headset — quality will be significantly better |



#### Whisper Translates Speech Instead of transcribing

If the recognition language does not match the language you are speaking, Whisper may start translating speech instead of transcribing it normally.

**What to check:**

- open **Settings**
- ensure the correct recognition language is selected
- for English speech, English language should be selected

#### GPU Acceleration Not Working

| Problem | Solution |
|----------|---------|
| You have AMD or Intel GPU | GPU acceleration only works with NVIDIA. Use CPU mode |
| No files in bin/gpu/ | Download whisper-cublas-bin-x64.zip from whisper.cpp releases and extract to `bin/gpu/` |
| Old NVIDIA drivers | Update drivers: nvidia.com/drivers. Need version 525 or newer |
| CUDA errors on startup | Ensure driver is compatible with CUDA 12.x |

#### Text Inserted in Wrong Window

| Problem | Solution |
|----------|---------|
| Window changed during recording | In button mode, window is remembered when button is pressed. Don't switch windows while speaking |
| In VAD mode | Window is remembered when speech starts. Don't switch windows while speaking |
| Cursor not in text field | Before recording, place cursor in text field where you want to insert text |

#### Voice Command Not Triggering

| Problem | Solution |
|----------|---------|
| Commands off | Check: tray → Commands → should be checked "Recognize commands" |
| Short word is not inserted as text | Check whether it matches a command or alias. If you want normal text insertion, disable "Recognize commands" |
| Whisper hears word differently | Enable "Show recognized" — you'll see what the app actually heard. If the mistake repeats, add an alias using the advanced guide |
| Commands not reloaded | After manual command changes: tray → Commands → Reload |
| Error in a manual config file | Check syntax or restore your backup. See the advanced guide for details |

#### Whisper "Hallucinating" (Garbage Text on Silence)

| Solution | How to do |
|---------|-------------|
| Enable hallucination filter | Tray → Text correction → "Remove hallucinations" |
| Enable noise suppression | Tray → enable "Noise suppression" |
| Disable "Short speech" | With short speech enabled, program is more sensitive to short sounds |

#### Slow Recognition

| Solution | Expected effect |
|---------|------------------|
| Choose smaller model (tiny or base) | Recognition in 1-3 seconds on CPU |
| Enable GPU | 5-30x speedup |
| Enable "Keep model in memory" | Removes model loading delay (2-10 sec) |

---

## 🤝 Contributing

All contributions are welcome! Testing on different hardware is especially needed.

If you tried the program, please report:

- Your computer specs (CPU, GPU, RAM)
- Which microphone you use
- Which model you used
- Recognition quality (good / acceptable / poor)
- Any problems or crashes

**👨‍💻 Want to contribute code?** Detailed instructions in **[Developer Guide](DEVELOPER.md)**.

---

## 👤 Author

**Boris Shkylnikov**  
aka *Secret Agent 007* 🕵️
Creator and developer of VoxBee.

---

## 📄 License

This program is free software: you can redistribute and/or modify it under the terms of the GNU General Public License v3.0.

Full license text is available in the repository root file [LICENSE](../LICENSE).

Copyright holder of the project: **Boris Shkylnikov**  
aka *Secret Agent 007* 🕵️.

- ✅ Free to use, modify, and distribute
- ✅ Source code must remain open
- ✅ Modifications must also be under GPLv3
- ❌ Cannot be made proprietary or sold as closed-source software

---

## 🙏 Acknowledgments

- **[Georgi Gerganov](https://github.com/ggerganov)** — for [whisper.cpp](https://github.com/ggml-org/whisper.cpp) and [optimized models](https://huggingface.co/ggerganov/whisper.cpp). His C/C++ implementation made Whisper fast and easy to use
- **[OpenAI](https://openai.com)** — original [Whisper](https://github.com/openai/whisper) speech recognition model
- **[PyInstaller](https://pyinstaller.org)** — packaging Python into EXE
- **[Inno Setup](https://jrsoftware.org/isinfo.php)** — creating Windows installers

---

*Made with ❤️ for everyone who prefers speaking to typing.*
