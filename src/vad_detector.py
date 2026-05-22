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

import numpy as np
import threading
from collections import deque

class VADDetector:
    """
    Energy-based voice activity detector.
    Детектор голосовой активности на основе энергии сигнала.

    Buffers audio between calls so chunks of arbitrary size can still be processed frame by frame.
    Накапливает аудио между вызовами, чтобы корректно обрабатывать чанки произвольного размера по фреймам.
    """

    def __init__(self, sample_rate=16000, aggressiveness=1,
                 silence_duration=1.5, min_speech_duration=0.15,
                 accept_short_speech=False):
        self.sample_rate = sample_rate
        self.silence_duration = silence_duration
        self.min_speech_duration = min_speech_duration

        # Lower aggressiveness keeps quieter microphones usable by starting from a softer threshold.
        # При низкой агрессивности стартуем с более мягкого порога, чтобы тихие микрофоны оставались рабочими.
        self.energy_threshold = [0.0005, 0.001, 0.002, 0.005][min(aggressiveness, 3)]

        self.frame_duration = 0.03
        self.frame_size = int(sample_rate * self.frame_duration)  # Frame size at 30 ms. / Размер фрейма при 30 мс.

        self.is_speaking = False
        self.silence_frames = 0
        self.speech_frames = 0
        self.silence_threshold = int(silence_duration / self.frame_duration)
        self.min_speech_frames = int(min_speech_duration / self.frame_duration)

        # Startup noise calibration adapts the threshold to the current environment.
        # Стартовая калибровка подстраивает порог под текущий шум окружения.
        self._noise_samples = []
        self._noise_adapted = False
        self._calibration_frames = int(1.0 / self.frame_duration)

        # Deque keeps buffering O(1) while chunks are accumulated across callbacks.
        # Deque даёт O(1) при накоплении чанков между callback'ами.
        self._buffer = deque()
        self._buffer_samples = 0  # Buffered sample count. / Счётчик сэмплов в буфере.

        self._debug_counter = 0
        self._total_chunks = 0
        self.accept_short_speech = accept_short_speech

        # Guard shared state because audio callbacks and processing can race.
        # Защищаем общее состояние, потому что audio thread и обработка могут выполняться одновременно.
        self._lock = threading.Lock()

    def process_chunk(self, audio_float32):
        """
        Accepts float32 audio chunks of any size.
        Buffers them and processes complete frames one by one.

        Принимает float32-аудио любого размера.
        Накапливает его в буфере и обрабатывает полными фреймами по очереди.

        Thread-safe: protected by _lock.
        Thread-safe: защищён через _lock.
        """
        with self._lock:
            return self._process_chunk_unlocked(audio_float32)

    def _process_chunk_unlocked(self, audio_float32):
        """Внутренняя логика process_chunk (вызывать только под _lock)."""
        self._total_chunks += 1

        if self._total_chunks == 1:
            print(f"[VAD] process_chunk ВЫЗВАН! shape={audio_float32.shape}, frame_size={self.frame_size}")

        flat = audio_float32.flatten()

        # Append incoming samples to the rolling deque buffer in O(1).
        # Добавляем входящие сэмплы в deque-буфер за O(1).
        self._buffer.append(flat)
        self._buffer_samples += len(flat)

        # Process every complete frame that is already buffered.
        # Обрабатываем все полные фреймы, которые уже накопились в буфере.
        result = None

        while self._buffer_samples >= self.frame_size:
            frame = self._extract_frame()

            energy = np.sqrt(np.mean(frame ** 2))

            # During calibration we learn the noise floor before making speech decisions.
            # Во время калибровки сначала учим шумовой фон и только потом принимаем решение о речи.
            if not self._noise_adapted:
                self._noise_samples.append(energy)
                if len(self._noise_samples) >= self._calibration_frames:
                    avg_noise = np.mean(self._noise_samples)
                    std_noise = np.std(self._noise_samples)
                    calibrated = avg_noise + 2.5 * std_noise
                    calibrated = max(calibrated, avg_noise * 2.5)
                    calibrated = max(calibrated, 0.001)
                    calibrated = min(calibrated, 0.01)
                    self.energy_threshold = calibrated
                    self._noise_adapted = True
                    print(f"[VAD] ✅ Калибровка: шум={avg_noise:.6f}±{std_noise:.6f}, порог={self.energy_threshold:.6f}")
                continue

            is_speech = energy > self.energy_threshold

            # Emit a periodic debug line roughly once per second.
            # Печатаем отладочную строку примерно раз в секунду.
            self._debug_counter += 1
            if self._debug_counter % 33 == 0:
                status = "🔊" if is_speech else "🔇"
                print(f"[VAD] {status} e={energy:.6f} thr={self.energy_threshold:.6f} spk={self.is_speaking}")

            if is_speech:
                self.speech_frames += 1
                self.silence_frames = 0
                if not self.is_speaking and self.speech_frames >= 2:
                    self.is_speaking = True
                    result = 'speech_start'
                    print(f"[VAD] >>> SPEECH START")
            else:
                if self.is_speaking:
                    self.silence_frames += 1

                    if self.silence_frames >= self.silence_threshold:
                        if self.speech_frames >= self.min_speech_frames:
                            result = 'speech_end'
                            print(f"[VAD] >>> SPEECH END (речь={self.speech_frames} фреймов)")
                        elif self.accept_short_speech:
                            result = 'speech_end'
                            print(f"[VAD] >>> SHORT SPEECH ({self.speech_frames} фреймов) — принято")
                        else:
                            print(f"[VAD] >>> Короткая речь, пропуск")
                        self.is_speaking = False
                        self.speech_frames = 0
                        self.silence_frames = 0
                else:
                    self.speech_frames = 0

        return result

    def _extract_frame(self):
        """Extracts exactly frame_size samples from the deque buffer with amortized O(1) behavior.
        Извлекает ровно frame_size сэмплов из deque-буфера с амортизированным O(1)."""
        needed = self.frame_size
        parts = []
        while needed > 0 and self._buffer:
            chunk = self._buffer[0]
            if len(chunk) <= needed:
                parts.append(self._buffer.popleft())
                needed -= len(chunk)
            else:
                parts.append(chunk[:needed])
                self._buffer[0] = chunk[needed:]
                needed = 0
        self._buffer_samples -= self.frame_size
        if len(parts) == 1:
            return parts[0]
        return np.concatenate(parts)

    def reset(self):
        """Performs a full reset, including noise calibration state.
        Выполняет полный сброс, включая состояние калибровки шума."""
        with self._lock:
            self.is_speaking = False
            self.silence_frames = 0
            self.speech_frames = 0
            self._noise_samples = []
            self._noise_adapted = False
            self._buffer = deque()
            self._buffer_samples = 0
            self._debug_counter = 0
            self._total_chunks = 0

    def soft_reset(self):
        """Soft reset that clears speech state but preserves the learned noise calibration.
        Мягкий сброс: очищает состояние речи, но сохраняет калибровку шума."""
        with self._lock:
            self.is_speaking = False
            self.silence_frames = 0
            self.speech_frames = 0
            self._buffer = deque()
            self._buffer_samples = 0
            # Keep the calibrated threshold so the next phrase does not need to relearn ambient noise.
            # Сохраняем откалиброванный порог, чтобы следующей фразе не пришлось заново учить фон.
            print(f"[VAD] 🔄 Состояние сброшено (калибровка сохранена, порог={self.energy_threshold:.6f})")


