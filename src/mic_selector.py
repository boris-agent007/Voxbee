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
Microphone selection utilities: list, choose, and test input devices.
Выбор микрофона: показать список, выбрать устройство и протестировать его.
"""

import sounddevice as sd
import numpy as np
import time


def list_microphones():
    """Returns the list of available microphones without duplicates.
    For each device, the best available HostAPI is selected:
    WASAPI -> WDM-KS -> DirectSound -> MME.

    Возвращает список доступных микрофонов без дублей.
    Для каждого устройства выбирается лучший доступный HostAPI:
    WASAPI → WDM-KS → DirectSound → MME.
    """
    HOST_PRIORITY = {
        'wasapi':               0,
        'windows wasapi':       0,
        'wdm-ks':               1,
        'windows wdm-ks':       1,
        'directsound':          2,
        'windows directsound':  2,
        'mme':                  3,
        'windows mme':          3,
    }

    devices = sd.query_devices()
    try:
        default_idx = sd.default.device[0]
    except Exception:
        default_idx = -1

    best_by_name = {}

    for i, dev in enumerate(devices):
        if dev['max_input_channels'] <= 0:
            continue

        try:
            hostapi_info = sd.query_hostapis(dev['hostapi'])
            hostapi_name = hostapi_info['name'].lower()
        except Exception:
            hostapi_name = ''

        priority = HOST_PRIORITY.get(hostapi_name, 99)

        # Penalize WASAPI/WDM-KS devices that do not natively support 16 kHz.
        # Realtime resampling is unstable on some USB microphones.
        # Понижаем приоритет WASAPI/WDM-KS, если устройство не умеет 16 кГц нативно.
        # Ресемплинг в реальном времени бывает нестабилен на USB-микрофонах.
        if priority <= 1:
            try:
                native_rate = int(dev['default_samplerate'])
                if native_rate != 16000:
                    priority = 3  # понижаем до уровня MME
            except Exception:
                pass
        is_default = (i == default_idx)
        raw_name = dev['name']

        entry = {
            'index': i,
            'name': raw_name,
            'channels': dev['max_input_channels'],
            'sample_rate': dev['default_samplerate'],
            'is_default': is_default,
        }

        # MME truncates names to 31 characters, so deduplication uses the short key.
        # MME обрезает имя до 31 символа, поэтому дедупликация идёт по короткому ключу.
        dedup_key = raw_name[:31].rstrip()
        existing = best_by_name.get(dedup_key)
        if existing is None or priority < existing['_priority']:
            entry['_priority'] = priority
            best_by_name[dedup_key] = entry

    # Drop the internal priority marker before returning data to callers.
    # Убираем внутреннее поле приоритета перед возвратом данных.
    mics = []
    for entry in best_by_name.values():
        entry.pop('_priority', None)
        mics.append(entry)

    # Keep the default microphone first, then sort the rest by name.
    # Сначала ставим микрофон по умолчанию, затем сортируем остальные по имени.
    mics.sort(key=lambda m: (not m['is_default'], m['name']))
    if mics:
        # Log the selected HostAPI for easier troubleshooting.
        # Логируем выбранный HostAPI для упрощения диагностики.
        for m in mics:
            # Query the device again only for diagnostics output.
            # Повторно запрашиваем устройство только для диагностического лога.
            try:
                dev = sd.query_devices(m['index'])
                hostapi_info = sd.query_hostapis(dev['hostapi'])
                api_name = hostapi_info['name']
            except Exception:
                api_name = '?'
            print(f"[MIC] [{m['index']:2d}] {m['name']} → {api_name}")

    return mics


def print_microphones(mics=None):
    """Prints the microphone list in a readable format.
    Выводит список микрофонов в удобном для чтения виде."""
    if mics is None:
        mics = list_microphones()

    print("\n" + "=" * 60)
    print("  🎤 ДОСТУПНЫЕ МИКРОФОНЫ")
    print("=" * 60)

    if not mics:
        print("  ❌ Микрофоны не найдены!")
        return mics

    for mic in mics:
        default_mark = " ⭐ (по умолчанию)" if mic['is_default'] else ""
        print(f"  [{mic['index']:2d}] {mic['name']}")
        print(f"       Каналы: {mic['channels']}, "
              f"Частота: {int(mic['sample_rate'])} Hz"
              f"{default_mark}")

    print("=" * 60)
    return mics


def test_microphone(device_index=None, duration=3):
    """
    Records a short sample and shows the input level.
    Записывает короткий фрагмент и показывает уровень сигнала.
    """
    name = "системный" if device_index is None else f"#{device_index}"
    print(f"\n[TEST] Тест микрофона {name} ({duration} сек)...")
    print("[TEST] Говорите что-нибудь...")

    try:
        sample_rate = 16000
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            device=device_index,
        )

        # Show the signal level while recording is still in progress.
        # Показываем уровень сигнала, пока запись ещё идёт.
        for i in range(duration * 10):
            time.sleep(0.1)
            recorded_so_far = recording[:int((i + 1) * sample_rate / 10)]
            if len(recorded_so_far) > 0:
                level = np.sqrt(np.mean(recorded_so_far[-1600:] ** 2))
                bars = int(level * 500)
                bar_str = "█" * min(bars, 40)
                print(f"\r  Уровень: [{bar_str:<40}] {level:.4f}", end="", flush=True)

        sd.wait()
        print()

        max_level = np.max(np.abs(recording))
        avg_level = np.sqrt(np.mean(recording ** 2))

        print(f"[TEST] Максимум: {max_level:.4f}")
        print(f"[TEST] Среднее:  {avg_level:.4f}")

        if max_level < 0.001:
            print("[TEST] ⚠️  Очень тихо — микрофон может не работать!")
            return False
        elif max_level < 0.01:
            print("[TEST] ⚠️  Тихо — попробуйте увеличить громкость микрофона")
            return True
        else:
            print("[TEST] ✅ Микрофон работает нормально!")
            return True

    except Exception as e:
        print(f"\n[TEST] ❌ Ошибка: {e}")
        return False


def select_microphone_interactive():
    """
    Interactive microphone selection in the console.
    Интерактивный выбор микрофона через консоль.

    Возвращает (device_index, device_name) или (None, "системный").
    Returns (device_index, device_name) or (None, "system default").
    """
    mics = print_microphones()

    if not mics:
        return None, "не найден"

    print("\nВведите номер микрофона (или Enter для системного по умолчанию):")
    print("Введите 't' + номер для теста (например: t0, t1)")

    while True:
        try:
            choice = input("\n> ").strip()

            if choice == "" or choice.lower() == "d":
                default_mic = next((m for m in mics if m['is_default']), mics[0])
                print(f"[MIC] Выбран системный: {default_mic['name']}")
                return None, default_mic['name']

            # Prefix "t" runs the device test without changing the selection.
            # Префикс "t" запускает тест устройства без смены выбора.
            if choice.lower().startswith('t'):
                try:
                    idx = int(choice[1:])
                    mic = next((m for m in mics if m['index'] == idx), None)
                    if mic:
                        test_microphone(idx)
                    else:
                        print(f"Микрофон #{idx} не найден")
                except ValueError:
                    print("Формат: t0, t1, t2...")
                continue

            # Plain numeric input selects the microphone by its device index.
            # Обычное число выбирает микрофон по индексу устройства.
            idx = int(choice)
            mic = next((m for m in mics if m['index'] == idx), None)
            if mic:
                print(f"[MIC] ✅ Выбран: [{idx}] {mic['name']}")
                return idx, mic['name']
            else:
                print(f"Микрофон #{idx} не найден. Доступные: "
                      f"{[m['index'] for m in mics]}")

        except ValueError:
            print("Введите число или 't' + число")
        except KeyboardInterrupt:
            print("\nОтмена")
            return None, "системный"
