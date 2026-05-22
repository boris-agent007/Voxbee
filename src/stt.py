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

import threading
import requests
import subprocess
import os
import socket
import time
import tempfile
from pathlib import Path
from app_paths import get_root, BIN_DIR, MODELS_DIR, COMMANDS_PATH
import re
import json


_program_start_time = None


def set_program_start_time(t):
    """Sets the program start time (called from main).
    Устанавливает время запуска программы (вызывается из main)."""
    global _program_start_time
    _program_start_time = t


def _format_start_info():
    """Returns a string with the start time and uptime.
    Возвращает строку: время запуска + аптайм."""
    if _program_start_time is None:
        return "N/A"
    start_str = time.strftime('%H:%M:%S', time.localtime(_program_start_time))
    elapsed = time.time() - _program_start_time
    h = int(elapsed // 3600)
    m = int((elapsed % 3600) // 60)
    s = int(elapsed % 60)
    if h > 0:
        return f"{start_str} (+{h}ч{m:02d}м)"
    elif m > 0:
        return f"{start_str} (+{m}м{s:02d}с)"
    else:
        return f"{start_str} (+{s}с)"


def _build_commands_prompt():
    """Builds a prompt from commands and numerals to improve recognition.
    Собирает prompt из команд + числительных для улучшения распознавания."""
    try:
        commands_path = COMMANDS_PATH
        
        # Numerals 1-72 for grid navigation.
        # Числительные 1-72 для grid-навигации
        numerals = [
            "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
            "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
            "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать", "двадцать",
            "двадцать один", "двадцать два", "двадцать три", "двадцать четыре",
            "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят",
        ]
        
        triggers = []
        if commands_path.exists():
            with open(commands_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # All triggers except the English ones; Whisper will not emit them in Russian mode.
            # Все триггеры, кроме английских (Whisper в русском режиме их не выдаст)
            for k in raw.keys():
                if k.startswith("_"):
                    continue
                # Skip purely English entries.
                # Пропускаем чисто английские
                if all(ord(c) < 128 or c in ' -' for c in k):
                    continue
                triggers.append(k)
        
        # Unique words with preserved order.
        # Уникальные слова, порядок сохранён
        all_words = list(dict.fromkeys(triggers + numerals))
        
        if not all_words:
            return ""
        
        prompt = ", ".join(all_words)
        # Whisper prompt is limited to about 224 tokens, so trim it if it gets too long.
        # Whisper prompt ограничен ~224 токена, обрезаем если слишком длинный
        if len(prompt) > 1200:
            prompt = prompt[:1200]
        
        print(f"[PROMPT] Загружено {len(triggers)} команд + {len(numerals)} числительных")
        return prompt
        
    except Exception as e:
        print(f"[PROMPT] Ошибка загрузки: {e}")
        return ""


# Cache the prompt on the first call to avoid rebuilding it for every recognition request.
# Кэшируем prompt при первом вызове, чтобы не собирать его заново для каждого распознавания.
_cached_prompt = None


def _get_commands_prompt():
    """Returns the cached prompt.
    Возвращает закэшированный prompt."""
    global _cached_prompt
    if _cached_prompt is None:
        _cached_prompt = _build_commands_prompt()
    return _cached_prompt


def invalidate_prompt_cache():
    """Clears the prompt cache; call after reload_commands().
    Сбрасывает кэш prompt — вызывать после reload_commands()."""
    global _cached_prompt
    _cached_prompt = None
    print("[PROMPT] Кэш сброшен")

# === Whisper server mode ===
# === Режим whisper-server ===

_server_process = None
_server_port = 8178
_server_lock = threading.Lock()
_server_model = None
_server_use_gpu = None


# === Automatic restart when the server crashes (GPU TDR, OOM, etc.) ===
# === Автоперезапуск при падении сервера (GPU TDR, OOM и т.п.) ===
_auto_restart_lock = threading.Lock()
_auto_restart_count = 0
_auto_restart_last_time = 0
_AUTO_RESTART_MAX = 3
_AUTO_RESTART_WINDOW = 300


def _is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _choose_server_port(preferred_port):
    if _is_port_available(preferred_port):
        return preferred_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        fallback_port = sock.getsockname()[1]

    print(f"[SERVER] ⚠️ Порт {preferred_port} занят, переключаюсь на {fallback_port}")
    return fallback_port

def _bind_child_to_parent(pid):
    """Windows: bind the child process so it dies with the parent.
    Windows: привязать дочерний процесс — умрёт вместе с родителем."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        # Create a Job Object.
        # Создаём Job Object
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return

        # Configure it to kill child processes when the Job closes.
        # Настраиваем: убивать дочерние при закрытии Job
        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        kernel32.SetInformationJobObject(
            job, 9,  # JobObjectExtendedLimitInformation
            ctypes.byref(info), ctypes.sizeof(info)
        )

        # Open the process and bind it.
        # Открываем процесс и привязываем
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
        if handle:
            kernel32.AssignProcessToJobObject(job, handle)
            # Do not close the job handle; it must live as long as the parent lives.
            # НЕ закрываем job handle — должен жить пока жив родитель

        print(f"[SERVER] 🔒 Привязан к родителю (Job Object)")
    except Exception as e:
        print(f"[SERVER] Job Object не удался: {e}")

def start_server(model_name="auto", use_gpu=True, port=8178):
    """Starts whisper-server in the background. The model is loaded once.
    Запускает whisper-server в фоне. Модель грузится 1 раз."""
    global _server_process, _server_port, _server_model, _server_use_gpu

    with _server_lock:
        port = _choose_server_port(port)
        _server_port = port

        if (_server_process and _server_process.poll() is None
                and _server_model == model_name
                and _server_use_gpu == use_gpu):
            if _check_server_health():
                print(f"[SERVER] Уже работает (модель: {model_name})")
                return True

        stop_server()

        bin_dir = BIN_DIR
        models_dir = MODELS_DIR

        server_exe = _find_server_exe(bin_dir, use_gpu)
        if not server_exe:
            print("[SERVER] ⚠️  whisper-server.exe не найден, будет subprocess")
            return False

        model_path = _resolve_model(models_dir, model_name)
        model_size_mb = model_path.stat().st_size / (1024 * 1024)
        threads = _get_optimal_threads(model_path.name)

        
        cmd = [
            str(server_exe),
            "-m", str(model_path),
            "--language", "ru",
            "--port", str(port),
            "--threads", str(threads),
        ]

        if not use_gpu:
            cmd.append("--no-gpu")

        print(f"[SERVER] Запуск: {server_exe}")
        print(f"[SERVER] Папка:  {server_exe.parent}")
        print(f"[SERVER] Модель: {model_path.name} ({model_size_mb:.0f} MB)")
        print(f"[SERVER] Порт:   {port}")
        print(f"[SERVER] GPU:    {'Да' if use_gpu else 'Нет'}")

        try:
            creationflags = 0
            if os.name == 'nt':
                CREATE_NO_WINDOW = 0x08000000
                creationflags = CREATE_NO_WINDOW

            env = os.environ.copy()
            if not use_gpu:
                env["CUDA_VISIBLE_DEVICES"] = ""

            _server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                env=env,
                cwd=str(server_exe.parent),
            )

            if _wait_for_server(timeout=30):
                _server_model = model_name
                _server_use_gpu = use_gpu
                _bind_child_to_parent(_server_process.pid)  # ← НОВОЕ
                mode = "GPU (VRAM)" if use_gpu else "CPU (RAM)"
                print(f"[SERVER] ✅ Готов! Модель в памяти — {mode}")
                return True
            else:
                print(f"[SERVER] ❌ Не запустился за 30 сек")
                stop_server()
                return False

        except Exception as e:
            print(f"[SERVER] Ошибка запуска: {e}")
            return False


def stop_server():
    """Останавливает whisper-server и ждёт освобождения порта."""
    global _server_process, _server_model, _server_use_gpu

    if _server_process:
        pid = _server_process.pid
        print(f"[SERVER] Останавливаю (PID {pid})...")
        try:
            _server_process.terminate()
            _server_process.wait(timeout=5)
            print(f"[SERVER] Остановлен корректно (PID {pid})")
        except subprocess.TimeoutExpired:
            print(f"[SERVER] terminate не помог, kill (PID {pid})")
            try:
                _server_process.kill()
                _server_process.wait(timeout=3)
            except Exception:
                pass
        except Exception:
            try:
                _server_process.kill()
            except Exception:
                pass
        _server_process = None
        _server_model = None
        _server_use_gpu = None

        # Give the TCP port a short grace period to close cleanly after shutdown.
        # Даём TCP-порту короткое время, чтобы он корректно освободился после остановки.
        for i in range(6):
            if not _check_server_health():
                break
            time.sleep(0.5)
        print("[SERVER] Порт свободен")

def restart_server(model_name="auto", use_gpu=True):
    """Перезапуск сервера (при смене модели/GPU)."""
    mode = "GPU" if use_gpu else "CPU"
    print(f"[SERVER] 🔄 Перезапуск → {mode} (модель: {model_name})")
    stop_server()
    time.sleep(1)
    result = start_server(model_name=model_name, use_gpu=use_gpu, port=_server_port)
    if result:
        print(f"[SERVER] ✅ Перезапуск на {mode} завершён")
    else:
        print(f"[SERVER] ⚠️ Перезапуск на {mode} не удался — будет subprocess fallback")
    return result



def _try_auto_restart():
    """Автоперезапуск упавшего сервера (после GPU TDR, OOM и т.п.).
    Возвращает True если сервер восстановлен."""
    global _auto_restart_count, _auto_restart_last_time

    with _auto_restart_lock:
        now = time.time()
        if now - _auto_restart_last_time > _AUTO_RESTART_WINDOW:
            _auto_restart_count = 0
        if _auto_restart_count >= _AUTO_RESTART_MAX:
            print(f"[SERVER] ⚠️ Лимит автоперезапусков ({_AUTO_RESTART_MAX}) — только subprocess")
            return False
        _auto_restart_count += 1
        _auto_restart_last_time = now
        attempt = _auto_restart_count

    # Save the current server settings before stop_server() clears them.
    # Сохраняем текущие параметры сервера до stop_server(), потому что он их обнулит.
    model = _server_model or "auto"
    gpu = _server_use_gpu if _server_use_gpu is not None else False

    print(f"\n[SERVER] 🔄 Автоперезапуск ({attempt}/{_AUTO_RESTART_MAX})...")

    if gpu:
        _wait_gpu_recovery()

    stop_server()
    time.sleep(1)

    success = start_server(model_name=model, use_gpu=gpu, port=_server_port)
    if success:
        print(f"[SERVER] ✅ Сервер восстановлен!")
    else:
        print(f"[SERVER] ❌ Автоперезапуск не удался — subprocess fallback")
    return success


def _wait_gpu_recovery(max_wait=20):
    """Ожидание восстановления GPU после сброса драйвера (TDR)."""
    print("[SERVER] ⏳ Ожидание GPU...")
    for i in range(max_wait // 2):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000 if os.name == 'nt' else 0,
            )
            if result.returncode == 0 and result.stdout.strip():
                print(f"[SERVER] ✅ GPU доступен ({(i + 1) * 2}с)")
                return True
        except Exception:
            pass
        time.sleep(2)
    print("[SERVER] ⚠️ GPU не отвечает — пробуем запуск")
    return False    


def is_server_running():
    """Проверяет работает ли сервер."""
    return (_server_process is not None
            and _server_process.poll() is None
            and _check_server_health())


def _find_server_exe(bin_dir, use_gpu=False):
    """Ищет whisper-server.exe."""
    if use_gpu:
        gpu_dir = bin_dir / "gpu"
        if gpu_dir.exists():
            candidate = gpu_dir / "whisper-server.exe"
            if candidate.exists():
                return candidate

    cpu_dir = bin_dir / "cpu"
    if cpu_dir.exists():
        candidate = cpu_dir / "whisper-server.exe"
        if candidate.exists():
            return candidate

    candidate = bin_dir / "whisper-server.exe"
    if candidate.exists():
        return candidate

    return None


def _check_server_health():
    """Проверяет здоровье сервера."""
    try:
        r = requests.get(f"http://127.0.0.1:{_server_port}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _wait_for_server(timeout=30):
    """Ждёт пока сервер станет доступен."""
    start = time.time()
    while time.time() - start < timeout:
        if _server_process and _server_process.poll() is not None:
            print(f"[SERVER] Процесс завершился с кодом {_server_process.returncode}")
            return False
        if _check_server_health():
            return True
        time.sleep(0.5)
    return False


def _transcribe_via_server(wav_path, language="ru"):
    """Распознавание через HTTP API сервера."""
    start_time = time.time()

    wav_path = Path(wav_path)
    if not wav_path.exists():
        return None

    file_size = wav_path.stat().st_size / 1024
    url = f"http://127.0.0.1:{_server_port}/inference"

    # Prompt helps mostly on short command-like clips; on long dictation it usually hurts.
    # Prompt в основном полезен на коротких командных фрагментах, а на длинной диктовке обычно мешает.
    try:    
        wav_size_kb = wav_path.stat().st_size / 1024
        prompt = _get_commands_prompt() if wav_size_kb < 200 else ""
        
        with open(wav_path, 'rb') as f:
            files = {'file': (wav_path.name, f, 'audio/wav')}
            data = {
                'language': language,
                'response_format': 'json',
                'temperature': '0.0',
                'beam_size': '5',
                'best_of': '5',
                'entropy_thold': '2.2',
                'no_speech_thold': '0.5',
            }
            # Attach the prompt only when the audio is short enough to resemble command speech.
            # Добавляем prompt только если запись короткая и похожа на командную речь.
            if prompt:
                data['prompt'] = prompt
            
            r = requests.post(url, files=files, data=data, timeout=60)

        elapsed = time.time() - start_time

        if r.status_code != 200:
            print(f"[SERVER] HTTP {r.status_code}: {r.text[:200]}")
            return None

        result = r.json()
        text = result.get('text', '').strip()


        print()
        print("┌─────────────────────────────────────────────┐")
        print("│           📊 РЕЗУЛЬТАТ (SERVER)             │")
        print("├─────────────────────────────────────────────┤")
        print(f"│ Время:      {elapsed:<6.2f} сек{'':<22}│")
        print(f"│ Аудио:      {file_size:<6.0f} KB{'':<23}│")
        print(f"│ Режим:      🚀 Сервер (модель в памяти){'':<4} │")
        print(f"│ Модель:     {_server_model or 'auto':<32}│")
        start_info = _format_start_info()
        print(f"│ Запуск:     {start_info:<32}│")        
        print("└─────────────────────────────────────────────┘")

        return text

    except requests.Timeout:
        print("[SERVER] Таймаут запроса (60 сек)")
        return None
    except requests.ConnectionError:
        print("[SERVER] Сервер недоступен")
        return None

# Controls whether the server stays resident or starts only on demand.
# Определяет, держим ли сервер постоянно в памяти или запускаем только по требованию.
_keep_server_alive = True


def set_keep_server_alive(value):
    """True = модель постоянно в памяти, False = загружать/выгружать по требованию."""
    global _keep_server_alive
    _keep_server_alive = value
    mode = "постоянно в памяти" if value else "по требованию"
    print(f"[SERVER] Режим: {mode}")


def transcribe_audio(wav_path, use_gpu=False, language="ru",
                     threads=0, model_name="auto"):
    """Приоритет: сервер → автоперезапуск при падении → subprocess fallback."""

    # On-demand mode starts the server for a single request and unloads it right after.
    # В режиме «по требованию» запускаем сервер на один запрос и сразу выгружаем его после.
    if not _keep_server_alive:
        return _transcribe_on_demand(wav_path, use_gpu, language, threads, model_name)

    # Keep-alive mode reuses the server only when it is healthy and already running in the requested mode.
    # В режиме «постоянно в памяти» переиспользуем сервер только если он жив и уже работает в нужном режиме.
    server_ok = (is_server_running()
                 and _server_use_gpu == use_gpu)

    # If the matching server should exist but crashed, try automatic recovery before falling back.
    # Если нужный сервер должен был быть запущен, но упал, сначала пробуем автоперезапуск.
    if not server_ok and _server_model is not None and _server_use_gpu == use_gpu:
        server_ok = _try_auto_restart()

    if server_ok:
        try:
            text = _transcribe_via_server(wav_path, language)
            if text is not None:
                return text
        except Exception as e:
            print(f"[SERVER] Ошибка: {e}")

        # A failed request may mean the server died during inference, so one restart attempt is still worthwhile.
        # Если запрос не удался, сервер мог упасть прямо во время инференса, поэтому ещё одна попытка перезапуска оправдана.
        if not is_server_running() and _try_auto_restart():
            try:
                text = _transcribe_via_server(wav_path, language)
                if text is not None:
                    return text
            except Exception:
                pass
        print("[SERVER] → Fallback на subprocess")
    elif is_server_running() and _server_use_gpu != use_gpu:
        # Do not reuse a server running in the wrong backend mode.
        # Сервер в другом режиме не переиспользуем.
        wrong_mode = "GPU" if _server_use_gpu else "CPU"
        right_mode = "GPU" if use_gpu else "CPU"
        print(f"[SERVER] ⚠️ Сервер в режиме {wrong_mode}, нужен {right_mode} → subprocess")

    # Final fallback is the legacy one-shot subprocess path.
    # Финальный fallback — старый одноразовый запуск через subprocess.
    return _transcribe_via_subprocess(
        wav_path, use_gpu, language, threads, model_name
    )

def _transcribe_on_demand(wav_path, use_gpu, language, threads, model_name):
    """Запускает сервер → распознаёт → выгружает."""
    server_started = False

    try:
        print("[SERVER] 📥 Загрузка модели (по требованию)...")
        t0 = time.time()
        server_started = start_server(model_name=model_name, use_gpu=use_gpu)
        t_load = time.time() - t0

        if server_started:
            print(f"[SERVER] ✅ Модель загружена за {t_load:.1f}с")
            try:
                text = _transcribe_via_server(wav_path, language)
                if text is not None:
                    return text
            except Exception as e:
                print(f"[SERVER] Ошибка: {e}")

        # If the temporary server path failed, fall back to the legacy CLI execution.
        # Если временный серверный путь не сработал, откатываемся на старый CLI-путь.
        return _transcribe_via_subprocess(
            wav_path, use_gpu, language, threads, model_name
        )

    finally:
        if server_started:
            print("[SERVER] 📤 Выгрузка модели (освобождение памяти)")
            stop_server()

def _transcribe_via_subprocess(wav_path, use_gpu=False, language="ru",
                               threads=0, model_name="auto"):
    """Старый способ — запуск whisper-cli.exe как процесс."""
    bin_dir = BIN_DIR
    models_dir = MODELS_DIR

    whisper_exe = _find_whisper_exe(bin_dir, use_gpu)
    model_path = _resolve_model(models_dir, model_name)

    model_size_mb = model_path.stat().st_size / (1024 * 1024)

    if threads <= 0:
        threads = _get_optimal_threads(model_path.name)

    timeout = _get_timeout(model_path.name, use_gpu)

    exe_type = _detect_exe_type(whisper_exe, bin_dir)
    print()
    print("┌─────────────────────────────────────────────┐")
    print("│           🔍 ДИАГНОСТИКА STT                │")
    print("├─────────────────────────────────────────────┤")
    print(f"│ exe:       {whisper_exe.name:<32}│")
    print(f"│ тип exe:   {exe_type[:32]:<32}│")
    print(f"│ модель:    {model_path.name:<32}│")
    print(f"│ размер:    {model_size_mb:<6.0f} MB{'':<23}│")
    print(f"│ потоки:    {threads:<32}│")
    print(f"│ таймаут:   {timeout} сек{'':<26}│")
    print(f"│ use_gpu:   {str(use_gpu):<32}│")

    if use_gpu:
        print(f"│ РЕЖИМ:     🟢 GPU (CUDA) -ngl 999{'':<10}│")
    else:
        print(f"│ РЕЖИМ:     🔵 CPU ONLY -ngl 0{'':<13}│")
        print(f"│            CUDA_VISIBLE_DEVICES=\"\"{'':<11}│")

    print("└─────────────────────────────────────────────┘")

    if use_gpu and "CPU" in exe_type:
        print("[⚠️] use_gpu=True, но exe — CPU-версия! Будет CPU.")

    # Build the exact whisper.cpp command line for this request.
    # Собираем точную команду whisper.cpp для текущего запроса.
    cmd = _build_command(whisper_exe, model_path, wav_path,
                         language, threads, model_size_mb, use_gpu)

    # Process environment can hard-disable GPU paths for CPU-only runs.
    # Через окружение процесса можно жёстко отключить GPU-пути для CPU-only запуска.
    env = os.environ.copy()
    if not use_gpu:
        # Some builds do not honor only --no-gpu, so block CUDA at process level too.
        # Некоторые сборки игнорируют один только --no-gpu, поэтому дополнительно блокируем CUDA на уровне процесса.
        env["CUDA_VISIBLE_DEVICES"] = ""
        env["GGML_CUDA_NO_PEER_COPY"] = "1"
        env["GGML_DISABLE_GPU"] = "1"             # Some builds honor this flag. / Некоторые сборки учитывают этот флаг.
        env["WHISPER_NO_GPU"] = "1"               # Extra safety for nonstandard builds. / Дополнительная страховка для нестандартных сборок.

    print(f"\n[STT] Команда: {' '.join(cmd[:6])}...")
    start_time = time.time()

    try:
        creationflags = 0
        if os.name == 'nt' and not use_gpu:
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            creationflags = BELOW_NORMAL_PRIORITY_CLASS

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=creationflags,
            env=env,
        )

        elapsed = time.time() - start_time
        stdout = result.stdout.decode('utf-8', errors='ignore')
        stderr = result.stderr.decode('utf-8', errors='ignore')

        hw_info = _analyze_hardware_info(stderr)

        print()
        print("┌─────────────────────────────────────────────┐")
        print("│           📊 РЕЗУЛЬТАТ STT                  │")
        print("├─────────────────────────────────────────────┤")
        print(f"│ Время:      {elapsed:<6.1f} сек{'':<22}│")
        print(f"│ Код выхода: {result.returncode:<32}│")
        print(f"│ Устройство: {hw_info['device']:<32}│")
        start_info = _format_start_info()
        print(f"│ Запуск:     {start_info:<32}│")
        if hw_info['backend']:
            bk = hw_info['backend'][:32]
            print(f"│ Backend:    {bk:<32}│")
        if hw_info['threads_used']:
            th = hw_info['threads_used'][:32]
            print(f"│ Потоков:    {th:<32}│")
        if hw_info['gpu_name']:
            gn = hw_info['gpu_name'][:32]
            print(f"│ GPU:        {gn:<32}│")

        # Cross-check which backend actually ran, not just what was requested.
        # Перепроверяем, какой backend реально отработал, а не только что было запрошено.
        if hw_info['is_gpu'] and not use_gpu:
            print(f"│ ❌ ПРОБЛЕМА: GPU работал при use_gpu=False! │")
            print(f"│    Нужна CPU-only сборка whisper.cpp       │")
        elif not hw_info['is_gpu'] and use_gpu:
            print(f"│ ⚠️  GPU запрошен, но работал CPU            │")
        elif hw_info['is_gpu']:
            print(f"│ ✅ ФАКТ:    Работало на GPU                │")
        else:
            print(f"│ ✅ ФАКТ:    Работало на CPU                │")

        print("└─────────────────────────────────────────────┘")

        # Print only diagnostically important stderr lines to keep logs readable.
        # Выводим только важные для диагностики строки stderr, чтобы не засорять лог.
        if stderr:
            for line in stderr.split('\n'):
                line = line.strip()
                if not line:
                    continue
                important = ['cuda', 'gpu', 'cpu', 'blas', 'openblas',
                             'thread', 'device', 'backend', 'system_info',
                             'ggml_cuda', 'ngl', 'no gpu', 'disabled']
                if any(kw in line.lower() for kw in important):
                    print(f"[STT stderr] {line}")

        if result.returncode != 0:
            if use_gpu:
                print("\n[STT] ⚠️  GPU fail → CPU fallback...")
                return transcribe_audio(wav_path, use_gpu=False,
                                        language=language, threads=threads,
                                        model_name=model_name)
            print(f"[STT] stderr:\n{stderr[:800]}")
            raise RuntimeError(f"whisper.cpp код {result.returncode}")

        text = _parse_whisper_output(stdout)

        if text:
            return text

        for txt_path in [Path(str(wav_path) + ".txt"),
                         Path(wav_path).with_suffix(".txt")]:
            if txt_path.exists():
                text = txt_path.read_text(encoding="utf-8",
                                          errors="ignore").strip()
                txt_path.unlink()
                if text:
                    return text

        return ""

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        raise RuntimeError(
            f"Таймаут ({elapsed:.0f}с > {timeout}с). "
            f"Модель '{model_path.name}' слишком тяжёлая для CPU.\n"
            f"Переключите на tiny или base."
        )


def _build_command(whisper_exe, model_path, wav_path,
                   language, threads, model_size_mb, use_gpu):
    # Prompt is reserved for short command-like clips; long dictation usually performs better without it.
    # Prompt используем только для коротких командных записей; на длинной диктовке обычно лучше без него.
    wav_size_kb = Path(wav_path).stat().st_size / 1024
    prompt = _get_commands_prompt() if wav_size_kb < 200 else ""
    
    cmd = [
        str(whisper_exe),
        "-m", str(model_path),
        "-f", str(wav_path),
        "--language", language,
        "--threads", str(threads),
        "--no-timestamps",
        "--print-progress",
    ]
    
    # Only attach the prompt when the clip stays within the command-oriented range.
    # Добавляем prompt только если длина записи остаётся в диапазоне командной речи.
    if prompt:
        cmd.extend(["--prompt", prompt])

    # Tune decoding quality by model size so CPU mode does not become unusably slow.
    # Подбираем параметры качества по размеру модели, чтобы CPU-режим не становился непригодно медленным.
    if use_gpu:
        # GPU mode can afford the highest decoding settings.
        # В GPU-режиме можно позволить себе максимальные параметры декодирования.
        cmd.extend([
            "--best-of", "5",
            "--beam-size", "5",
            "--entropy-thold", "2.2",
            "--no-speech-thold", "0.5",
            "--logprob-thold", "-1.0",
            "--temperature", "0.0",
            "--temperature-inc", "0.0",
        ])
    else:
        # CPU mode uses softer settings that scale down as models get larger.
        # В CPU-режиме используем более щадящие параметры, особенно для крупных моделей.
        if model_size_mb > 500:
            cmd.extend(["--best-of", "3", "--beam-size", "3",
                         "--entropy-thold", "2.2",
                         "--no-speech-thold", "0.5",
                         "--logprob-thold", "-1.0",
                         "--temperature", "0.0",
                         "--temperature-inc", "0.0"])
        elif model_size_mb > 100:
            cmd.extend(["--best-of", "2", "--beam-size", "2",
                         "--entropy-thold", "2.4",
                         "--no-speech-thold", "0.6",
                         "--temperature", "0.0",
                         "--temperature-inc", "0.2"])
        else:
            cmd.extend(["--best-of", "2", "--beam-size", "2",
                         "--entropy-thold", "2.6",
                         "--temperature", "0.0",
                         "--temperature-inc", "0.2"])

    # Finish the command with backend-specific switches.
    # Завершаем команду переключателями, зависящими от backend.
    if use_gpu:
        cmd.extend([
            "--flash-attn",
            "--no-fallback",
        ])
        print("[STT] 🟢 GPU: beam=5, temp=0.0 fixed, flash-attn")
    else:
        cmd.append("--no-gpu")
        print("[STT] 🔵 CPU: GPU отключён (--no-gpu)")
    return cmd


def _detect_exe_type(whisper_exe, bin_dir):
    # Inspect DLLs next to the executable because packaged layouts keep runtime dependencies there.
    # Смотрим DLL рядом с exe, потому что в packaged-раскладке runtime-зависимости лежат именно там.
    exe_dir = whisper_exe.parent
    cuda_dlls = (
        list(exe_dir.glob("cublas*.dll")) +
        list(exe_dir.glob("cublasLt*.dll")) +
        list(exe_dir.glob("cudart*.dll")) +
        list(exe_dir.glob("cudnn*.dll"))
    )
    openblas_dlls = list(exe_dir.glob("libopenblas*.dll"))

    exe_name = whisper_exe.name.lower()

    if "cuda" in exe_name or cuda_dlls:
        dll_names = [d.name for d in cuda_dlls[:3]]
        return f"CUDA ({', '.join(dll_names)})" if dll_names else "CUDA"

    if openblas_dlls:
        return "CPU + OpenBLAS"

    return "CPU-only"


def _analyze_hardware_info(stderr):
    info = {
        'device': 'неизвестно',
        'is_gpu': False,
        'gpu_name': '',
        'backend': '',
        'threads_used': '',
    }

    if not stderr:
        info['device'] = 'CPU (нет данных)'
        return info

    lines_lower = stderr.lower()

    # Look for markers of actual GPU execution, not just CUDA discovery.
    # Ищем маркеры реального использования GPU, а не просто обнаружения CUDA.
    gpu_usage_markers = [
        'using cuda',
        'whisper_backend_init_gpu: using',
        'cuda0 total size',
        'using metal',
        'using opencl',
        'using vulkan',
    ]

    # Markers that the process explicitly ran with GPU disabled.
    # Маркеры того, что процесс явно работал с отключённым GPU.
    gpu_disabled_markers = [
        'use gpu    = 0',
        'no gpu',
        'gpu disabled',
        'gpu_layers = 0',
        'ngl = 0',
    ]

    gpu_disabled = any(m in lines_lower for m in gpu_disabled_markers)

    if not gpu_disabled:
        for marker in gpu_usage_markers:
            if marker in lines_lower:
                info['is_gpu'] = True
                if 'cuda' in marker:
                    info['device'] = 'GPU (NVIDIA CUDA)'
                    info['backend'] = 'CUDA / cuBLAS'
                elif 'metal' in marker:
                    info['device'] = 'GPU (Apple Metal)'
                    info['backend'] = 'Metal'
                elif 'opencl' in marker:
                    info['device'] = 'GPU (OpenCL)'
                    info['backend'] = 'OpenCL'
                break

    # Some builds print explicit use_gpu=0/1 diagnostics; consume them too.
    # Некоторые сборки печатают явные диагностики вида use_gpu=0/1, тоже учитываем их.
    for line in stderr.split('\n'):
        ll = line.lower().strip()
        if 'use gpu' in ll:
            if '= 0' in ll or '= false' in ll or '= no' in ll:
                info['is_gpu'] = False
                info['device'] = 'CPU (GPU отключён -ngl 0)'
                info['backend'] = 'CPU'
            elif '= 1' in ll or '= true' in ll or '= yes' in ll:
                if not gpu_disabled:
                    info['is_gpu'] = True

    if not info['is_gpu']:
        info['device'] = 'CPU'
        if 'openblas' in lines_lower:
            info['backend'] = 'OpenBLAS'
        elif 'blas = 1' in lines_lower:
            info['backend'] = 'BLAS'
        elif 'blas = 0' in lines_lower:
            info['backend'] = 'без BLAS'
        if not info['backend']:
            info['backend'] = 'стандартный'

    # Extract the GPU model name when stderr exposes it.
    # Извлекаем имя модели GPU, если stderr его содержит.
    for line in stderr.split('\n'):
        ll = line.lower().strip()
        if 'device' in ll and ('nvidia' in ll or 'geforce' in ll or 'rtx' in ll):
            info['gpu_name'] = line.strip()[:50]

    # Extract the effective thread count when whisper.cpp reports it.
    # Извлекаем фактическое число потоков, если whisper.cpp его печатает.
    for line in stderr.split('\n'):
        if 'n_threads' in line.lower():
            info['threads_used'] = line.strip()[:60]
            break

    return info


def _resolve_model(models_dir, model_name):
    if model_name and model_name != "auto":
        model_path = models_dir / model_name
        if model_path.exists():
            return model_path
        print(f"[STT] ⚠️  '{model_name}' не найдена")

    return _find_best_model(models_dir)


def _find_whisper_exe(bin_dir, use_gpu=False):
    if use_gpu:
        gpu_dir = bin_dir / "gpu"
        if gpu_dir.exists():
            for name in ["whisper-cli.exe", "main.exe"]:
                candidate = gpu_dir / name
                if candidate.exists():
                    return candidate

    # CPU mode first searches in cpu/, then falls back to the historical bin/ layout.
    # Для CPU сначала ищем бинарник в cpu/, потом откатываемся к старой схеме в bin/.
    cpu_dir = bin_dir / "cpu"
    if cpu_dir.exists():
        for name in ["whisper-cli.exe", "main.exe"]:
            candidate = cpu_dir / name
            if candidate.exists():
                return candidate

    # Backward compatibility for older layouts that stored binaries directly in bin/.
    # Обратная совместимость для старых раскладок, где бинарники лежали прямо в bin/.
    for name in ["whisper-cli.exe", "main.exe", "whisper.cpp.exe", "whisper.exe"]:
        candidate = bin_dir / name
        if candidate.exists():
            return candidate

    exes = list(bin_dir.glob("*.exe"))
    if exes:
        return exes[0]

    raise FileNotFoundError(f"Не найден whisper exe в {bin_dir}")


def _find_best_model(models_dir):
    from model_selector import MODEL_PRIORITY
    for name in MODEL_PRIORITY:
        candidate = models_dir / name
        if candidate.exists():
            return candidate

    bins = list(models_dir.glob("ggml-*.bin"))
    if bins:
        bins.sort(key=lambda p: p.stat().st_size, reverse=True)
        return bins[0]

    raise FileNotFoundError(f"Модели не найдены в {models_dir}")


def _get_optimal_threads(model_name):
    cpu_count = os.cpu_count() or 4
    if "large" in model_name:
        return min(cpu_count, 8)
    elif "medium" in model_name:
        return min(cpu_count, 6)
    else:
        return min(cpu_count, 4)


def _get_timeout(model_name, use_gpu):
    if use_gpu:
        return 60
    if "large" in model_name:
        return 300  # Large models on CPU can take a long time. / Крупные модели на CPU работают долго.
    elif "medium" in model_name:
        return 180
    elif "small" in model_name:
        return 120
    else:
        return 60


def _parse_whisper_output(stdout):
    if not stdout:
        return ""

    lines = stdout.strip().split("\n")
    text_parts = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        skip_prefixes = (
            "whisper_", "WARNING", "CUDA", "ggml",
            "system_info", "main:", "output_",
            "log_", "process_", "encoder_",
        )
        if any(line.startswith(p) for p in skip_prefixes):
            continue

        if "]" in line and ("-->" in line or ":" in line):
            text_part = line.split("]", 1)[-1].strip()
            if text_part:
                text_parts.append(text_part)
        else:
            text_parts.append(line)

    result = " ".join(text_parts).strip()

    return result


def warmup_model(model_name="auto", use_gpu=False):
    """Прогрев: запускает сервер (модель остаётся в памяти)."""
    # Prefer server warmup because it leaves the model resident in memory for the next request.
    # Для прогрева сначала пробуем серверный путь, потому что он оставляет модель загруженной в памяти.
    success = start_server(model_name=model_name, use_gpu=use_gpu)
    if success:
        return True

    # If the server path is unavailable, fall back to the legacy CLI warmup.
    # Если серверный путь недоступен, откатываемся на старый прогрев через CLI.
    bin_dir = BIN_DIR
    models_dir = MODELS_DIR
    temp_wav_handle = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
        prefix="vox_bee_warmup_",
    )
    temp_wav_handle.close()
    temp_wav = Path(temp_wav_handle.name)

    try:
        whisper_exe = _find_whisper_exe(bin_dir, use_gpu)
        model_path = _resolve_model(models_dir, model_name)

        import wave
        sample_rate = 16000
        samples = int(sample_rate * 0.5)
        with wave.open(str(temp_wav), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b'\x00\x00' * samples)

        prompt = _get_commands_prompt()
        
        cmd = [
            str(whisper_exe),
            "-m", str(model_path),
            "-f", str(temp_wav),
            "--language", "ru",
            "--threads", str(min(os.cpu_count() or 4, 4)),
            "--no-timestamps",
        ]
        
        if prompt:
            cmd.extend(["--prompt", prompt])
        
        if not use_gpu:
            cmd.append("--no-gpu")

        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        return True

    except Exception as e:
        print(f"[WARMUP] Ошибка: {e}")
        return False
    finally:
        if temp_wav.exists():
            temp_wav.unlink()
