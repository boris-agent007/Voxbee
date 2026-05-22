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
Unified VoxBee settings window.
Единое окно настроек VoxBee.

All changes are applied immediately without a Save button.
Все изменения применяются сразу, без кнопки «Сохранить».

When the window closes, tray state is synchronized back to config.
При закрытии окна состояние трея синхронизируется обратно в config.
"""

import tkinter as tk
from tkinter import ttk, filedialog
import threading
from pathlib import Path

from ui_strings import tr

_settings_win = None


def _apply_window_icon(win):
    """Applies the best available VoxBee window icon.
    Устанавливает окну лучшую доступную фирменную иконку VoxBee."""
    from app_paths import get_template_path
    try:
        png_path = get_template_path("voxbee_full.png")
        if png_path.exists():
            icon_image = tk.PhotoImage(file=str(png_path))
            win.iconphoto(True, icon_image)
            win._voxbee_icon = icon_image
            return
    except Exception:
        pass

    try:
        icon_path = get_template_path("voxbee.ico")
        if icon_path.exists():
            win.iconbitmap(str(icon_path))
    except Exception:
        pass


def open_settings_window(tk_root, ctx):
    """
    Opens the settings window.
    Открывает окно настроек.

    ctx is a dict with the current state and callbacks:
    ctx — dict с текущими данными и callback-ами:
        config, mic_list, model_list, fix_settings, trigger_label,
        autostart_enabled, noise_filter_enabled, commands_enabled,
        on_mode_change, on_mic_change, on_mic_refresh, on_gpu_toggle,
        on_model_change, on_fix_toggle, on_short_speech_toggle,
        on_warmup_toggle, on_noise_filter_toggle, on_show_recognition_toggle,
        on_mouse_step_change, on_commands_toggle, on_log_toggle,
        on_log_dir_change, on_autostart_toggle, on_trigger_capture,
        on_trigger_reset, refresh_trigger_label, on_reload_commands,
        on_reload_dict, on_settings_closed
    """
    global _settings_win
    if _settings_win is not None:
        try:
            if _settings_win.winfo_exists():
                _settings_win.lift()
                _settings_win.focus_force()
                return
        except Exception:
            pass
        _settings_win = None

    win = tk.Toplevel(tk_root)
    _settings_win = win
    _apply_window_icon(win)
    lang = ctx.get('language', 'ru')
    _t = lambda key, **kwargs: tr(key, lang, **kwargs)
    win.title(_t("settings.title"))
    win.geometry("900x1400")
    win.resizable(False, True)
    win.attributes('-topmost', True)

    def _on_close():
        global _settings_win
        _settings_win = None
        cb = ctx.get('on_settings_closed')
        if cb:
            cb()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)

    # Build a scrollable content area because the settings window is taller than many screens.
    # Делаем прокручиваемую область, потому что окно настроек выше, чем многие экраны.
    outer = ttk.Frame(win)
    outer.pack(fill='both', expand=True)

    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)

    scroll_frame.bind(
        '<Configure>',
        lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
    )
    canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)

    def _sync_scroll_frame_width(event):
        """Keeps the inner frame stretched to the canvas width to avoid horizontal scrolling.
        Растягивает внутренний frame по ширине canvas, чтобы не было горизонтального скролла."""
        try:
            canvas.itemconfigure(canvas_window, width=event.width)
        except Exception:
            pass

    canvas.bind('<Configure>', _sync_scroll_frame_width)

    canvas.pack(side='left', fill='both', expand=True)
    # Hide the scrollbar visually; scrolling still works through the mouse wheel and canvas API.
    # Полосу прокрутки намеренно не показываем; скролл остаётся доступным колёсиком и через canvas.

    _mousewheel_bound = {'active': False}

    def _on_mousewheel(event):
        # Ignore wheel events when a combobox drop-down owns the interaction.
        # Не скроллим окно, если сейчас открыт popdown у Combobox.
        try:
            if 'popdown' in str(event.widget):
                return
        except Exception:
            pass

        # Only scroll while this settings window is the active target.
        # Скроллим только пока активно именно это окно настроек.
        try:
            if win.focus_displayof() is None:
                return
        except Exception:
            return

        canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _bind_mousewheel():
        if _mousewheel_bound['active']:
            return
        try:
            canvas.bind_all('<MouseWheel>', _on_mousewheel)
            _mousewheel_bound['active'] = True
        except Exception:
            pass

    def _unbind_mousewheel():
        if not _mousewheel_bound['active']:
            return
        try:
            canvas.unbind_all('<MouseWheel>')
        except Exception:
            pass
        _mousewheel_bound['active'] = False

    # Bind the global wheel handler only while the settings window is active.
    # Глобальный перехват колеса включаем только пока активно окно настроек.
    win.bind('<FocusIn>', lambda e: _bind_mousewheel())
    win.bind('<FocusOut>', lambda e: _unbind_mousewheel())
    win.bind('<Destroy>', lambda e: _unbind_mousewheel() if e.widget == win else None)
    _bind_mousewheel()

    cfg = ctx.get('config', {})
    fs = ctx.get('fix_settings', {})
    pad = {'padx': 12, 'pady': 2}

    # Wrap the microphone list in a mutable container so refresh can replace it in closures.
    # Оборачиваем список микрофонов в изменяемый контейнер, чтобы refresh мог обновлять его в замыканиях.
    _mic_data = {'list': list(ctx.get('mic_list', []))}

    # === Recognition section ===
    # === Секция распознавания ===
    _section(scroll_frame, _t("settings.recognition"))

    # Automatic/VAD recognition mode.
    # Режим автоматического распознавания через VAD.
    vad_var = tk.BooleanVar(value=cfg.get('vad_mode', False))

    def _on_vad():
        cb = ctx.get('on_mode_change')
        if cb:
            threading.Thread(target=cb, args=(vad_var.get(),), daemon=True).start()

    ttk.Checkbutton(scroll_frame, text=_t("settings.auto_mode"),
                    variable=vad_var, command=_on_vad).pack(anchor='w', **pad)

    # GPU toggle.
    # Переключатель GPU.
    gpu_var = tk.BooleanVar(value=cfg.get('use_gpu', False))

    def _on_gpu():
        cb = ctx.get('on_gpu_toggle')
        if cb:
            cb(gpu_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.gpu"),
                    variable=gpu_var, command=_on_gpu).pack(anchor='w', **pad)

    # Microphone selection row.
    # Блок выбора микрофона.
    ttk.Label(scroll_frame, text=_t("settings.microphone")).pack(anchor='w', padx=12, pady=(8, 0))
    mic_frame = ttk.Frame(scroll_frame)
    mic_frame.pack(fill='x', padx=12, pady=2)

    mic_names = [f"[{m['index']}] {m['name']}" for m in _mic_data['list']]
    mic_var = tk.StringVar()
    current_mic_name = cfg.get('microphone_name', '')
    for mn in mic_names:
        if current_mic_name and current_mic_name in mn:
            mic_var.set(mn)
            break
    if not mic_var.get() and mic_names:
        mic_var.set(mic_names[0])

    mic_combo = ttk.Combobox(mic_frame, textvariable=mic_var,
                             values=mic_names, state='readonly', width=42)
    mic_combo.pack(side='left', fill='x', expand=True)

    def _on_mic_select(event=None):
        sel = mic_var.get()
        for m in _mic_data['list']:
            tag = f"[{m['index']}] {m['name']}"
            if tag == sel:
                cb = ctx.get('on_mic_change')
                if cb:
                    threading.Thread(target=cb, args=(m['index'], m['name']),
                                     daemon=True).start()
                break

    mic_combo.bind('<<ComboboxSelected>>', _on_mic_select)

    def _on_mic_refresh():
        def _do():
            cb = ctx.get('on_mic_refresh')
            if cb:
                new_list = cb()
                if new_list:
                    new_names = [f"[{m['index']}] {m['name']}" for m in new_list]

                    def _update_combo():
                        _mic_data['list'] = list(new_list)
                        mic_combo['values'] = new_names

                    try:
                        win.after(0, _update_combo)
                    except Exception:
                        pass

        threading.Thread(target=_do, daemon=True).start()

    ttk.Button(mic_frame, text="🔄", width=3,
               command=_on_mic_refresh).pack(side='left', padx=(4, 0))

    # Whisper model selector.
    # Выбор модели Whisper.
    ttk.Label(scroll_frame, text=_t("settings.model")).pack(anchor='w', padx=12, pady=(8, 0))
    model_list = ctx.get('model_list', [])
    model_names = ["Auto"] + [f"{m['label']} ({m['size_mb']:.0f}MB)" for m in model_list]
    model_keys = ["auto"] + [m['name'] for m in model_list]
    model_var = tk.StringVar()
    cur_model = cfg.get('model_name', 'auto')
    if cur_model in model_keys:
        model_var.set(model_names[model_keys.index(cur_model)])
    else:
        model_var.set(model_names[0])

    model_combo = ttk.Combobox(scroll_frame, textvariable=model_var,
                               values=model_names, state='readonly', width=44)
    model_combo.pack(anchor='w', padx=12, pady=2)

    def _on_model_select(event=None):
        sel = model_var.get()
        if sel in model_names:
            key = model_keys[model_names.index(sel)]
            cb = ctx.get('on_model_change')
            if cb:
                cb(key)

    model_combo.bind('<<ComboboxSelected>>', _on_model_select)

    # Accept short speech segments.
    # Принимать короткие фрагменты речи.
    short_var = tk.BooleanVar(value=fs.get('vad_accept_short_speech', False))

    def _on_short():
        cb = ctx.get('on_short_speech_toggle')
        if cb:
            cb(short_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.short_speech"),
                    variable=short_var, command=_on_short).pack(anchor='w', **pad)

    # Keep the model warm in memory when the mode requires it.
    # Держать модель прогретой в памяти, если это допускает выбранный режим.
    warmup_var = tk.BooleanVar(value=fs.get('warmup_on_start', True))

    def _on_warmup():
        cb = ctx.get('on_warmup_toggle')
        if cb:
            cb(warmup_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.keep_model"),
                    variable=warmup_var, command=_on_warmup).pack(anchor='w', **pad)

    # Noise-reduction toggle.
    # Переключатель шумоподавления.
    noise_var = tk.BooleanVar(value=ctx.get('noise_filter_enabled', True))

    def _on_noise():
        cb = ctx.get('on_noise_filter_toggle')
        if cb:
            cb(noise_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.noise"),
                    variable=noise_var, command=_on_noise).pack(anchor='w', **pad)

    # === Text processing section ===
    # === Секция обработки текста ===
    _section(scroll_frame, _t("settings.text_processing"))

    fix_keys = [
        ("text_fix_enabled", _t("settings.fix_all")),
        ("text_fix_hallucinations", _t("settings.fix_hallucinations")),
        ("text_fix_dictionary", _t("settings.fix_dictionary")),
        ("text_fix_user_dict", _t("settings.fix_user_dictionary")),
        ("text_fix_repetitions", _t("settings.fix_repetitions")),
        ("text_fix_punctuation", _t("settings.fix_punctuation")),
    ]

    for key, label in fix_keys:
        var = tk.BooleanVar(value=fs.get(key, True))

        def _make_fix_cb(k, v):
            def _cb():
                cb = ctx.get('on_fix_toggle')
                if cb:
                    cb(k, v.get())
            return _cb

        ttk.Checkbutton(scroll_frame, text=label,
                        variable=var, command=_make_fix_cb(key, var)).pack(anchor='w', **pad)

    # Dictionary actions.
    # Действия со словарём.
    dict_frame = ttk.Frame(scroll_frame)
    dict_frame.pack(fill='x', padx=12, pady=4)

    def _on_reload_dict():
        cb = ctx.get('on_reload_dict')
        if cb:
            cb()

    ttk.Button(dict_frame, text=_t("settings.reload_dictionary"),
               command=_on_reload_dict).pack(side='left')

    # Voice-command controls.
    # Блок голосовых команд.
    ttk.Separator(scroll_frame, orient='horizontal').pack(fill='x', padx=12, pady=6)

    cmd_var = tk.BooleanVar(value=ctx.get('commands_enabled', True))

    def _on_cmd():
        cb = ctx.get('on_commands_toggle')
        if cb:
            cb(cmd_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.recognize_commands"),
                    variable=cmd_var, command=_on_cmd).pack(anchor='w', **pad)

    def _on_reload_cmds():
        cb = ctx.get('on_reload_commands')
        if cb:
            cb()

    ttk.Button(scroll_frame, text=_t("settings.reload_commands"),
               command=_on_reload_cmds).pack(anchor='w', padx=12, pady=2)

    # === Interface section ===
    # === Секция интерфейса ===
    _section(scroll_frame, _t("settings.interface"))

    # Show the recognition result in the UI.
    # Показывать распознанный текст в интерфейсе.
    show_var = tk.BooleanVar(value=cfg.get('show_recognition_result', False))

    def _on_show():
        cb = ctx.get('on_show_recognition_toggle')
        if cb:
            cb(show_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.show_recognition"),
                    variable=show_var, command=_on_show).pack(anchor='w', **pad)

    # Mouse movement step.
    # Шаг перемещения мыши.
    ttk.Label(scroll_frame, text=_t("settings.mouse_step")).pack(anchor='w', padx=12, pady=(8, 0))
    steps = [50, 100, 150, 200, 300, 500]
    step_var = tk.StringVar(value=str(cfg.get('mouse_step', 150)))
    step_combo = ttk.Combobox(scroll_frame, textvariable=step_var,
                              values=[str(s) for s in steps], state='readonly', width=10)
    step_combo.pack(anchor='w', padx=12, pady=2)

    def _on_step(event=None):
        try:
            val = int(step_var.get())
            cb = ctx.get('on_mouse_step_change')
            if cb:
                cb(val)
        except ValueError:
            pass

    step_combo.bind('<<ComboboxSelected>>', _on_step)

    # Push-to-talk trigger assignment.
    # Назначение кнопки записи.
    ttk.Label(scroll_frame, text=_t("settings.record_button")).pack(anchor='w', padx=12, pady=(8, 0))
    trigger_frame = ttk.Frame(scroll_frame)
    trigger_frame.pack(fill='x', padx=12, pady=2)

    trigger_label_var = tk.StringVar(value=ctx.get('trigger_label', _t("settings.middle_mouse")))
    ttk.Label(trigger_frame, textvariable=trigger_label_var,
              font=('Segoe UI', 10, 'bold')).pack(side='left')

    def _on_capture():
        old_label = trigger_label_var.get()
        cb = ctx.get('on_trigger_capture')
        if cb:
            cb()

        def _poll(n=30):
            refresh = ctx.get('refresh_trigger_label')
            if refresh:
                try:
                    new_label = refresh()
                    if new_label != old_label:
                        trigger_label_var.set(new_label)
                        return
                except Exception:
                    pass
            if n > 0:
                try:
                    win.after(1000, lambda: _poll(n - 1))
                except Exception:
                    pass

        win.after(500, lambda: _poll())

    ttk.Button(trigger_frame, text=_t("settings.assign"),
               command=_on_capture).pack(side='left', padx=(8, 0))

    def _on_reset_trigger():
        cb = ctx.get('on_trigger_reset')
        if cb:
            cb()
        trigger_label_var.set(_t("settings.middle_mouse"))

    ttk.Button(trigger_frame, text=_t("settings.reset"),
               command=_on_reset_trigger).pack(side='left', padx=(4, 0))

    # === System section ===
    # === Секция системы ===
    _section(scroll_frame, _t("settings.system"))

    ttk.Label(scroll_frame, text=_t("settings.language")).pack(anchor='w', padx=12, pady=(8, 0))
    lang_frame = ttk.Frame(scroll_frame)
    lang_frame.pack(fill='x', padx=12, pady=2)
    lang_var = tk.StringVar(value=ctx.get('language', 'ru'))
    lang_combo = ttk.Combobox(lang_frame, textvariable=lang_var,
                              values=['ru', 'en'], state='readonly', width=10)
    lang_combo.pack(side='left')

    def _on_language(event=None):
        cb = ctx.get('on_language_change')
        if cb:
            cb(lang_var.get())
            _on_close()

    lang_combo.bind('<<ComboboxSelected>>', _on_language)

    # File logging toggle.
    # Переключатель логирования в файл.
    log_var = tk.BooleanVar(value=cfg.get('log_enabled', False))

    def _on_log():
        cb = ctx.get('on_log_toggle')
        if cb:
            cb(log_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.write_log"),
                    variable=log_var, command=_on_log).pack(anchor='w', **pad)

    # Log directory chooser and reset controls.
    # Выбор и сброс папки логов.
    ttk.Label(scroll_frame, text=_t("settings.log_folder")).pack(anchor='w', padx=12, pady=(4, 0))
    logdir_frame = ttk.Frame(scroll_frame)
    logdir_frame.pack(fill='x', padx=12, pady=2)

    logdir_var = tk.StringVar(value=cfg.get('log_directory', '') or _t("settings.logs_default"))
    ttk.Label(logdir_frame, textvariable=logdir_var, width=40,
              anchor='w').pack(side='left', fill='x', expand=True)

    def _on_pick_logdir():
        path = filedialog.askdirectory(
            parent=win,
            title=_t("settings.select_log_folder"),
            initialdir=cfg.get('log_directory') or None,
        )
        if path:
            logdir_var.set(path)
            cb = ctx.get('on_log_dir_change')
            if cb:
                cb(path)

    ttk.Button(logdir_frame, text="📂", width=3,
               command=_on_pick_logdir).pack(side='left', padx=(4, 0))

    def _on_reset_logdir():
        logdir_var.set(_t("settings.logs_default"))
        cb = ctx.get('on_log_dir_change')
        if cb:
            cb('')

    ttk.Button(logdir_frame, text=_t("settings.reset"), width=8,
               command=_on_reset_logdir).pack(side='left', padx=(4, 0))

    # Windows autostart toggle.
    # Переключатель автозапуска Windows.
    auto_var = tk.BooleanVar(value=ctx.get('autostart_enabled', False))

    def _on_auto():
        cb = ctx.get('on_autostart_toggle')
        if cb:
            cb(auto_var.get())

    ttk.Checkbutton(scroll_frame, text=_t("settings.autostart"),
                    variable=auto_var, command=_on_auto).pack(anchor='w', **pad)

    about_cb = ctx.get('on_open_about')
    if about_cb:
        ttk.Button(scroll_frame, text=_t("settings.about"), command=about_cb).pack(anchor='w', padx=12, pady=(8, 2))

    # Bottom close action.
    # Нижняя кнопка закрытия.
    ttk.Separator(scroll_frame, orient='horizontal').pack(fill='x', padx=12, pady=8)
    ttk.Button(scroll_frame, text=_t("common.close"), command=_on_close).pack(pady=(0, 12))

    # Center the window after the full layout is measured.
    # Центрируем окно после расчёта итогового размера.
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    ww = win.winfo_width()
    wh = win.winfo_height()
    win.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 2}")
    win.focus_force()


def _section(parent, title):
    """Renders a section header with a separator.
    Рисует заголовок секции с разделителем."""
    ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=12, pady=(10, 2))
    ttk.Label(parent, text=title,
              font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=12, pady=(2, 4))
