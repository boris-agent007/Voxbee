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
Noise reduction for voice input.
Шумоподавление для голосового ввода.

It records a background-noise profile during VAD calibration
and subtracts it from audio before sending it to Whisper.
Записывает профиль фонового шума при калибровке VAD,
затем вычитает его из аудио перед отправкой в Whisper.
"""
import time
import numpy as np

try:
    import noisereduce as nr
    HAS_NOISEREDUCE = True
except ImportError:
    HAS_NOISEREDUCE = False
    print("[NOISE] ⚠️ noisereduce не установлен. pip install noisereduce")


class NoiseFilter:
    def __init__(self, sample_rate=16000, calibration_sec=3.0):
        self.sample_rate = sample_rate
        self.calibration_sec = calibration_sec
        self.noise_profile = None
        self._calibration_buffer = []
        self._calibration_samples = int(sample_rate * calibration_sec)
        self._is_calibrated = False
        self._enabled = True

    @property
    def is_calibrated(self):
        return self._is_calibrated

    @property
    def enabled(self):
        return self._enabled and HAS_NOISEREDUCE

    def set_enabled(self, value):
        self._enabled = value
        print(f"[NOISE] Шумоподавление: {'ВКЛ' if value else 'ВЫКЛ'}")

    def feed_calibration(self, audio_chunk):
        """
        Feeds audio into the noise-profile calibration.
        Подаёт аудио для записи профиля шума.
        Called during silence while VAD is calibrating.
        Вызывается во время тишины (калибровка VAD).
        Returns True once the profile is captured.
        Возвращает True когда профиль записан.
        """
        if self._is_calibrated:
            return True

        flat = audio_chunk.flatten()
        self._calibration_buffer.append(flat)
        total = sum(len(c) for c in self._calibration_buffer)

        if total >= self._calibration_samples:
            self.noise_profile = np.concatenate(self._calibration_buffer)
            self.noise_profile = self.noise_profile[:self._calibration_samples]
            self._is_calibrated = True
            noise_energy = np.sqrt(np.mean(self.noise_profile ** 2))
            print(f"[NOISE] ✅ Профиль шума: {self.calibration_sec}с, "
                  f"энергия={noise_energy:.6f}")
            return True
        return False

    def reset(self):
        """Resets calibration.
        Сброс калибровки."""
        self.noise_profile = None
        self._calibration_buffer = []
        self._is_calibrated = False
        print("[NOISE] 🔄 Калибровка сброшена")


    def soft_reset(self):
        """Soft reset: clears buffers but preserves calibration.
        Мягкий сброс: очищает буферы, но сохраняет калибровку."""
        if self._is_calibrated:
            # Preserve the learned noise profile and clear only the transient buffer.
            # Сохраняем обученный профиль шума и очищаем только временный буфер.
            self._calibration_buffer = []
            print("[NOISE] 🔄 Буферы очищены (калибровка сохранена)")
        else:
            # Fall back to a full reset if calibration is not complete yet.
            # Если калибровка ещё не завершена, выполняем полный сброс.
            self.reset()


    def filter_audio(self, audio_data):
        """
        Removes background noise from audio before Whisper.
        Убирает фоновый шум из аудио перед Whisper.
        """
        if not self.enabled or not self._is_calibrated:
            return audio_data

        try:
            t_start = time.time()

            if audio_data.ndim > 1:
                audio_flat = audio_data.flatten()
            else:
                audio_flat = audio_data

            cleaned = nr.reduce_noise(
                y=audio_flat,
                y_noise=self.noise_profile,
                sr=self.sample_rate,
                prop_decrease=0.95,
                stationary=True,
                n_fft=2048,
                hop_length=512,
                n_std_thresh_stationary=1.5,
            )

            t_elapsed = time.time() - t_start

            before_energy = np.sqrt(np.mean(audio_flat ** 2))
            after_energy = np.sqrt(np.mean(cleaned ** 2))
            reduction = (1 - after_energy / max(before_energy, 1e-10)) * 100
            print(f"[NOISE] 🔇 до={before_energy:.4f} → после={after_energy:.4f} "
                  f"(-{reduction:.0f}%) [{t_elapsed:.2f}с]")

            return cleaned.astype(np.float32)

        except Exception as e:
            print(f"[NOISE ERROR] {e}")
            return audio_data
