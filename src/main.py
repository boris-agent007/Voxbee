#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
voise_input_mouse is a local voice input application.
voise_input_mouse — локальный голосовой ввод.

Supports CPU/GPU modes and microphone/model selection.
Поддержка CPU/GPU, выбор микрофона и модели.
"""
import os
import sys
import time
import threading
import atexit
import signal
import ctypes
from pathlib import Path


# === Intercept --run-script: execute a .py script and exit ===
# === Перехват --run-script: выполнить .py скрипт и выйти ===
# MUST run before any heavy imports (numpy, win32, tray, recorder, ...).
# ОБЯЗАТЕЛЬНО до любых тяжёлых импортов (numpy, win32, tray, recorder...)
# This lets Vox Bee.exe act as a Python interpreter for scripts.
# Это позволяет Vox Bee.exe работать как Python-интерпретатор для скриптов
if len(sys.argv) >= 3 and sys.argv[1] == "--run-script":
    import runpy
    _script_path = sys.argv[2]
    # The script sees itself as a normal python script.py invocation.
    # Скрипт видит себя как обычный python script.py
    sys.argv = [_script_path] + sys.argv[3:]
    try:
        runpy.run_path(_script_path, run_name="__main__")
    except SystemExit as e:
        sys.exit(e.code if e.code is not None else 0)
    except Exception as e:
        print(f"[SCRIPT ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)


# === Single instance protection ===
# === Single Instance — защита от повторного запуска ===

_mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\VoxBee_SingleInstance")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    ctypes.windll.kernel32.CloseHandle(_mutex_handle)
    print("[VOXBEE] Уже запущен — выход")    
    sys.exit(0)    

# Ensure src/ is in sys.path for both development and exe mode.
# Гарантируем что src/ в sys.path (для разработки и exe)
# sys.path is modified only in development mode.
# sys.path — только для режима разработки
# In frozen mode (PyInstaller), imports are managed automatically.
# В frozen (PyInstaller) импорты управляются автоматически
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent))

from app_paths import get_root, BIN_DIR, LOGS_DIR, DATA_DIR, CONFIG_PATH

import numpy as np
# === DPI awareness for a crisp tray icon and text ===
# === DPI Awareness — чёткая иконка и текст в трее ===
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware v2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Fallback для Windows 7
    except Exception:
        pass

from text_fixer import (fix_text, create_sample_dictionary,
                        reload_dictionary, get_user_dict_path,
                        get_user_dict_word_count)
from config import load_config, save_config
from mic_selector import list_microphones, select_microphone_interactive
from model_selector import scan_models, print_models, find_best_model
from mouse_listener import (MouseListener, check_trigger_press,
                             check_trigger_release, check_key_trigger_press,
                             check_key_trigger_release, config_to_trigger,
                             trigger_to_label, trigger_to_config,
                             check_paste_dictated_hotkey)
from recorder import AudioRecorder
from stt import transcribe_audio, warmup_model, stop_server, restart_server
from inserter import insert_text_at_cursor, insert_last_dictated, clear_insert_context
from tray_icon import TrayIcon
from vad_detector import VADDetector
from command_executor import (try_execute_command, create_sample_commands,
                              create_sample_aliases,
                              reload_commands, get_commands_count,
                              get_commands_path)
from command_executor import set_math_mode_callback                              
from mouse_controller import get_mouse_controller
from noise_filter import NoiseFilter
from script_manager import reload_scripts
from settings_window import open_settings_window
from about_window import open_about_window

# Replace emoji with ASCII equivalents for cp1251 compatibility.
# Замена эмодзи на ASCII для совместимости с cp1251
_EMOJI_TO_ASCII = {
    '✅': '[OK]',
    '❌': '[X]',
    '⚠️': '[!]',
    '⚠': '[!]',
    '🎤': '[MIC]',
    '🔴': '[REC]',
    '🟢': '[ON]',
    '⏹': '[STOP]',
    '⏳': '[...]',
    '🖥️': '[PC]',
    '🖥': '[PC]',
    '🧠': '[AI]',
    '🎙️': '[MIC]',
    '🎙': '[MIC]',
    '✏️': '[EDIT]',
    '✏': '[EDIT]',
    '🎯': '[>]',
    '💡': '[i]',
    '📋': '[PASTE]',
    '📁': '[DIR]',
    '📂': '[DIR]',
    '📄': '[FILE]',
    '📍': '[POS]',
    '📊': '[STAT]',
    '📤': '[OUT]',
    '🚀': '[RUN]',
    '🗑️': '[DEL]',
    '🗑': '[DEL]',
    '🔄': '[SYNC]',
    '🛑': '[STOP]',
    'ℹ️': '[i]',
    'ℹ': '[i]',
    '⌨️': '[KEY]',
    '⌨': '[KEY]',
    '🖱️': '[MOUSE]',
    '🖱': '[MOUSE]',
    '⏰': '[TIME]',
}


def _safe_encode(text):
    """Replaces emoji with ASCII equivalents for cp1251 compatibility.
    Заменяет эмодзи на ASCII-аналоги для совместимости с cp1251."""
    if not text:
        return text
    for emoji, replacement in _EMOJI_TO_ASCII.items():
        text = text.replace(emoji, replacement)
    # Remove any remaining non-printable characters.
    # Убираем оставшиеся непечатаемые символы
    try:
        text.encode('cp1251')
        return text
    except UnicodeEncodeError:
        # Replace unsupported characters with ?.
        # Заменяем непечатаемые на ?
        return text.encode('cp1251', errors='replace').decode('cp1251')


class _TimestampedOutput:
    """Adds [HH:MM:SS] to every non-empty output line.
    Добавляет [HH:MM:SS] к каждой непустой строке вывода."""

    def __init__(self, stream):
        self._stream = stream
        self._at_line_start = True

    def write(self, text):
        if not text:
            return 0
        text = _safe_encode(text)
        parts = text.split('\n')
        for i, part in enumerate(parts):
            if i > 0:
                self._stream.write('\n')
                self._at_line_start = True
            if part:
                if self._at_line_start:
                    stamp = time.strftime('[%H:%M:%S]')
                    self._stream.write(f"{stamp} {part}")
                else:
                    self._stream.write(part)
                self._at_line_start = False
        return len(text)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _PeriodicFileSink:
    """Buffered sink that accumulates logs and flushes them to a file on a timer.
    Буферизованный sink: накапливает лог и сбрасывает в файл по таймеру."""

    def __init__(self, file_path, flush_interval_sec=180):
        self.file_path = Path(file_path)
        self.flush_interval_sec = flush_interval_sec
        self._lock = threading.Lock()
        self._buffer = []
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="log-flush")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.flush()

    def write(self, text):
        if not text:
            return
        with self._lock:
            self._buffer.append(text)

    def flush(self):
        with self._lock:
            if not self._buffer:
                return
            data = ''.join(self._buffer)
            self._buffer.clear()

        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(data)
                f.flush()
        except Exception:
            # Logging must never break the main process.
            # Логирование не должно ломать основной процесс
            pass

    def _loop(self):
        while not self._stop_event.wait(self.flush_interval_sec):
            self.flush()


class _TeeStream:
    """Writes to two streams at once: console and buffered file output.
    Пишет одновременно в два потока (консоль + файл-буфер)."""

    def __init__(self, stream_a, stream_b):
        self._a = stream_a
        self._b = stream_b

    def write(self, text):
        n = self._a.write(text)
        self._b.write(text)
        return n

    def flush(self):
        try:
            self._a.flush()
        except Exception:
            pass
        try:
            self._b.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._a, name)


class _NullStream:
    """No-op stdout replacement used when console=False.
    Заглушка для stdout когда console=False."""
    def write(self, text):
        return len(text) if text else 0
    def flush(self):
        pass

# === Global state ===
# === Глобальные ===
config = {}
recorder = None
tray = None
listener = None
saved_hwnd = None
is_recording = False
is_listening = False
use_gpu = False
current_model = "auto"

# VAD state
# VAD
vad_detector = None
vad_mode = False
vad_processing = False
_vad_lock = threading.Lock()  # Protect vad_processing from race conditions.
                              # Защита vad_processing от race condition
commands_enabled = True
math_mode = False

noise_filter = None
_vad_speech_start_time = 0
_vad_processing_start_time = 0
_file_log_sink = None

def check_dependencies():
    root = get_root()
    bin_dir = BIN_DIR

    # === Check executables ===
    # === Проверяем exe ===
    whisper_exe = None
    for sub in ["cpu", "gpu", ""]:
        search_dir = bin_dir / sub if sub else bin_dir
        if not search_dir.exists():
            continue
        for name in ["whisper-cli.exe", "main.exe", "whisper.exe"]:
            candidate = search_dir / name
            if candidate.exists():
                whisper_exe = candidate
                break
        if whisper_exe:
            break
    if not whisper_exe:
        exes = list(bin_dir.glob("*.exe")) if bin_dir.exists() else []
        if exes:
            whisper_exe = exes[0]

    # === Check models ===
    # === Проверяем модели ===
    models = scan_models()

    errors = []
    if not whisper_exe:
        errors.append(
            f"❌ Не найден whisper exe в {bin_dir}\n"
            f"   CPU-версия: https://github.com/ggerganov/whisper.cpp/releases\n"
            f"   Файл: whisper-blas-bin-x64.zip"
        )
    if not models:
        errors.append(
            f"❌ Не найдены модели в models/\n"
            f"   Скачайте: https://huggingface.co/ggerganov/whisper.cpp/tree/main\n"
            f"   Рекомендация для слабого CPU: ggml-tiny.bin (75 MB)"
        )

    if errors:
        print("\n".join(errors))
        sys.exit(1)

    print(f"✅ whisper: {whisper_exe.name}")
    for m in models:
        print(f"✅ модель:  {m['name']} ({m['size_mb']:.0f} MB) — {m['speed']}")

    # === GPU / CPU: verify REAL physical GPU availability ===
    # === GPU / CPU — проверяем РЕАЛЬНОЕ наличие видеокарты ===
    gpu_dir = BIN_DIR / "gpu"
    has_gpu_exe = gpu_dir.exists() and any(
        (gpu_dir / name).exists()
        for name in ["whisper-cli.exe", "main.exe"]
    )

    gpu_physically_present = False
    gpu_name = ""

    if has_gpu_exe:
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                timeout=5,
                text=True,
                creationflags=0x08000000,  # CREATE_NO_WINDOW (Windows)
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_physically_present = True
                gpu_name = result.stdout.strip().split('\n')[0].strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    if has_gpu_exe and gpu_physically_present:
        print(f"✅ GPU доступен: {gpu_name}")
    elif has_gpu_exe and not gpu_physically_present:
        print(f"⚠️  bin/gpu/ есть, но NVIDIA GPU не обнаружен — GPU работать НЕ будет")
        if config.get("use_gpu", False):
            print(f"   → Автопереключение на CPU")
            config["use_gpu"] = False
            save_config(config)
    else:
        print(f"ℹ️  Только CPU (это нормально!)")

def setup_microphone():
    global config

    mic_index = config.get("microphone_index")
    mic_name = config.get("microphone_name", "")

    # 1. If a name exists, resolve the canonical index from list_microphones().
    # 1. Если есть имя — ищем канонический индекс из list_microphones()
    if mic_name:
        mics = list_microphones()
        for m in mics:
            if m['name'] == mic_name:
                canonical = m['index']
                if canonical != mic_index:
                    print(f"[MIC] Канонизация: [{mic_index}] → [{canonical}] {mic_name}")
                    config["microphone_index"] = canonical
                    save_config(config)
                print(f"[MIC] Сохранённый: [{canonical}] {m['name']}")
                return canonical
        
        # Not found in list_microphones(), so continue searching below.
        # Не найден в list_microphones() — продолжаем поиск ниже
        print(f"[MIC] ⚠️ '{mic_name}' не найден в канонизированном списке")

    # 2. Partial match on the first 20 characters, reusing mics from step 1.
    # 2. Частичное совпадение (первые 20 символов) — используем mics из шага 1
    if mic_name:
        if not mics:
            mics = list_microphones()

        # 2b. Partial match on the first 20 characters.
        # 2b. Частичное совпадение (первые 20 символов)
        mic_name_prefix = mic_name[:20].lower()
        for mic in mics:
            if mic['name'][:20].lower() == mic_name_prefix:
                new_index = mic['index']
                print(f"[MIC] Похожий по имени: [{new_index}] {mic['name']}")
                config["microphone_index"] = new_index
                config["microphone_name"] = mic['name']
                save_config(config)
                return new_index

        print(f"[MIC] ⚠️  '{mic_name}' не найден — возможно ещё не подключён")
        print(f"[MIC]    Watchdog найдёт его автоматически после подключения")

    # 3. Interactive selection.
    # 3. Интерактивный выбор
    if "--select-mic" in sys.argv:
        mics = list_microphones()
        if len(mics) <= 1:
            if mics:
                config["microphone_index"] = None
                config["microphone_name"] = mics[0]['name']
                save_config(config)
            return None

        if "--no-interactive" not in sys.argv:
            print("\n💡 Несколько микрофонов. Выберите:")
            idx, name = select_microphone_interactive()
            config["microphone_index"] = idx
            config["microphone_name"] = name
            save_config(config)
            return idx

    return None


def setup_model():
    """Initial model setup.
    Настройка модели при первом запуске."""
    global config, current_model

    current_model = config.get("model_name", "auto")

    models = scan_models()

    if "--select-model" in sys.argv and "--no-interactive" not in sys.argv:
        from model_selector import select_model_interactive
        chosen = select_model_interactive()
        config["model_name"] = chosen
        current_model = chosen
        save_config(config)
        return

    if current_model != "auto":
        # Verify that the selected model still exists.
        # Проверяем что модель ещё существует
        found = any(m['name'] == current_model for m in models)
        if not found:
            print(f"[MODEL] ⚠️  '{current_model}' не найдена, переключаю на auto")
            current_model = "auto"
            config["model_name"] = "auto"
            save_config(config)

    if current_model == "auto" and models:
        best = models[0]
        print(f"[MODEL] Auto → {best['name']} ({best['speed']})")
    elif models:
        m = next((m for m in models if m['name'] == current_model), models[0])
        print(f"[MODEL] {m['name']} ({m['speed']})")


# === Callbacks ===
# === Колбэки ===

def on_vad_audio(chunk):
    global vad_detector, saved_hwnd, vad_processing, noise_filter, _vad_speech_start_time, _vad_processing_start_time

    if not vad_mode or not vad_detector:
        return

    with _vad_lock:
        if vad_processing:
            # Stuck-state protection; the timeout depends on the current mode.
            # Защита от залипания — таймаут зависит от режима
            vad_timeout = 15.0 if use_gpu else 45.0
            if _vad_processing_start_time > 0:
                elapsed = time.time() - _vad_processing_start_time
                if elapsed > vad_timeout:
                    print(f"\n[VAD] ⚠️ vad_processing залип ({elapsed:.0f}с > {vad_timeout:.0f}с) — принудительный сброс!")
                    vad_processing = False
                    _vad_processing_start_time = 0
                    if vad_detector:
                        vad_detector.soft_reset()
                    # Do not return here; continue processing the current chunk.
                    # Не return — продолжаем обработку чанка
                else:
                    return
            else:
                return

    # Calibrate noise reduction during silence.
    # Калибровка шумоподавления во время тишины
    if noise_filter and not noise_filter.is_calibrated:
        noise_filter.feed_calibration(chunk)

    flat = chunk.flatten()
    event = vad_detector.process_chunk(flat)

    if event == 'speech_start':
        # If the cursor is moving, save its position for a future stop.
        # Если курсор двигается — запоминаем позицию для стопа
        mc = get_mouse_controller()
        if mc.is_moving():
            mc.mark_stop_position()
        _vad_speech_start_time = time.time()
        import win32gui
        saved_hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(saved_hwnd) if saved_hwnd else "?"
        recorder.start_vad_capture()
        print(f"\n[VAD] 🎤 Речь! Окно: '{title}'")
        if tray:
            tray.set_state(TrayIcon.STATE_RECORDING)
        # If noise reduction is still calibrating, finish calibration early.
        # Если шумоподавление ещё калибруется — завершаем калибровку
        if noise_filter and not noise_filter.is_calibrated:
            noise_filter._is_calibrated = True
            if noise_filter._calibration_buffer:
                noise_filter.noise_profile = np.concatenate(noise_filter._calibration_buffer)
                print("[VAD] 📊 Калибровка шума завершена досрочно")

    elif event == 'speech_end':
        speech_dur = time.time() - _vad_speech_start_time
        recorder.stop_vad_capture()
        print(f"[VAD] ⏸ Распознаю... (запись: {speech_dur:.2f}с)")
        if tray:
            tray.set_state(TrayIcon.STATE_READY)
        hwnd = saved_hwnd
        if hwnd:
            with _vad_lock:
                vad_processing = True
                _vad_processing_start_time = time.time()
            threading.Thread(target=_process_and_insert,
                             args=(hwnd, True), daemon=True).start()



def _setup_vad():
    """Creates and configures the VAD pipeline from the current config.
    Создаёт и настраивает VAD pipeline из текущего config."""
    global vad_detector, noise_filter
    vad_detector = VADDetector(
        aggressiveness=config.get("vad_aggressiveness", 1),
        silence_duration=config.get("vad_silence_duration", 1.5),
        accept_short_speech=config.get("vad_accept_short_speech", False),
    )
    if config.get("noise_filter_enabled", True):
        noise_filter = NoiseFilter(sample_rate=16000, calibration_sec=2.0)
        recorder.set_noise_filter(noise_filter)
    else:
        noise_filter = None
        recorder.set_noise_filter(None)
    recorder.vad_mode = True
    recorder.set_vad_callback(on_vad_audio)


def _teardown_vad():
    """Disables the VAD pipeline.
    Отключает VAD pipeline."""
    global vad_detector, noise_filter
    vad_detector = None
    noise_filter = None
    recorder.set_noise_filter(None)
    recorder.vad_mode = False
    recorder.set_vad_callback(None)




def on_mode_change(is_vad):
    global vad_mode, vad_processing, config
    vad_mode = is_vad
    vad_processing = False
    config["vad_mode"] = is_vad
    save_config(config)
    print(f"\n[MODE] {'VAD' if is_vad else 'Кнопка мыши'}")

    if is_listening:
        recorder.stop_listening()
        time.sleep(0.2)

        if is_vad:
            _setup_vad()
        else:
            _teardown_vad()

        recorder.start_listening()


def on_mic_change(device_index, device_name):
    global config
    print(f"\n[MIC] → [{device_index}] {device_name}")
    config["microphone_index"] = device_index
    config["microphone_name"] = device_name
    save_config(config)
    recorder.set_device(device_index, device_name=device_name)
    # If the app is enabled but the recorder is not running, start it.
    # Если программа включена, но recorder не запущен — запустить
    if is_listening and not recorder.is_running:
        if vad_mode:
            _setup_vad()
        recorder.start_listening()


def on_mic_refresh():
    """Safely refreshes the device list by stopping the stream and reinitializing PortAudio.
    Безопасное обновление списка: останавливает поток, переинициализирует PortAudio."""
    import sounddevice as sd
    was_running = recorder.is_running
    if was_running:
        recorder.stop_listening()
        time.sleep(0.3)
    try:
        sd._terminate()
        sd._initialize()
    except Exception as e:
        print(f"[MIC] PortAudio reinit error: {e}")
    mics = list_microphones()

    if was_running:
        # Resolve the current index from the saved device name.
        # Резолвим актуальный индекс по сохранённому имени
        saved_name = recorder._original_device_name or config.get("microphone_name", "")
        if saved_name:
            resolved = recorder._resolve_index_by_name(saved_name)
            if resolved is not None and resolved != recorder.device_index:
                print(f"[MIC] Обновлён индекс после refresh: [{recorder.device_index}] → [{resolved}]")
                recorder.device_index = resolved
                recorder._original_device_index = resolved
                config["microphone_index"] = resolved
                save_config(config)
        if vad_mode:
            _setup_vad()
        recorder.start_listening()
    return mics


def on_model_change(model_name):
    """Changes the model from the tray without restarting the application.
    Смена модели через трей — БЕЗ перезапуска."""
    global config, current_model
    current_model = model_name
    config["model_name"] = model_name
    save_config(config)

    if model_name == "auto":
        best = find_best_model()
        if best:
            print(f"\n[MODEL] Auto → {best['name']} ({best['speed']})")
        else:
            print("\n[MODEL] Auto (модель не найдена!)")
    else:
        models = scan_models()
        m = next((m for m in models if m['name'] == model_name), None)
        if m:
            print(f"\n[MODEL] → {m['label']} ({m['size_mb']:.0f} MB, {m['speed']})")
        else:
            print(f"\n[MODEL] → {model_name}")

    # Restart the server with the new model.
    # Перезапускаем сервер с новой моделью
    def _do_model_restart():
        success = restart_server(model_name, use_gpu)
        if success:
            print(f"[MODEL] ✅ Сервер перезапущен с новой моделью")
        else:
            print(f"[MODEL] ⚠️ Сервер не запустился — будет subprocess")

    threading.Thread(target=_do_model_restart, daemon=True).start()


def on_gpu_toggle(use_gpu_new):
    global use_gpu, config
    use_gpu = use_gpu_new
    config["use_gpu"] = use_gpu_new
    save_config(config)
    mode = "GPU" if use_gpu_new else "CPU"
    print(f"\n[MODE] Переключение → {mode}")

    keep_alive = config.get("warmup_on_start", True)

    def _do_switch():
        if keep_alive:
            success = restart_server(current_model, use_gpu_new)
            if success:
                print(f"[MODE] ✅ Сервер переключён на {mode}")
            else:
                print(f"[MODE] ⚠️ Сервер {mode} не запустился — будет subprocess")
        else:
            stop_server()
            print(f"[MODE] ✅ Переключено на {mode} (модель загружается по требованию)")
        if tray:
            tray.set_gpu_mode(use_gpu_new)

    threading.Thread(target=_do_switch, daemon=True).start()


def on_toggle(enabled):
    global is_listening, config
    config["app_enabled"] = enabled
    save_config(config)

    if enabled:
        print("\n[🎤] ВКЛЮЧЁН")
        is_listening = True

        if vad_mode:
            _setup_vad()
        else:
            recorder.vad_mode = False
            recorder.set_vad_callback(None)

        recorder.start_listening()
    else:
        print("\n[⏹] ВЫКЛЮЧЁН")
        is_listening = False
        if vad_detector:
            vad_detector.reset()
        _teardown_vad()
        recorder.stop_listening()


_cleanup_done = False

def _cleanup():
    """Single cleanup entry point that is safe to call multiple times.
    Единая точка очистки — безопасно вызывать многократно."""
    global _cleanup_done, is_listening
    if _cleanup_done:
        return
    _cleanup_done = True

    print("\n[EXIT] Очистка ресурсов...")
    is_listening = False

    try:
        recorder.stop_listening()
    except Exception:
        pass

    try:
        if listener:
            listener.stop()
    except Exception:
        pass

    # Most important: stop whisper-server and release GPU memory.
    # ⭐ ГЛАВНОЕ — убиваем whisper-server и освобождаем GPU
    try:
        stop_server()
    except Exception:
        pass

    try:
        if tray:
            tray.stop()
    except Exception:
        pass

    try:
        if _file_log_sink:
            _file_log_sink.stop()
    except Exception:
        pass

    print("[EXIT] Готово. GPU память освобождена.")


def on_quit():
    """Exits via the tray.
    Выход через трей."""
    _cleanup()
    os._exit(0)


def on_mouse_event(x, y, button, pressed):
    global saved_hwnd, is_recording

    trigger = config_to_trigger(config.get("trigger_button", "middle"))

    if pressed and not is_recording and not check_trigger_press(button, trigger):
        clear_insert_context()

    if not is_listening or vad_mode:
        return

    if pressed:
        if not is_recording and check_trigger_press(button, trigger):
            import win32gui
            saved_hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(saved_hwnd) if saved_hwnd else "?"
            print(f"\n[🔴] Запись | '{title}'")
            is_recording = True
            recorder.start_capture()
            if tray:
                tray.set_state(TrayIcon.STATE_RECORDING)
    else:
        if is_recording and check_trigger_release(button, trigger):
            is_recording = False
            recorder.stop_capture()
            if tray:
                tray.set_state(TrayIcon.STATE_READY)
            if not saved_hwnd:
                return
            threading.Thread(target=_process_and_insert,
                             args=(saved_hwnd,), daemon=True).start()


def _do_transcribe(wav_path):
    """Runs recognition and text-fixing.
    Распознавание + исправление текста."""
    raw_text = transcribe_audio(
        str(wav_path),
        use_gpu=use_gpu,
        language=config.get("language", "ru"),
        threads=config.get("threads", 0),
        model_name=current_model,
    )

    if raw_text:
        print(f"[STT raw] '{raw_text}'")

    # Apply text-fixing with the current settings.
    # Исправляем с учётом настроек
    # Pass the fixer settings into the text-fixing pipeline.
    # Передаём настройки исправления в трей
    fix_settings = {
        "text_fix_enabled": config.get("text_fix_enabled", True),
        "text_fix_hallucinations": config.get("text_fix_hallucinations", True),
        "text_fix_dictionary": config.get("text_fix_dictionary", True),
        "text_fix_punctuation": config.get("text_fix_punctuation", True),
        "text_fix_repetitions": config.get("text_fix_repetitions", True),
        "text_fix_user_dict": config.get("text_fix_user_dict", True),
        "preserve_numeric_repetitions": math_mode,
        "preserve_math_symbol_repetitions": math_mode,
    }

    fixed_text = fix_text(raw_text, settings=fix_settings)
    return fixed_text

def on_fix_toggle(key, value):
    """Enables or disables one text-fixing stage.
    Вкл/выкл этап исправления текста."""
    global config
    config[key] = value
    save_config(config)
    status = "ВКЛ" if value else "ВЫКЛ"
    labels = {
        "text_fix_enabled": "Исправление текста",
        "text_fix_hallucinations": "Галлюцинации",
        "text_fix_dictionary": "Словарь терминов",
        "text_fix_punctuation": "Пунктуация",
        "text_fix_repetitions": "Повторы",
        "text_fix_user_dict": "Пользовательский словарь",
    }
    name = labels.get(key, key)
    print(f"\n[FIX] {name}: {status}")



def on_short_speech_toggle(value):
    global config, vad_detector
    config["vad_accept_short_speech"] = value
    save_config(config)
    if vad_detector:
        vad_detector.accept_short_speech = value
    print(f"\n[VAD] Короткая речь: {'ВКЛ' if value else 'ВЫКЛ'}")

def on_warmup_toggle(value):
    global config
    config["warmup_on_start"] = value
    save_config(config)

    from stt import set_keep_server_alive
    set_keep_server_alive(value)

    if value:
        print(f"\n[SERVER] Модель будет постоянно в памяти")
        def _start():
            success = warmup_model(model_name=current_model, use_gpu=use_gpu)
            if success:
                print("[SERVER] ✅ Модель загружена в память")
            else:
                print("[SERVER] ⚠️ Не удалось загрузить")
        threading.Thread(target=_start, daemon=True).start()
    else:
        print(f"\n[SERVER] Модель выгружена, будет загружаться по требованию")
        threading.Thread(target=stop_server, daemon=True).start()


def on_trigger_change(trigger_config_str):
    global config
    config["trigger_button"] = trigger_config_str
    save_config(config)
    trigger = config_to_trigger(trigger_config_str)
    label = trigger_to_label(trigger)
    print(f"\n[TRIGGER] Кнопка записи: {label}")

def on_noise_filter_toggle(value):
    global config, noise_filter
    config["noise_filter_enabled"] = value
    save_config(config)
    if value and vad_mode:
        noise_filter = NoiseFilter(sample_rate=16000, calibration_sec=2.0)
        recorder.set_noise_filter(noise_filter)
    else:
        noise_filter = None
        recorder.set_noise_filter(None)
    print(f"\n[NOISE] Шумоподавление: {'ВКЛ' if value else 'ВЫКЛ'}")


def on_math_mode_toggle(value):
    """Enables or disables math mode.
    Вкл/выкл режим математики."""
    global math_mode, config
    math_mode = value
    config["math_mode"] = value
    save_config(config)
    try:
        from math_converter import reset_math_buffer
        reset_math_buffer()
    except Exception:
        pass
    print(f"\n[MATH] Режим математики: {'ВКЛ' if value else 'ВЫКЛ'}")    
    if tray:
        tray.set_math_mode(value)

def on_show_recognition_toggle(value):
    global config
    config["show_recognition_result"] = value
    save_config(config)
    print(f"\n[POPUP] Показ распознанного: {'ВКЛ' if value else 'ВЫКЛ'}")    



def on_log_toggle(enabled):
    """Enables or disables file logging.
    Вкл/выкл запись логов."""
    global config, _file_log_sink
    config["log_enabled"] = enabled
    save_config(config)

    if enabled:
        if _file_log_sink is None:
            _start_file_logging()
        print(f"[LOG] Логирование: ВКЛ")
    else:
        print(f"[LOG] Логирование: ВЫКЛ (лог-файл закрыт)")
        if _file_log_sink:
            _file_log_sink.stop()
            _file_log_sink = None
            # Switch stdout/stderr back to plain timestamped wrappers.
            # Переключаем stdout/stderr обратно на чистый timestamped
            raw_stdout = sys.__stdout__
            raw_stderr = sys.__stderr__
            if raw_stdout is not None:
                sys.stdout = _TimestampedOutput(raw_stdout)
            else:
                sys.stdout = _TimestampedOutput(_NullStream())
            if raw_stderr is not None:
                sys.stderr = _TimestampedOutput(raw_stderr)
            else:
                sys.stderr = _TimestampedOutput(_NullStream())


def on_log_dir_change(new_dir):
    """Changes the log directory at runtime.
    Смена папки логов на лету."""
    global config, _file_log_sink
    config["log_directory"] = new_dir
    save_config(config)

    display = new_dir if new_dir else "logs/ (стандартная)"
    print(f"[LOG] Папка логов: {display}")

    # If file logging is enabled, restart the sink in the new folder.
    # Если логирование активно — перезапускаем sink в новую папку
    if config.get("log_enabled", True) and _file_log_sink:
        _file_log_sink.stop()
        _file_log_sink = None
        _start_file_logging()
        print(f"[LOG] Лог перенаправлен в: {display}")


def _start_file_logging():
    """Starts file logging in the directory from the current config.
    Запускает файловый лог в текущую папку из конфига."""
    global _file_log_sink
    log_dir_cfg = config.get("log_directory", "")
    if log_dir_cfg:
        logs_dir = Path(log_dir_cfg)
    else:
        logs_dir = LOGS_DIR

    log_name = time.strftime("vox_bee_%Y%m%d_%H%M%S.log")
    log_path = logs_dir / log_name

    _file_log_sink = _PeriodicFileSink(log_path, flush_interval_sec=180)
    _file_log_sink.start()

    # Rebuild stdout/stderr with tee streams.
    # Перестраиваем stdout/stderr с tee
    raw_stdout = sys.__stdout__
    raw_stderr = sys.__stderr__
    if raw_stdout is not None:
        sys.stdout = _TimestampedOutput(_TeeStream(raw_stdout, _file_log_sink))
    else:
        sys.stdout = _TimestampedOutput(_file_log_sink)
    if raw_stderr is not None:
        sys.stderr = _TimestampedOutput(_TeeStream(raw_stderr, _file_log_sink))
    else:
        sys.stderr = _TimestampedOutput(_file_log_sink)

    print(f"[LOG] Файл лога: {log_path}")

def on_mouse_step_change(step):
    global config
    config["mouse_step"] = step
    save_config(config)
    get_mouse_controller().set_step(step)
    print(f"\n[MOUSE] Шаг: {step}px")     

    
def on_focus_positions_changed(positions):
    """Focus-position callback: persist updates into config.
    Callback при изменении позиций — сохраняем в конфиг."""
    global config
    config["focus_positions"] = positions
    save_config(config)
    if tray:
        from focus_manager import get_positions_for_tray
        tray.set_focus_positions(get_positions_for_tray())


def on_focus_position_delete(label):
    """Deletes one focus position from the tray by label like "[1] Title".
    Удаление одной позиции через трей (по label вида '[1] Title')."""
    from focus_manager import delete_position, get_positions_for_tray, get_positions_for_save
    # Extract the slot number from a label like "[1] Title...".
    # Извлекаем номер слота из label: "[1] Title..."
    import re
    match = re.match(r'^\[(\d+)\]', label)
    if match:
        slot = int(match.group(1))
        delete_position(slot)
    global config
    config["focus_positions"] = get_positions_for_save()
    save_config(config)
    if tray:
        tray.set_focus_positions(get_positions_for_tray())


def on_focus_position_goto(label):
    """Moves to a saved focus point from the tray.
    Переход к точке фокуса через трей."""
    from focus_manager import switch_to_position
    import re
    match = re.match(r'^\[(\d+)\]', label)
    if match:
        slot = int(match.group(1))
        switch_to_position(slot)

def on_focus_positions_reset():
    """Resets all focus positions from the tray.
    Сброс всех позиций через трей."""
    from focus_manager import clear_all_positions, get_positions_for_tray, get_positions_for_save
    clear_all_positions()
    global config
    config["focus_positions"] = get_positions_for_save()
    save_config(config)
    if tray:
        tray.set_focus_positions(get_positions_for_tray()) 


def _sync_tray_from_config():
    """Syncs tray state from the current config after the settings window closes.
    Синхронизирует состояние трея с текущим config после закрытия окна настроек."""
    if not tray:
        return
    tray._vad_mode = config.get('vad_mode', False)
    tray.set_gpu_mode(config.get('use_gpu', False))
    tray.set_mic_name(config.get('microphone_name', 'системный'))
    tray.set_model_name(config.get('model_name', 'auto'))
    tray._noise_filter_enabled = config.get('noise_filter_enabled', True)
    tray.set_show_recognition_result(config.get('show_recognition_result', False))
    tray.set_mouse_step(config.get('mouse_step', 150))
    tray.set_commands_enabled(config.get('commands_enabled', True))
    tray.set_math_mode(config.get('math_mode', False))    
    tray.set_log_enabled(config.get('log_enabled', False))
    tray.set_log_directory(config.get('log_directory', ''))
    tray.set_trigger_button(config.get('trigger_button', 'middle'))
    if hasattr(tray, 'set_language'):
        tray.set_language(config.get('language', 'ru'))
    from autostart import is_autostart_enabled
    tray.set_autostart_enabled(is_autostart_enabled())

    fix_settings = {
        "text_fix_enabled": config.get("text_fix_enabled", True),
        "text_fix_hallucinations": config.get("text_fix_hallucinations", True),
        "text_fix_dictionary": config.get("text_fix_dictionary", True),
        "text_fix_punctuation": config.get("text_fix_punctuation", True),
        "text_fix_repetitions": config.get("text_fix_repetitions", True),
        "text_fix_user_dict": config.get("text_fix_user_dict", True),
        "vad_accept_short_speech": config.get("vad_accept_short_speech", False),
        "warmup_on_start": config.get("warmup_on_start", True),
    }
    tray.set_fix_settings(fix_settings)


def _open_settings():
    """Builds context and opens the settings window in the Tk thread.
    Собирает контекст и открывает окно настроек в Tk-потоке."""
    from mouse_listener import config_to_trigger, trigger_to_label
    from autostart import is_autostart_enabled, toggle_autostart

    fix_settings = {
        "text_fix_enabled": config.get("text_fix_enabled", True),
        "text_fix_hallucinations": config.get("text_fix_hallucinations", True),
        "text_fix_dictionary": config.get("text_fix_dictionary", True),
        "text_fix_punctuation": config.get("text_fix_punctuation", True),
        "text_fix_repetitions": config.get("text_fix_repetitions", True),
        "text_fix_user_dict": config.get("text_fix_user_dict", True),
        "vad_accept_short_speech": config.get("vad_accept_short_speech", False),
        "warmup_on_start": config.get("warmup_on_start", True),
    }

    current_language = config.get("language", "ru")
    trigger = config_to_trigger(config.get("trigger_button", "middle"))
    t_label = trigger_to_label(trigger, current_language)

    def _capture_trigger():
        if tray:
            tray._do_capture_in_tk()

    def _reset_trigger():
        if tray:
            tray._on_reset_trigger(None, None)

    def _refresh_trigger():
        t = config_to_trigger(config.get("trigger_button", "middle"))
        return trigger_to_label(t, config.get("language", "ru"))

    def _on_language_change(lang):
        config["language"] = lang
        save_config(config)
        if tray and hasattr(tray, 'set_language'):
            tray.set_language(lang)

    def _open_about():
        if tray and tray._tk_root:
            open_about_window(tray._tk_root, config.get("language", "ru"))

    ctx = {
        'config': config,
        'language': current_language,
        'mic_list': list_microphones(),
        'model_list': scan_models(),
        'fix_settings': fix_settings,
        'trigger_label': t_label,
        'autostart_enabled': is_autostart_enabled(),
        'noise_filter_enabled': config.get("noise_filter_enabled", True),
        'commands_enabled': config.get("commands_enabled", True),
        'on_mode_change': on_mode_change,
        'on_mic_change': on_mic_change,
        'on_mic_refresh': on_mic_refresh,
        'on_gpu_toggle': on_gpu_toggle,
        'on_model_change': on_model_change,
        'on_fix_toggle': on_fix_toggle,
        'on_short_speech_toggle': on_short_speech_toggle,
        'on_warmup_toggle': on_warmup_toggle,
        'on_noise_filter_toggle': on_noise_filter_toggle,
        'on_show_recognition_toggle': on_show_recognition_toggle,
        'on_mouse_step_change': on_mouse_step_change,
        'on_commands_toggle': on_commands_toggle,
        'on_log_toggle': on_log_toggle,
        'on_log_dir_change': on_log_dir_change,
        'on_autostart_toggle': lambda val: toggle_autostart(val),
        'on_trigger_capture': _capture_trigger,
        'on_trigger_reset': _reset_trigger,
        'refresh_trigger_label': _refresh_trigger,
        'on_reload_commands': on_reload_commands,
        'on_reload_dict': on_reload_dict,
        'on_language_change': _on_language_change,
        'on_open_about': _open_about,
        'on_settings_closed': _sync_tray_from_config,
    }

    if tray and tray._tk_root:
        open_settings_window(tray._tk_root, ctx)        

def on_reload_dict():
    """Reloads the dictionary from disk.
    Перезагрузка словаря из файла."""
    reload_dictionary()
    count = get_user_dict_word_count()
    if tray:
        tray.set_user_dict_count(count)
    print(f"[FIX] Словарь: {count} слов")


def on_open_dict():
    """Opens the dictionary file in a text editor.
    Открывает файл словаря в текстовом редакторе."""
    dict_path = get_user_dict_path()
    if not dict_path.exists():
        create_sample_dictionary()
    try:
        os.startfile(str(dict_path))
        print(f"[FIX] Открыт: {dict_path}")
    except Exception as e:
        print(f"[FIX] Ошибка открытия: {e}")


def on_reload_commands():
    """Reloads commands from disk.
    Перезагрузка команд из файла."""
    reload_commands()
    count = get_commands_count()
    reload_scripts()
    if tray:
        tray.set_commands_count(count)
    print(f"[CMD] Команды перезагружены: {count} триггеров")


def on_commands_toggle(enabled):
    """Enables or disables command recognition.
    Вкл/выкл распознавание команд."""
    global commands_enabled, config
    commands_enabled = enabled
    config["commands_enabled"] = enabled
    save_config(config)
    status = "ВКЛ" if enabled else "ВЫКЛ"
    print(f"\n[CMD] Распознавание команд: {status}")       

def _process_and_insert(hwnd, is_vad=False):
    """Recognizes speech, then executes a command or inserts text.
    Распознавание + выполнение команды или вставка текста."""
    global vad_processing, _vad_processing_start_time
    import tempfile
    temp_wav_handle = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
        prefix="vox_bee_vad_" if is_vad else "vox_bee_audio_",
    )
    temp_wav_handle.close()
    temp_wav = Path(temp_wav_handle.name)
    try:
        t0 = time.time()
        if not recorder.save_to_wav(temp_wav):
            if not is_vad:
                print("[INFO] Нет аудио")
            return

        t1 = time.time()
        if is_vad:
            print(f"[⏳] Распознавание... (save: {t1-t0:.2f}с)")
        else:
            print("[⏳] Распознавание...")

        text = _do_transcribe(temp_wav)
        t2 = time.time()
        if is_vad:
            print(f"[✅] '{text}' (STT: {t2-t1:.2f}с, всего: {t2-t0:.2f}с)")
        else:
            print(f"[✅] '{text}'")

        if tray and is_listening:
            tray.set_state(TrayIcon.STATE_READY)

        if not text.strip():
            if tray:
                tray.show_recognition_popup(text)
            if not is_vad:
                print("[INFO] Пусто")
            return

        # Decide whether the phrase is a command or plain text.
        # Проверяем: команда или текст?
        if commands_enabled:
            is_cmd, cmd_info = try_execute_command(text)
        else:
            is_cmd, cmd_info = False, None

        if is_cmd:
            if tray:
                tray.show_recognition_popup(
                    text,
                    is_command=True,
                    command_name=cmd_info.get("value", ""),
                    trigger_word=cmd_info.get("trigger", "")
                )
            if cmd_info["type"] == "paste":
                if insert_text_at_cursor(hwnd, cmd_info["value"]):
                    print(f"[CMD] 📋 Вставлена команда: {cmd_info['value']}")
            elif cmd_info["type"] == "hotkey":
                print(f"[CMD] ⌨️ Выполнено: {cmd_info['value']}")
            elif cmd_info["type"] == "mouse":
                print(f"[CMD] 🖱️ Мышь: {cmd_info['value']}")
            elif cmd_info["type"] == "focus":
                print(f"[CMD] 📍 Фокус: {cmd_info['value']}")
            elif cmd_info["type"] == "script":
                print(f"[CMD] 🚀 Скрипт: {cmd_info['value']}")
            elif cmd_info["type"] == "none":
                pass
        else:
            # Math mode: convert spoken words into formulas.
            # Математический режим — конвертируем слова в формулы
            if math_mode:
                from math_converter import process_math_input
                original = text
                math_result = process_math_input(text)
                text = math_result["text"]
                replace_left_chars = math_result.get("replace_left_chars", 0)
                smart_spacing = math_result.get("smart_spacing", False)
                if text != original or replace_left_chars:
                    print(f"[MATH] '{original}' -> '{text}' (replace_left={replace_left_chars})")
            else:
                replace_left_chars = 0
                smart_spacing = True
            if tray:
                tray.show_recognition_popup(text, is_command=False)
            if insert_text_at_cursor(hwnd, text, replace_left_chars=replace_left_chars, smart_spacing=smart_spacing):
                print("[📋] Вставлено!")
            elif not is_vad:
                print("[⚠] Не удалось вставить")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        if tray and is_listening:
            tray.set_state(TrayIcon.STATE_READY)
    finally:
        if is_vad:
            with _vad_lock:
                vad_processing = False
                _vad_processing_start_time = 0

        if temp_wav.exists():
            try:
                temp_wav.unlink()
            except Exception:
                pass
        recorder.clear()

        if is_vad:
            if vad_detector:
                vad_detector.soft_reset()
            if noise_filter:
                noise_filter.soft_reset()


def on_device_lost():
    """Handles microphone loss.
    Микрофон потерян."""
    print("[🔴 MIC] Микрофон отключён!")
    if tray:
        tray.set_state(TrayIcon.STATE_OFF)
        tray.icon.title = "VoxBee — ⚠️ Микрофон потерян"


def on_device_restored():
    """Handles microphone restoration.
    Микрофон восстановлен."""
    print("[🟢 MIC] Микрофон восстановлен!")

    if recorder:
        recorder._device_pending = False

        # Update the saved index; it may change after the device reconnects.
        # Обновляем сохранённый индекс (мог измениться после переподключения)
        if recorder.device_index is not None:
            new_index = recorder.device_index
            new_name = recorder._get_device_name()
            config["microphone_index"] = new_index
            config["microphone_name"] = new_name
            save_config(config)
            print(f"[MIC] Обновлён конфиг: [{new_index}] {new_name}")

            if tray:
                tray.set_mic_name(new_name)
                tray.set_mic_list(list_microphones())
    if tray and is_listening:
        tray.set_state(TrayIcon.STATE_READY)
        tray.icon.title = "VoxBee — Готов"

def _get_pressed_key_name(key):
    """Returns a normalized pynput key name when possible.
    Возвращает нормализованное имя клавиши pynput, если это возможно."""
    name = getattr(key, "name", None)
    if name:
        return name.lower()

    char = getattr(key, "char", None)
    if char:
        return char.lower()

    vk = getattr(key, "vk", None)
    if vk is None:
        return None

    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    return None


def _should_clear_insert_context_on_key(key):
    """Manual typing or navigation invalidates smart-spacing history.
    Ручной ввод или навигация сбрасывают историю умных пробелов."""
    key_name = _get_pressed_key_name(key)
    if not key_name:
        return False

    if key_name in {
        "ctrl", "ctrl_l", "ctrl_r",
        "alt", "alt_l", "alt_r", "alt_gr",
        "shift", "shift_l", "shift_r",
        "cmd", "cmd_l", "cmd_r",
    }:
        return False

    return True


def on_key_event(key, pressed):
    """Handles keyboard input as a recording trigger or paste hotkey.
    Обработка клавиши клавиатуры как триггера записи или хоткея вставки."""
    global saved_hwnd, is_recording

    # Ctrl+Alt+V inserts the last dictated text.
    # It works ALWAYS, even when the microphone is disabled.
    # Ctrl+Alt+V — вставка последнего надиктованного текста
    # Работает ВСЕГДА, даже когда микрофон выключен
    if pressed and check_paste_dictated_hotkey(key):
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            threading.Thread(
                target=insert_last_dictated,
                args=(hwnd,),
                daemon=True,
            ).start()
        return

    if pressed and _should_clear_insert_context_on_key(key):
        clear_insert_context()

    if not is_listening or vad_mode:
        return

    trigger = config_to_trigger(config.get("trigger_button", "middle"))

    # Apply this path only when the trigger is a keyboard key.
    # Только если триггер — клавиша клавиатуры
    if not trigger.get("button", "").startswith("key:"):
        return

    if pressed:
        if not is_recording and check_key_trigger_press(key, trigger):
            import win32gui
            saved_hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(saved_hwnd) if saved_hwnd else "?"
            print(f"\n[🔴] Запись | '{title}'")
            is_recording = True
            recorder.start_capture()
            if tray:
                tray.set_state(TrayIcon.STATE_RECORDING)
    else:
        if is_recording and check_key_trigger_release(key, trigger):
            is_recording = False
            recorder.stop_capture()
            if tray:
                tray.set_state(TrayIcon.STATE_READY)
            if not saved_hwnd:
                return
            threading.Thread(target=_process_and_insert,
                             args=(saved_hwnd,), daemon=True).start()


# === Entry point ===
# === Точка входа ===
def main():
    global config, recorder, tray, listener, use_gpu, current_model, _file_log_sink, vad_mode, math_mode, commands_enabled
    # === Timestamps for all logs ===
    # === Таймстампы для всех логов ===
    _program_start = time.time()
    _is_first_run = not CONFIG_PATH.exists()
    config = load_config()

    if config.get("log_enabled", True):
        _start_file_logging()
        print("[LOG] Сброс буфера в файл: каждые 3 минуты")
    else:
        if sys.stdout is not None:
            sys.stdout = _TimestampedOutput(sys.stdout)
        else:
            sys.stdout = _TimestampedOutput(_NullStream())
        if sys.stderr is not None:
            sys.stderr = _TimestampedOutput(sys.stderr)
        else:
            sys.stderr = _TimestampedOutput(_NullStream())
        print("[LOG] Логирование в файл: ВЫКЛ")

    from stt import set_program_start_time
    set_program_start_time(_program_start)    

    # === Ensure GPU cleanup on ANY shutdown path ===
    # === Гарантия очистки GPU при ЛЮБОМ завершении ===
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, lambda sig, frame: _cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda sig, frame: _cleanup() or sys.exit(0))

    use_gpu = config.get("use_gpu", False)
    if use_gpu:
        gpu_dir = BIN_DIR / "gpu"
        has_gpu_exe = (gpu_dir / "whisper-cli.exe").exists() or (gpu_dir / "main.exe").exists()
        if not has_gpu_exe:
            print("[CONFIG] ⚠️ GPU запрошен, но bin/gpu/ не найден → CPU")
            use_gpu = False
            config["use_gpu"] = False
            save_config(config)

    # Create sample data files if they do not exist yet.
    # Создаём пример словаря если нет
    create_sample_dictionary()
    create_sample_commands()
    create_sample_aliases()

    # Check runtime dependencies.
    # Проверяем зависимости
    check_dependencies()

    # Print the model list for --list-models and exit.
    # Показать модели если --list-models
    if "--list-models" in sys.argv:
        from model_selector import print_models
        print_models()
        sys.exit(0)

    # Initial model and microphone setup.
    # Настройка модели и микрофона
    setup_model()
    mic_index = setup_microphone()

    # Create the recorder with the selected microphone.
    # Создаём рекордер с выбранным микрофоном
    recorder = AudioRecorder(
        pre_buffer_sec=config.get("pre_buffer_sec", 0.5),
        max_duration_sec=config.get("max_duration_sec", 180),
        device_index=mic_index,
    )
    recorder.on_device_lost = on_device_lost
    recorder.on_device_restored = on_device_restored

    # If the microphone is missing at startup, the watchdog will keep searching for it.
    # Если микрофон не найден при старте — watchdog будет искать его
    if mic_index is None and config.get("microphone_name"):
        recorder._original_device_name = config["microphone_name"]
        recorder._device_pending = True
        print(f"[MIC] Watchdog будет искать: '{config['microphone_name']}'")
    # Startup banner.
    # Баннер
    print()
    print("=" * 55)
    print("  🐝 VoxBee — голосовой ввод")
    mode_str = "GPU (CUDA)" if use_gpu else "CPU"
    mic_name = config.get("microphone_name", "системный")
    fix_status = "ВКЛ" if config.get("text_fix_enabled", True) else "ВЫКЛ"
    mic_api = ""
    try:
        import sounddevice as sd
        mic_idx = config.get("microphone_index")
        if mic_idx is not None:
            dev = sd.query_devices(mic_idx)
            hostapi_info = sd.query_hostapis(dev['hostapi'])
            mic_api = f" ({hostapi_info['name']})"
    except Exception:
        pass
    print(f"  🖥️  Режим:       {mode_str}")
    print(f"  🧠 Модель:      {current_model}")
    print(f"  🎙️  Микрофон:    {mic_name}{mic_api}")
    trigger_label = trigger_to_label(config_to_trigger(config.get("trigger_button", "middle")))
    print(f"  ✏️  Исправление: {fix_status}")
    print(f"  🎯 Триггер:     {trigger_label}")
    print(f"  📂 Данные:      {DATA_DIR}")    
    print("=" * 55)

    # === Tray ===
    # === Трей ===
    tray = TrayIcon(on_toggle=on_toggle, on_quit=on_quit)

    # Mode callback.
    # Режим
    tray.on_mode_change = on_mode_change

    # Microphone callbacks.
    # Микрофон
    tray.on_mic_change = on_mic_change
    tray.on_mic_refresh = on_mic_refresh    

    # GPU callback.
    # GPU
    tray.on_gpu_toggle = on_gpu_toggle

    # Model callback.
    # Модель
    tray.on_model_change = on_model_change

    # Text-fixing callbacks.
    # Исправление текста
    tray.on_fix_toggle = on_fix_toggle
    tray.on_reload_dict = on_reload_dict
    tray.on_open_dict = on_open_dict
    tray.on_reload_commands = on_reload_commands
    tray.on_commands_toggle = on_commands_toggle    
    tray.on_short_speech_toggle = on_short_speech_toggle
    tray.on_warmup_toggle = on_warmup_toggle
    tray.on_mouse_step_change = on_mouse_step_change
    tray.on_noise_filter_toggle = on_noise_filter_toggle
    tray.on_math_mode_toggle = on_math_mode_toggle    
    set_math_mode_callback(on_math_mode_toggle)    
    tray.on_trigger_change = on_trigger_change
    tray.on_show_recognition_toggle = on_show_recognition_toggle
    tray.on_log_toggle = on_log_toggle
    tray.on_log_dir_change = on_log_dir_change
    tray.on_language_change = lambda lang: (config.__setitem__("language", lang), save_config(config))
    # Autostart integration.
    # Автозапуск
    from autostart import is_autostart_enabled, toggle_autostart
    tray.on_autostart_toggle = lambda val: toggle_autostart(val)
    tray.set_autostart_enabled(is_autostart_enabled())    
    
    tray.set_log_enabled(config.get("log_enabled", True))
    tray.set_log_directory(config.get("log_directory", ""))
    tray.set_language(config.get("language", "ru"))
    tray.set_show_recognition_result(config.get("show_recognition_result", False))
    tray._noise_filter_enabled = config.get("noise_filter_enabled", True)
    mouse_step = config.get("mouse_step", 150)
    tray.set_mouse_step(mouse_step)
    get_mouse_controller().set_step(mouse_step)

    # === Focus system ===
    # === Фокус-система ===
    from focus_manager import (set_on_change_callback, load_positions_from_config,
                               start_hotkey_listener, get_positions_for_tray)
    set_on_change_callback(on_focus_positions_changed)
    load_positions_from_config(config.get("focus_positions", {}))
    tray.on_focus_position_delete = on_focus_position_delete
    tray.on_focus_position_goto = on_focus_position_goto    
    tray.on_focus_positions_reset = on_focus_positions_reset
    tray.set_focus_positions(get_positions_for_tray())
    start_hotkey_listener()

    

    tray.set_trigger_button(config.get("trigger_button", "middle"))
    # Pass text-fixing settings into the tray state.
    # Передаём настройки исправления в трей
    fix_settings = {
        "text_fix_enabled": config.get("text_fix_enabled", True),
        "text_fix_hallucinations": config.get("text_fix_hallucinations", True),
        "text_fix_dictionary": config.get("text_fix_dictionary", True),
        "text_fix_punctuation": config.get("text_fix_punctuation", True),
        "text_fix_repetitions": config.get("text_fix_repetitions", True),
        "text_fix_user_dict": config.get("text_fix_user_dict", True),
        "vad_accept_short_speech": config.get("vad_accept_short_speech", False),
        "warmup_on_start": config.get("warmup_on_start", True),
    }

    
    
    tray.set_fix_settings(fix_settings)
    tray.set_commands_count(get_commands_count())
    tray.set_commands_enabled(config.get("commands_enabled", True))
    commands_enabled = config.get("commands_enabled", True)      
    math_mode = config.get("math_mode", False)
    tray.set_math_mode(math_mode)    
    tray.set_user_dict_count(get_user_dict_word_count())

    # Pass the microphone list into the tray.
    # Передаём список микрофонов
    mics = list_microphones()
    tray.set_mic_list(mics)
    tray.set_mic_name(config.get("microphone_name", "системный"))

    # Pass the model list into the tray.
    # Передаём список моделей
    models = scan_models()
    tray.set_model_list(models)
    tray.set_model_name(current_model)

    # GPU mode state.
    # GPU режим
    tray.set_gpu_mode(use_gpu)

    # === Restore VAD mode ===
    # Set vad_mode BEFORE on_toggle(), because on_toggle() checks it
    # and creates the VAD detector, noise filter, and callback.
    # === ВОССТАНОВЛЕНИЕ VAD РЕЖИМА ===
    # vad_mode ставится ДО on_toggle(), который проверяет его
    # и создаёт VAD detector + noise_filter + callback
    saved_vad_mode = config.get("vad_mode", False)
    if saved_vad_mode:
        vad_mode = True
        tray._vad_mode = True
        print("[CONFIG] VAD режим восстановлен: ВКЛ")

    # Settings-window callbacks.
    # Callback окна настроек
    tray.on_open_settings = _open_settings
    tray.on_open_about = lambda: open_about_window(tray._tk_root, config.get("language", "ru"))

    # Start the tray icon.
    # Запускаем трей
    tray.start()

    # On first launch, open the settings window automatically.
    # Первый запуск — показать окно настроек
    if _is_first_run:
        def _show_first_run_settings():
            import time as _t
            _t.sleep(2.0)
            if tray:
                tray._run_in_tk(_open_settings)

        threading.Thread(target=_show_first_run_settings, daemon=True).start()

    # Configure whether the server stays warm in memory or starts on demand.
    # Настройка режима сервера: постоянно в памяти или по требованию
    from stt import set_keep_server_alive
    keep_alive = config.get("warmup_on_start", True)
    set_keep_server_alive(keep_alive)

    # Warm up the model only in the "always in memory" mode.
    # Прогрев модели (только если режим "постоянно в памяти")
    if keep_alive:
        def _warmup():
            print("\n[⏳] Прогрев модели...")
            tray.icon.title = "VoxBee — Загрузка модели..."
            start = time.time()
            success = warmup_model(model_name=current_model, use_gpu=use_gpu)
            elapsed = time.time() - start
            if success:
                print(f"[✅] Модель готова! ({elapsed:.1f} сек)")
            else:
                print(f"[⚠️] Прогрев не удался ({elapsed:.1f} сек)")

        warmup_thread = threading.Thread(target=_warmup, daemon=True)
        warmup_thread.start()
        warmup_thread.join(timeout=90)
    else:
        print("\n[ℹ️] Модель будет загружаться по требованию (экономия памяти)")
    
    # Restore enabled/disabled state on startup.
    # Восстанавливаем состояние вкл/выкл при запуске
    enabled = config.get("app_enabled", True)
    on_toggle(enabled)
    tray.set_state(TrayIcon.STATE_READY if enabled else TrayIcon.STATE_OFF)

    # User hints.
    # Подсказки
    print()
    print("  🟢 Трей → ЛКМ вкл/выкл")
    print(f"  🎯 {trigger_label} → говорите → отпустите")
    print("  ⚙️  Трей ПКМ → Модель / Микрофон / GPU / VAD")
    print("  ✏️  Трей ПКМ → Исправление текста / Словарь")
    print("  📋 Ctrl+Alt+V → повторная вставка надиктованного")
    print()
    print("  💡 Аргументы:")
    print("     --select-mic     выбрать микрофон")
    print("     --select-model   выбрать модель")
    print("     --list-models    показать все модели")
    print()

    # Mouse + keyboard listener.
    # Слушатель мыши + клавиатуры
    listener = MouseListener(on_mouse_event, on_key_event)
    listener.start()
    
    import faulthandler
    try:
        faulthandler.enable()
    except Exception:
        pass


    # Main loop.
    # Главный цикл
    try:
        while True:

                     
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C...")
        _cleanup()
        sys.exit(0)


if __name__ == "__main__":
    main()
