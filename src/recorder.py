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

import sounddevice as sd
import numpy as np
import wave
import threading
import time
from pathlib import Path
from collections import deque


class AudioRecorder:
    """
    Keeps the microphone stream open.
    Держит поток микрофона постоянно открытым.

    Reconnects automatically when the device disappears.
    Автоматически переподключается при потере устройства.

    Searches only for the original device or the system default fallback.
    Ищет только исходное устройство или системный fallback по умолчанию.
    """

    # Virtual devices must never replace a real microphone during recovery.
    # Виртуальные устройства нельзя использовать как замену реальному микрофону при восстановлении.
    VIRTUAL_DEVICES = [
        "cable", "vb-audio", "virtual", "voicemeeter",
        "stereo mix", "wave out", "loopback",
        "what u hear", "переназначение",
        # Windows may expose phantom Bluetooth endpoints that report input but deliver no data.
        # Windows может показывать фантомные Bluetooth-устройства, у которых есть вход, но нет реальных данных.
        "@system32", "bthhfenum", "hands-free ag",
    ]

    def __init__(self, sample_rate=16000, channels=1,
                 pre_buffer_sec=0.5, max_duration_sec=180,
                 device_index=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.pre_buffer_sec = pre_buffer_sec
        self.pre_buffer_samples = int(sample_rate * pre_buffer_sec)
        self.device_index = device_index

        self.max_duration_sec = max_duration_sec
        self.max_samples = int(sample_rate * max_duration_sec)

        self.is_capturing = False
        self.is_running = False
        self.audio_data = []
        self.ring_buffer = []
        self.ring_buffer = deque()
        self._lock = threading.Lock()
        self.stream = None

        # Voice activity detection state.
        # Состояние voice activity detection.
        self.vad_mode = False
        self.vad_recording = False
        self._vad_callback = None
        self._chunk_count = 0
        self._warned = False
        # Optional noise filter applied before saving audio to disk.
        # Необязательный фильтр шума, применяемый перед сохранением на диск.
        self.noise_filter = None
   
        # === Watchdog state ===
        # === Состояние watchdog ===
        self._last_callback_time = 0
        self._watchdog_thread = None
        self._watchdog_running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 50
        self._watchdog_interval = 2.0
        self._silence_timeout = 5.0
        self._reconnect_cooldown = 3.0

        # === Silent-zero-stream detection ===
        # === Детекция нулевого потока ===
        self._last_nonzero_time = 0
        self._consecutive_zero_chunks = 0
        self._zero_energy_threshold = 0.000003  # Below any realistic microphone noise floor. / Ниже шумового порога любого реального микрофона.
        self._zero_stream_timeout = 10.0  # Seconds of zero data before reconnect. / Сколько секунд нулевых данных ждём до переподключения.

        # Preserve the original target device so recovery prefers it over random replacements.
        # Запоминаем исходное устройство, чтобы при восстановлении предпочитать именно его.
        self._original_device_index = device_index
        self._original_device_name = ""
        self._device_lost = False
        self._phantom_devices = set()  # Session-local phantom device blacklist. / Чёрный список фантомных устройств в пределах сессии.

        self._original_hostapi = None  # Original HostAPI used for recovery priority. / HostAPI исходного устройства для приоритизации восстановления.
        # Preference search state for returning to the original microphone.
        # Состояние поиска, которое возвращает нас к исходному микрофону.
        self._device_pending = False
        self._pending_check_interval = 15  # Check every ~30 seconds with the default watchdog interval. / Проверяем примерно каждые 30 секунд.
        self._pending_check_counter = 0        

        # Optional callbacks for UI state updates.
        # Необязательные callback'и для обновления состояния UI.
        self.on_device_lost = None
        self.on_device_restored = None

    def set_device(self, device_index, device_name=None):
        """Sets the microphone and optionally resolves its fresh index by name.
        Устанавливает микрофон и при необходимости заново ищет его актуальный индекс по имени."""
        was_running = self.is_running
        if was_running:
            self.stop_listening()
            time.sleep(0.3)

        # Resolve by name because Windows can renumber devices after reconnects.
        # Если передано имя, заново ищем индекс, потому что Windows может его поменять после переподключения.
        if device_name:
            resolved = self._resolve_index_by_name(device_name, hint_index=device_index)
            if resolved is not None:
                device_index = resolved
            else:
                print(f"[MIC] ⚠️ '{device_name}' не найден в текущем списке устройств")

        self.device_index = device_index
        self._original_device_index = device_index
        self._original_device_name = device_name or self._get_device_name_by_index(device_index)
        self._reconnect_attempts = 0
        self._device_lost = False
        self._device_pending = False
        self._original_hostapi = None  # Reset because the new microphone may live on another API. / Сбрасываем, потому что новый микрофон может быть на другом API.

        if device_index is not None:
            try:
                dev_info = sd.query_devices(device_index)
                print(f"[MIC] Устройство: [{device_index}] {dev_info['name']}")
            except Exception as e:
                print(f"[MIC] Ошибка устройства #{device_index}: {e}")
                self.device_index = None

        if was_running:
            self.start_listening()



    def set_noise_filter(self, noise_filter):
        """Устанавливает фильтр шума."""
        self.noise_filter = noise_filter
        print(f"[MIC] Шумоподавление: {'ВКЛ' if noise_filter else 'ВЫКЛ'}")        

    def _callback(self, indata, frames, time_info, status):
        if status:
            status_str = str(status)
            if any(err in status_str.lower() for err in
                   ['input overflow', 'input underflow',
                    'priming', 'device unavailable']):
                print(f"[AUDIO ⚠️] {status}")
            else:
                print(f"[AUDIO] {status}")

        chunk = indata.copy()
        self._chunk_count += 1
        self._last_callback_time = time.time()

        # Track energy so the watchdog can detect streams that are alive but emit only zeros.
        # Отслеживаем энергию, чтобы watchdog видел поток, который жив, но отдаёт только нули.
        energy = np.sqrt(np.mean(chunk ** 2))
        if energy > self._zero_energy_threshold:
            self._last_nonzero_time = time.time()
            self._consecutive_zero_chunks = 0
        else:
            self._consecutive_zero_chunks += 1

        if self._chunk_count % 125 == 0:
            dev_name = f"dev={self.device_index}" if self.device_index is not None else "dev=default"
            zero_info = ""
            if self._consecutive_zero_chunks > 100:
                zero_info = f", ⚠️ zero_chunks={self._consecutive_zero_chunks}"
            print(f"[MIC] alive, chunks={self._chunk_count}, energy={energy:.5f}, {dev_name}{zero_info}")

        with self._lock:
            if self.is_capturing or self.vad_recording:
                current_samples = sum(len(c) for c in self.audio_data)
                if current_samples < self.max_samples:
                    self.audio_data.append(chunk)
                elif not self._warned:
                    self._warned = True
                    print(f"[⚠️ REC] Лимит записи достигнут")
            else:
                self.ring_buffer.append(chunk)
                total_samples = sum(len(c) for c in self.ring_buffer)
                while total_samples > self.pre_buffer_samples and len(self.ring_buffer) > 1:
                     removed = self.ring_buffer.popleft()
                     total_samples -= len(removed)

        if self.vad_mode and self._vad_callback:
            try:
                self._vad_callback(chunk)
            except Exception as e:
                print(f"[VAD CALLBACK ERROR] {e}")

    def _make_resample_callback(self, native_rate):
        """Создаёт callback с ресемплингом из native_rate в self.sample_rate."""
        from scipy.signal import resample_poly
        from math import gcd

        target_rate = self.sample_rate
        g = gcd(native_rate, target_rate)
        up = target_rate // g
        down = native_rate // g

        def _resampling_callback(indata, frames, time_info, status):
            if status:
                status_str = str(status)
                if any(err in status_str.lower() for err in
                       ['input overflow', 'input underflow',
                        'priming', 'device unavailable']):
                    print(f"[AUDIO ⚠️] {status}")
                else:
                    print(f"[AUDIO] {status}")

            # Resample into the target Whisper sample rate when the device rejects 16 kHz directly.
            # Ресемплируем в целевую частоту Whisper, если устройство не принимает 16 кГц напрямую.
            resampled = resample_poly(indata[:, 0], up, down).astype(np.float32)
            chunk = resampled.reshape(-1, 1)

            self._chunk_count += 1
            self._last_callback_time = time.time()

            energy = np.sqrt(np.mean(chunk ** 2))
            if energy > self._zero_energy_threshold:
                self._last_nonzero_time = time.time()
                self._consecutive_zero_chunks = 0
            else:
                self._consecutive_zero_chunks += 1

            if self._chunk_count % 125 == 0:
                dev_name = f"dev={self.device_index}" if self.device_index is not None else "dev=default"
                print(f"[MIC] alive, chunks={self._chunk_count}, energy={energy:.5f}, {dev_name}")

            with self._lock:
                if self.is_capturing or self.vad_recording:
                    current_samples = sum(len(c) for c in self.audio_data)
                    if current_samples < self.max_samples:
                        self.audio_data.append(chunk)
                    elif not self._warned:
                        self._warned = True
                        print(f"[⚠️ REC] Лимит записи достигнут")
                else:
                    self.ring_buffer.append(chunk)
                    total_samples = sum(len(c) for c in self.ring_buffer)
                    while total_samples > self.pre_buffer_samples and len(self.ring_buffer) > 1:
                        removed = self.ring_buffer.popleft()
                        total_samples -= len(removed)

            if self.vad_mode and self._vad_callback:
                try:
                    self._vad_callback(chunk)
                except Exception as e:
                    print(f"[VAD CALLBACK ERROR] {e}")

        return _resampling_callback


    def start_listening(self):
        if self.is_running:
            return

        if self.device_index is None:
            print("[MIC] ❌ Микрофон не выбран. Выберите микрофон в трее.")
            return

        self.is_running = True
        self._chunk_count = 0
        self._reconnect_attempts = 0
        self._device_lost = False
        self._consecutive_zero_chunks = 0
        self._last_nonzero_time = time.time()

        if not self._original_device_name:
            self._original_device_name = self._get_device_name_by_index(self.device_index)

        success = self._open_stream()

        # If opening failed, try to re-resolve the device by name because its index may have changed.
        # Если поток не открылся, пытаемся заново найти устройство по имени: индекс мог измениться.
        reindexed = False
        if not success and self._original_device_name:
            print(f"[MIC] 🔄 Переиндексация: '{self._original_device_name}'")
            try:
                sd._terminate()
                sd._initialize()
            except Exception:
                pass
            time.sleep(0.3)

            resolved = self._resolve_index_by_name(
                self._original_device_name,
                hint_index=self.device_index
            )
            if resolved is not None and resolved != self.device_index:
                self.device_index = resolved
                self._original_device_index = resolved
                success = self._open_stream()
                reindexed = success

        if success:
            self._start_watchdog()
            # Notify config/UI only when recovery actually moved to a new index.
            # Обновляем конфиг через callback только если реально перешли на новый индекс.
            if reindexed and self.on_device_restored:
                try:
                    self.on_device_restored()
                except Exception:
                    pass
        else:
            # Keep the watchdog alive so it can continue background recovery attempts.
            # Watchdog остаётся активным и продолжит искать устройство в фоне.
            print(f"[MIC] ⚠️ Микрофон недоступен — watchdog будет искать")
            self._device_lost = True
            self._start_watchdog()

    def stop_listening(self):
        self.is_running = False
        self.is_capturing = False
        self.vad_recording = False
        self._stop_watchdog()
        self._close_stream()
        print("[MIC] Микрофон закрыт")

    def _open_stream(self):
        """Открывает аудио поток. Fallback при ошибке sample rate."""
        dev_name = self._get_device_name()

        try:
            if self.device_index is not None:
                try:
                    dev_info = sd.query_devices(self.device_index)
                    if dev_info['max_input_channels'] < 1:
                        print(f"[MIC] ❌ [{self.device_index}] нет входных каналов")
                        return False
                except Exception as e:
                    print(f"[MIC] ❌ [{self.device_index}] недоступен: {e}")
                    return False

            # First try the requested Whisper rate directly.
            # Сначала пробуем открыть поток на целевой частоте Whisper.
            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    callback=self._callback,
                    dtype='float32',
                    blocksize=512,
                    latency='low',
                    device=self.device_index,
                )
                self.stream.start()
            except sd.PortAudioError as e:
                if '-9997' in str(e) or 'sample rate' in str(e).lower():
                    # Some WASAPI devices reject 16 kHz, so reopen them at the native rate with resampling.
                    # Некоторые WASAPI-устройства не принимают 16 кГц, поэтому переоткрываем их на нативной частоте с ресемплингом.
                    print(f"[MIC] ⚠️ {self.sample_rate}Hz не поддерживается, пробую нативную...")
                    native_rate = None
                    try:
                        dev_info = sd.query_devices(self.device_index)
                        native_rate = int(dev_info['default_samplerate'])
                    except Exception:
                        pass

                    if native_rate and native_rate != self.sample_rate:
                        self.stream = sd.InputStream(
                            samplerate=native_rate,
                            channels=self.channels,
                            callback=self._make_resample_callback(native_rate),
                            dtype='float32',
                            blocksize=int(512 * native_rate / self.sample_rate),
                            device=self.device_index,
                        )
                        self.stream.start()
                        print(f"[MIC] ✅ Открыт с ресемплингом: {native_rate}Hz → {self.sample_rate}Hz")
                    else:
                        raise
                else:
                    raise

            self._last_callback_time = time.time()
            self._last_nonzero_time = time.time()
            self._consecutive_zero_chunks = 0

            print(f"[MIC] ✅ Открыт: {dev_name}")
            print(f"[MIC]    Pre-buffer: {self.pre_buffer_sec}с, "
                  f"лимит: {self.max_duration_sec}с")

            # Remember the working HostAPI so reconnect prefers the same backend later.
            # Запоминаем рабочий HostAPI, чтобы при переподключении предпочитать тот же backend.
            if self.device_index is not None and self._original_hostapi is None:
                try:
                    dev_info = sd.query_devices(self.device_index)
                    hostapi_info = sd.query_hostapis(dev_info['hostapi'])
                    self._original_hostapi = hostapi_info['name'].lower()
                    print(f"[MIC] 📌 HostAPI: {hostapi_info['name']}")
                except Exception:
                    pass

            self._reconnect_attempts = 0
            return True

        except Exception as e:
            print(f"[MIC ERROR] ❌ {e}")
            self.stream = None
            return False

    def _close_stream(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    # === Device naming ===
    # === Имена устройств ===

    def _get_device_name(self):
        """Returns a readable name for the current device.
        Возвращает читаемое имя текущего устройства."""
        return self._get_device_name_by_index(self.device_index)

    def _get_device_name_by_index(self, device_index):
        """Looks up a device name by index.
        Получает имя устройства по индексу."""
        if device_index is not None:
            try:
                dev_info = sd.query_devices(device_index)
                return dev_info['name']
            except Exception:
                return f"[{device_index}] ???"
        else:
            try:
                default_idx = sd.default.device[0]
                dev_info = sd.query_devices(default_idx)
                return dev_info['name']
            except Exception:
                return "системный"


    def _resolve_index_by_name(self, device_name, hint_index=None):
        """
        Resolves the current device index from its name.
        Ищет актуальный индекс устройства по имени.

        hint_index используется для дополнительной проверки, но НЕ как результат.
        hint_index используется только как подсказка для сравнения и не возвращается автоматически.

        Возвращает индекс или None если не найдено.
        Возвращает индекс или None, если устройство не найдено.
        """
        try:
            devices = sd.query_devices()
            name_lower = device_name.lower()

            # Exact name match is the safest option.
            # Точное совпадение имени — самый надёжный вариант.
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and
                        dev['name'].lower() == name_lower):
                    if i != hint_index:
                        print(f"[MIC] Индекс обновлён: [{hint_index}] → [{i}] (имя: '{device_name}')")
                    return i

            # Fall back to the first 20 characters because some APIs truncate names.
            # В fallback сравниваем первые 20 символов, потому что некоторые API обрезают имена.
            prefix = name_lower[:20]
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and
                        dev['name'].lower()[:20] == prefix):
                    print(f"[MIC] Похожее: [{i}] '{dev['name']}' (искал '{device_name}')")
                    return i

        except Exception as e:
            print(f"[MIC] Ошибка поиска по имени: {e}")

        return None                

    def _is_virtual_device(self, device_name):
        """Checks whether a device name belongs to a virtual endpoint.
        Проверяет, относится ли имя устройства к виртуальному endpoint'у."""
        name_lower = device_name.lower()
        return any(v in name_lower for v in self.VIRTUAL_DEVICES)

    # === Watchdog ===
    # === Watchdog ===

    def _start_watchdog(self):
        if self._watchdog_running:
            return
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="mic-watchdog"
        )
        self._watchdog_thread.start()
        print("[WATCHDOG] 🐕 Мониторинг микрофона запущен")

    def _stop_watchdog(self):
        self._watchdog_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)
            self._watchdog_thread = None

    def _watchdog_loop(self):
        while self._watchdog_running and self.is_running:
            time.sleep(self._watchdog_interval)

            if not self.is_running:
                break

            now = time.time()
            elapsed = now - self._last_callback_time

            stream_alive = False
            if self.stream is not None and elapsed < self._silence_timeout:
                try:
                    stream_alive = self.stream.active
                except Exception:
                    stream_alive = False

            if stream_alive and not self._device_lost:
                # === ДЕТЕКЦИЯ "ТИХОЙ СМЕРТИ" ===
                # The stream object is alive, but the device may be feeding zeros only.
                # Поток жив, но устройство может отдавать только нули.
                if self._is_zero_stream():
                    zero_dur = now - self._last_nonzero_time
                    if zero_dur > self._zero_stream_timeout:
                        print(f"\n[WATCHDOG] ⚠️  Микрофон отдаёт нули уже {zero_dur:.0f}с — переподключение!")
                        self._device_lost = True
                        if self.on_device_lost:
                            try:
                                self.on_device_lost()
                            except Exception:
                                pass
                        self._try_reconnect()
                        time.sleep(self._reconnect_cooldown)
                        continue

                # The stream is fine, but we may still be sitting on a fallback microphone.
                # Поток работает, но мы всё ещё можем висеть на fallback-устройстве.
                if self._device_pending:
                    self._pending_check_counter += 1
                    if self._pending_check_counter >= self._pending_check_interval:
                        self._pending_check_counter = 0
                        self._try_switch_to_preferred()
                continue

            if stream_alive and self._device_lost:
                # The stream came back, but accept it only after non-zero audio resumes.
                # Поток восстановился, но принимаем его только после возврата реальных данных.
                if not self._is_zero_stream():
                    print(f"[WATCHDOG] ✅ Микрофон восстановлен!")
                    self._device_lost = False
                    self._reconnect_attempts = 0
                    if self.on_device_restored:
                        try:
                            self.on_device_restored()
                        except Exception:
                            pass
                    continue
                else:
                    # A live-but-silent stream still counts as broken, so keep reconnecting.
                    # Если поток живой, но молчит нулями, продолжаем переподключение.
                    pass

            # Recovery path: either the stream stopped or callbacks went silent for too long.
            # Переходим в восстановление, если поток умер или callback'и слишком долго молчат.
            if not self._device_lost:
                # Only announce the loss once when we enter the degraded state.
                # Сообщаем о потере только один раз, в момент входа в аварийное состояние.
                self._device_lost = True
                if elapsed >= self._silence_timeout:
                    reason = f"нет данных {elapsed:.0f}с"
                elif self.stream is None:
                    reason = "stream = None"
                else:
                    try:
                        is_active = self.stream.active
                        reason = "stream неактивен" if not is_active else "неизвестно"
                    except Exception:
                        reason = "stream невалиден"

                print(f"\n[WATCHDOG] ⚠️  Микрофон потерян! ({reason})")
                print(f"[WATCHDOG] 🔍 Ищу: '{self._original_device_name}'")

                if self.on_device_lost:
                    try:
                        self.on_device_lost()
                    except Exception:
                        pass

            # Each watchdog cycle performs one reconnect attempt until the limit is reached.
            # На каждом цикле watchdog делаем одну попытку переподключения, пока не упрёмся в лимит.
            self._reconnect_attempts += 1

            if self._reconnect_attempts > self._max_reconnect_attempts:
                print(f"[WATCHDOG] ❌ Лимит попыток ({self._max_reconnect_attempts})")
                print(f"[WATCHDOG] 💡 Переподключите микрофон и перезапустите")
                self._watchdog_running = False
                break

            if self._reconnect_attempts % 5 == 1:
                # Log every fifth attempt to keep the output readable.
                # Логируем каждую пятую попытку, чтобы не засорять вывод.
                print(f"[WATCHDOG] 🔄 Попытка {self._reconnect_attempts}... "
                      f"(ищу '{self._original_device_name}')")

            self._try_reconnect()
            time.sleep(self._reconnect_cooldown)

        print("[WATCHDOG] 🐕 Мониторинг остановлен")

    def _try_reconnect(self):
        """Attempts to reconnect specifically to the original microphone.
        Пытается переподключиться именно к исходному микрофону."""
        self._close_stream()
        time.sleep(0.5)

        # Refresh the device list so PortAudio sees hot-plugged changes.
        # Обновляем список устройств, чтобы PortAudio увидел изменения после hot-plug.
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass
        time.sleep(0.3)

        # Prefer the original device instead of silently drifting to any random input.
        # В первую очередь ищем исходное устройство, а не уходим на случайный вход.
        found_index = self._find_original_device()

        if found_index is None:
            # If the device is still missing, keep waiting and try again later.
            # Если устройство не найдено, продолжаем ждать и попробуем позже.
            if self._reconnect_attempts % 10 == 0:
                print(f"[WATCHDOG] ⏳ Жду '{self._original_device_name}'...")
                self._print_available_real_mics()
            return

        # Once found, reopen the stream and verify that real data starts flowing.
        # Если устройство нашли, открываем поток и проверяем, что пошли реальные данные.
        self.device_index = found_index
        success = self._open_stream()

        if not success:
            print(f"[WATCHDOG] ❌ Не удалось открыть [{found_index}]")
            return

        # Do not trust an opened stream until it produces several callbacks.
        # Не считаем поток рабочим, пока он не отдал несколько callback'ов с данными.
        print(f"[WATCHDOG] ⏳ Проверяю данные от [{found_index}]...")
        data_received = False
        check_start = time.time()
        initial_chunks = self._chunk_count

        while time.time() - check_start < 3.0:
            time.sleep(0.3)
            if self._chunk_count > initial_chunks + 5:
                data_received = True
                break

        if data_received:
            print(f"[WATCHDOG] ✅ Переподключено к [{found_index}]!")
            self._device_lost = False
            if self.on_device_restored:
                try:
                    self.on_device_restored()
                except Exception:
                    pass
        else:
            print(f"[WATCHDOG] ⚠️  [{found_index}] открылся, но данных нет — фантом")
            self._close_stream()
            # Blacklist the device for this session so the watchdog does not loop on the same phantom endpoint.
            # Помечаем устройство как фантомное в рамках сессии, чтобы watchdog не зациклился на нём.
            self._mark_device_as_phantom(found_index)

    def _try_switch_to_preferred(self):
        """Checks whether the preferred original device returned and switches back to it.
        Проверяет, вернулось ли исходное предпочтительное устройство, и переключается на него."""
        if not self._original_device_name:
            self._device_pending = False
            return

        print(f"[WATCHDOG] 🔍 Ищу '{self._original_device_name}'...")

        # Close the fallback stream before re-scanning devices.
        # Перед повторным поиском закрываем текущий fallback-поток.
        self._close_stream()
        time.sleep(0.3)

        # Refresh PortAudio state before looking for the original microphone again.
        # Перед новым поиском обновляем состояние PortAudio.
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass
        time.sleep(0.3)

        # Search for the preferred original device again.
        # Снова ищем предпочтительное исходное устройство.
        found_index = self._find_original_device()

        if found_index is not None:
            # If found, switch back and verify that callbacks resume.
            # Если нашли, переключаемся обратно и проверяем, что callback'и снова идут.
            self.device_index = found_index
            self._device_pending = False
            if self._open_stream():
                time.sleep(0.5)
                if self._last_callback_time > time.time() - 2.0:
                    print(f"[WATCHDOG] ✅ Переключился на [{found_index}] "
                          f"'{self._original_device_name}'")
                    if self.on_device_restored:
                        try:
                            self.on_device_restored()
                        except Exception:
                            pass
                    return
                else:
                    self._close_stream()

        # If the original device is still absent, reopen the best real default microphone.
        # Если исходное устройство не вернулось, заново открываем лучший реальный default-микрофон.
        fallback = self._find_default_real_mic()
        self.device_index = fallback
        self._open_stream()
        print(f"[WATCHDOG] ⏳ '{self._original_device_name}' не найден, жду...")

    def _find_original_device(self):
        """
        Finds the original device by name and HostAPI.
        Priority: same HostAPI first, then any other match.

        Ищет исходное устройство по имени и HostAPI.
        Приоритет: сначала тот же HostAPI, затем любой другой совпадающий вариант.
        """
        if not self._original_device_name:
            return self._find_default_real_mic()

        original_lower = self._original_device_name.lower()

        try:
            devices = sd.query_devices()
            
            # Separate matches by HostAPI so reconnect prefers the original backend.
            # Разделяем кандидатов по HostAPI, чтобы при восстановлении предпочитать исходный backend.
            same_api = []
            other_api = []

            # Exact name match.
            # Точное совпадение имени.
            for i, dev in enumerate(devices):
                if i in self._phantom_devices:
                    continue
                if (dev['max_input_channels'] > 0 and
                        dev['name'].lower() == original_lower and
                        not self._is_virtual_device(dev['name'])):
                    
                    # Keep same-API matches ahead of cross-API fallbacks.
                    # Совпадения на том же API держим выше fallback-вариантов с другого API.
                    try:
                        hostapi_info = sd.query_hostapis(dev['hostapi'])
                        hostapi_name = hostapi_info['name'].lower()
                        
                        if self._original_hostapi and hostapi_name == self._original_hostapi:
                            same_api.append(i)
                        else:
                            other_api.append(i)
                    except Exception:
                        other_api.append(i)

            if same_api:
                idx = same_api[0]
                print(f"[WATCHDOG] 🎯 Точное совпадение (тот же API): [{idx}] {self._original_device_name}")
                return idx
            
            if other_api:
                idx = other_api[0]
                print(f"[WATCHDOG] 🎯 Точное совпадение (другой API): [{idx}] {self._original_device_name}")
                return idx

            # Prefix match for APIs that truncate device names.
            # Совпадение по префиксу на случай API, которые обрезают имя устройства.
            same_api.clear()
            other_api.clear()
            original_prefix = original_lower[:20]
            
            for i, dev in enumerate(devices):
                if i in self._phantom_devices:
                    continue
                if (dev['max_input_channels'] > 0 and
                        dev['name'].lower()[:20] == original_prefix and
                        not self._is_virtual_device(dev['name'])):
                    
                    try:
                        hostapi_info = sd.query_hostapis(dev['hostapi'])
                        hostapi_name = hostapi_info['name'].lower()
                        
                        if self._original_hostapi and hostapi_name == self._original_hostapi:
                            same_api.append(i)
                        else:
                            other_api.append(i)
                    except Exception:
                        other_api.append(i)

            if same_api:
                idx = same_api[0]
                print(f"[WATCHDOG] 🔍 Похожее (тот же API): [{idx}] {devices[idx]['name']}")
                return idx
            
            if other_api:
                idx = other_api[0]
                print(f"[WATCHDOG] 🔍 Похожее (другой API): [{idx}] {devices[idx]['name']}")
                return idx

            # Final fallback: match by the most distinctive keywords.
            # Последний fallback: совпадение по самым значимым ключевым словам.
            keywords = self._extract_keywords(self._original_device_name)
            if keywords:
                same_api.clear()
                other_api.clear()
                
                for i, dev in enumerate(devices):
                    if i in self._phantom_devices:
                        continue
                    if dev['max_input_channels'] > 0:
                        dev_lower = dev['name'].lower()
                        if (all(kw in dev_lower for kw in keywords) and
                                not self._is_virtual_device(dev['name'])):
                            
                            try:
                                hostapi_info = sd.query_hostapis(dev['hostapi'])
                                hostapi_name = hostapi_info['name'].lower()
                                
                                if self._original_hostapi and hostapi_name == self._original_hostapi:
                                    same_api.append(i)
                                else:
                                    other_api.append(i)
                            except Exception:
                                other_api.append(i)

                if same_api:
                    idx = same_api[0]
                    print(f"[WATCHDOG] 🔍 По ключевым словам (тот же API): [{idx}] {devices[idx]['name']}")
                    return idx
                
                if other_api:
                    idx = other_api[0]
                    print(f"[WATCHDOG] 🔍 По ключевым словам (другой API): [{idx}] {devices[idx]['name']}")
                    return idx

        except Exception as e:
            print(f"[WATCHDOG] Ошибка поиска: {e}")

        return None

    def _find_default_real_mic(self):
        """Finds the system default microphone if it is real, otherwise the first real input.
        Ищет системный микрофон по умолчанию, а если он виртуальный — первый реальный вход."""
        try:
            default_idx = sd.default.device[0]
            if default_idx is not None:
                dev_info = sd.query_devices(default_idx)
                if (dev_info['max_input_channels'] > 0 and
                        not self._is_virtual_device(dev_info['name'])):
                    return default_idx

            # If the default endpoint is virtual, fall back to the first real microphone.
            # Если default-устройство виртуальное, берём первый реальный микрофон.
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and
                        not self._is_virtual_device(dev['name'])):
                    return i

        except Exception:
            pass
        return None

    def _extract_keywords(self, device_name):
        """Extracts the most distinctive keywords from a device name.
        Извлекает наиболее значимые ключевые слова из имени устройства."""
        # Drop generic words that are present in many microphone names.
        # Убираем общие слова, которые встречаются почти у всех микрофонов.
        skip_words = {
            'input', 'output', 'микрофон', 'microphone',
            'headset', 'headphone', 'головной', 'телефон',
            'hands-free', 'stereo', 'mono', 'audio',
            'high', 'definition', 'device',
        }

        words = device_name.lower().split()
        # Re-tokenize by brackets and punctuation to catch branded fragments cleanly.
        # Дополнительно разбиваем по скобкам и спецсимволам, чтобы чище выделить брендовые фрагменты.
        import re
        words = re.findall(r'\w+', device_name.lower())

        keywords = [w for w in words
                    if w not in skip_words and len(w) > 2]

        # A short keyword set is enough and keeps matching stable.
        # Короткого набора ключевых слов достаточно и он даёт более стабильный поиск.
        return keywords[:3] if keywords else []

    def _print_available_real_mics(self):
        """Показывает доступные реальные микрофоны."""
        try:
            devices = sd.query_devices()
            real_mics = []
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and
                        not self._is_virtual_device(dev['name'])):
                    real_mics.append(f"  [{i}] {dev['name']}")

            if real_mics:
                print(f"[WATCHDOG] Доступные реальные микрофоны:")
                for m in real_mics:
                    print(f"  {m}")
            else:
                print(f"[WATCHDOG] ❌ Реальных микрофонов не найдено!")
        except Exception:
            pass

    def _mark_device_as_phantom(self, device_index):
        """Marks a device as phantom when it opens but produces no data.
        Помечает устройство как фантомное, если оно открывается, но не отдаёт данные."""
        self._phantom_devices.add(device_index)
        try:
            dev_info = sd.query_devices(device_index)
            print(f"[WATCHDOG] 👻 Фантом: [{device_index}] {dev_info['name'][:50]}")
        except Exception:
            print(f"[WATCHDOG] 👻 Фантом: [{device_index}]")            

    # === Recording ===
    # === Запись ===

    def start_capture(self):
        if self.device_index is None:
            print("[REC] ❌ Микрофон не выбран")
            return

        if self._device_lost:
            print("[REC] ⚠️  Микрофон потерян! Дождитесь переподключения.")
            return

        if not self._is_stream_alive():
            print("[REC] ⚠️  Микрофон не активен! Пробую переподключить...")
            self._try_reconnect()
            time.sleep(0.5)
            if not self._is_stream_alive():
                print("[REC] ❌ Микрофон не работает")
                return

        with self._lock:
            pre_buf_samples = sum(len(c) for c in self.ring_buffer)
            pre_buf_duration = pre_buf_samples / self.sample_rate
            self.audio_data = list(self.ring_buffer)
            self.ring_buffer = deque()
            self.is_capturing = True
            self._warned = False
        print(f"[REC] ● Запись (pre-buffer: {pre_buf_duration:.2f}с)")

    def stop_capture(self):
        with self._lock:
            self.is_capturing = False
        time.sleep(0.03)
        with self._lock:
            total = sum(len(c) for c in self.audio_data)
        duration = total / self.sample_rate
        print(f"[REC] ■ Стоп. Записано: {duration:.1f} сек")

    def start_vad_capture(self):
        if self._device_lost:
            print("[REC] ⚠️  Микрофон потерян!")
            return

        if not self._is_stream_alive():
            self._try_reconnect()
            time.sleep(0.5)

        with self._lock:
            self.audio_data = list(self.ring_buffer)
            self.ring_buffer = deque()
            self.vad_recording = True
            self._warned = False
        print("[REC] ● VAD запись начата")

    def stop_vad_capture(self):
        with self._lock:
            self.vad_recording = False
            total = sum(len(c) for c in self.audio_data)
        duration = total / self.sample_rate
        print(f"[REC] ■ VAD стоп. {duration:.1f} сек")
        time.sleep(0.03)

    def _is_stream_alive(self):
        if self.stream is None:
            return False
        try:
            if not self.stream.active:
                return False
        except Exception:
            return False
        elapsed = time.time() - self._last_callback_time
        return elapsed < self._silence_timeout



    def _is_zero_stream(self):
        """Checks whether the stream has been producing only zero data for too long.
        Проверяет, не отдаёт ли поток слишком долго только нулевые данные."""
        now = time.time()
        # Ignore the first moments before any real signal has ever been seen.
        # Если реального сигнала ещё не было ни разу, не считаем это проблемой.
        if self._last_nonzero_time == 0:
            return False
        # Recent non-zero audio means the stream is still healthy.
        # Если недавно были реальные данные, поток считаем живым.
        if now - self._last_nonzero_time < self._zero_stream_timeout:
            return False
        return True        

    def set_vad_callback(self, callback):
        self._vad_callback = callback
        print(f"[MIC] VAD callback {'установлен' if callback else 'убран'}")

    def save_to_wav(self, filepath):
        with self._lock:
            if not self.audio_data:
                print("[REC] Нет данных")
                return False
            full_audio = np.concatenate(self.audio_data, axis=0)

        # Apply denoising only to the saved file, not to the live capture buffer.
        # Применяем шумоподавление только к сохраняемому файлу, а не к живому буферу.
        if self.noise_filter and self.noise_filter.enabled:
            full_audio = self.noise_filter.filter_audio(full_audio)

        max_val = np.max(np.abs(full_audio))
        duration = len(full_audio) / self.sample_rate
        print(f"[REC] {duration:.1f}с, громкость: {max_val:.4f}")

        if max_val < 0.001:
            print("[REC] Тишина")
            return False

        # Normalize toward the level Whisper was trained on, but cap gain to avoid clipping.
        # Нормализуем к уровню, на котором обучался Whisper, но ограничиваем усиление, чтобы не клипповать.
        rms = np.sqrt(np.mean(full_audio ** 2))
        if rms > 1e-6:
            target_rms = 0.1  # Roughly -20 dBFS. / Примерно -20 dBFS.
            gain = target_rms / rms
            # Hard-limit gain so peaks remain within the WAV range.
            # Жёстко ограничиваем усиление, чтобы пики остались в пределах WAV-диапазона.
            max_gain = 0.95 / max(max_val, 1e-6)
            gain = min(gain, max_gain)
            full_audio = full_audio * gain
            print(f"[REC] RMS-норм: rms={rms:.4f} → {target_rms}, gain={gain:.2f}x")

        audio_16bit = (full_audio * 32767).astype(np.int16)

        with wave.open(str(filepath), 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_16bit.tobytes())

        print(f"[REC] Сохранено → {filepath}")
        return True

    def clear(self):
        with self._lock:
            self.audio_data = []
