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
import time
import os
import sys
import queue
import traceback

from pathlib import Path
import pystray
from PIL import Image, ImageDraw

from ui_strings import tr

_tray_instance = None

def _get_tray_instance():
    """Returns the current TrayIcon instance.
    Возвращает текущий экземпляр TrayIcon."""
    return _tray_instance


class TrayIcon:
    STATE_OFF = "off"
    STATE_READY = "ready"
    STATE_RECORDING = "recording"

    def __init__(self, on_toggle=None, on_quit=None):
        self.on_toggle = on_toggle
        self.on_quit = on_quit
        self.on_mode_change = None
        self.on_mic_change = None
        self.on_mic_refresh = None
        self.on_gpu_toggle = None
        self.on_model_change = None

        # (key, bool) — toggle a text-fix stage.
        # (key, bool) — вкл/выкл этап
        self.on_fix_toggle = None
        # () — reload the dictionary.
        # () — перезагрузить словарь
        self.on_reload_dict = None
        # () — open the dictionary file.
        # () — открыть файл словаря
        self.on_open_dict = None
        # () — reload commands.
        # () — перезагрузить команды
        self.on_reload_commands = None
        # (bool) — toggle command recognition.
        # (bool) — вкл/выкл команды
        self.on_commands_toggle = None

        self.state = self.STATE_OFF
        self.icon = None
        self._thread = None
        self._vad_mode = False
        self._use_gpu = False
        self._mic_name = "системный"
        self._mic_list = []
        self._model_name = "auto"
        self._model_list = []
        self.on_short_speech_toggle = None

        self.on_warmup_toggle = None
        self.on_mouse_step_change = None
        self.on_scripts_changed = None
        self.on_reload_scripts = None
        self._mouse_step = 150
        self.on_noise_filter_toggle = None
        self._noise_filter_enabled = True
        self._show_recognition_result = False
        self._math_mode = False
        self.on_math_mode_toggle = None        
        self._math_indicator_win = None
        self._math_indicator_follow_job = None
        self._active_popup_win = None
        self._log_enabled = True
        self._log_directory = ""
        self.on_log_toggle = None
        self.on_log_dir_change = None           
        self._popup_close_flag = False          
        self.on_show_recognition_toggle = None
        self.on_autostart_toggle = None
        self.on_language_change = None
        self.on_open_about = None
        self.on_open_settings = None        
        self._autostart_enabled = False        
        self._language = "ru"


        

        self._trigger_button = "middle"
        self.on_trigger_change = None
        self._fix_settings = {
            "text_fix_enabled": True,
            "text_fix_hallucinations": True,
            "text_fix_dictionary": True,
            "text_fix_punctuation": True,
            "text_fix_repetitions": True,
            "text_fix_user_dict": True,
            "vad_accept_short_speech": False,
            "warmup_on_start": True,
        }
        self._user_dict_count = 0
        self._commands_count = 0
        self._commands_enabled = True                
        self._focus_positions = {}
        self.on_focus_position_delete = None
        self.on_focus_position_goto = None        
        self.on_focus_positions_reset = None

        # Thread-safe UI queue; all icon.* mutations go through it.
        # Thread-safe UI queue — все мутации icon.* проходят через неё
        self._ui_queue = queue.Queue()
        self._ui_thread = None
        self._ui_running = False

        # Debounce for _update_menu.
        # Debounce для _update_menu
        self._menu_update_pending = False
        self._menu_update_lock = threading.Lock()
        self._last_menu_update = 0.0
        _MENU_DEBOUNCE_SEC = 0.3

        # === Dedicated Tk thread for popups and dialogs ===
        # === Выделенный Tk-поток для popup/dialog ===
        self._tk_queue = queue.Queue()
        self._tk_thread = None
        self._tk_root = None
        self._tk_ready = threading.Event()    

    # --- Thread-safe UI operations ---
    # --- Потокобезопасные UI-операции ---

    def _start_ui_worker(self):
        """Starts the background thread that handles UI operations.
        Запускает фоновый поток для обработки UI-операций."""
        if self._ui_running:
            return
        self._ui_running = True
        self._ui_thread = threading.Thread(target=self._ui_worker_loop, daemon=True)
        self._ui_thread.start()

    def _ui_worker_loop(self):
        """Processes the UI operation queue in a separate thread.
        Обрабатывает очередь UI-операций в отдельном потоке."""
        while self._ui_running:
            try:
                func, args = self._ui_queue.get(timeout=0.5)                    
                try:
                    t0 = time.time()
                    func(*args)
                    elapsed = time.time() - t0
                    if elapsed > 2.0:
                        print(f"[TRAY] ⚠️ UI op {func.__name__} заняла {elapsed:.2f}с!")
                except Exception as e:
                    print(f"[TRAY] UI worker error: {e}")
                self._ui_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                break

    # --- Single Tk thread ---
    # --- Единый Tk-поток ---

    def _ensure_tk_thread(self):
        """Starts the dedicated Tk thread if it is not running yet.
        Запускает выделенный Tk-поток если ещё не запущен."""
        if self._tk_thread and self._tk_thread.is_alive():
            return
        self._tk_ready.clear()
        self._tk_thread = threading.Thread(target=self._tk_thread_loop, daemon=True, name="tk-ui")
        self._tk_thread.start()
        self._tk_ready.wait(timeout=3.0)

    def _tk_thread_loop(self):
        """Main loop of the Tk thread: one tk.Tk(), one mainloop.
        Главный цикл Tk-потока. Один tk.Tk(), один mainloop."""
        import tkinter as tk
        try:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
            self._tk_root.title("VoxBee_TkHost")
            # Make the host window invisible.
            # Делаем окно невидимым
            self._tk_root.attributes('-alpha', 0)
            self._tk_root.geometry('1x1+0+0')
            self._tk_ready.set()

            def _poll_tk_queue():
                try:
                    while not self._tk_queue.empty():
                        func, args = self._tk_queue.get_nowait()
                        try:
                            func(*args)
                        except Exception as e:
                            print(f"[TRAY] Tk task error: {e}")
                            traceback.print_exc()
                        self._tk_queue.task_done()
                except Exception:
                    pass
                if self._tk_root:
                    try:
                        self._tk_root.after(50, _poll_tk_queue)
                    except Exception:
                        pass

            self._tk_root.after(50, _poll_tk_queue)
            self._tk_root.mainloop()
        except Exception as e:
            print(f"[TRAY] Tk thread error: {e}")
        finally:
            self._tk_root = None
            self._tk_ready.clear()

    def _run_in_tk(self, func, *args):
        """Queues a task into the Tk thread safely.
        Ставит задачу в очередь Tk-потока (thread-safe)."""
        self._ensure_tk_thread()
        try:
            self._tk_queue.put_nowait((func, args))
        except queue.Full:
            pass

    def _enqueue_ui(self, func, *args):
        """Queues an operation into the UI thread without blocking.
        Ставит операцию в очередь UI-потока (неблокирующий вызов)."""
        try:
            self._ui_queue.put_nowait((func, args))
        except queue.Full:
            pass

    def _do_set_icon(self, image):
        """Performs the actual icon update from the UI worker.
        Фактическое обновление иконки — вызывается из UI-worker."""
        try:
            if self.icon:
                self.icon.icon = image
        except Exception as e:
            print(f"[TRAY] set icon error: {e}")

    def _do_set_title(self, title):
        """Performs the actual title update from the UI worker.
        Фактическое обновление title — вызывается из UI-worker."""
        try:
            if self.icon:
                self.icon.title = title
        except Exception as e:
            print(f"[TRAY] set title error: {e}")

    def _do_update_menu(self):
        """Performs the actual menu update from the UI worker.
        Фактическое обновление меню — вызывается из UI-worker."""
        try:
            if self.icon:
                self.icon.menu = self._get_menu()
        except Exception as e:
            print(f"[TRAY] update menu error: {e}")

    # --- Setters ---
    # --- Сеттеры ---
    def set_trigger_button(self, trigger_id):
        self._trigger_button = trigger_id
        self._update_menu()

    def set_mouse_step(self, step):
        self._mouse_step = step
        self._update_menu()

    def set_language(self, language):
        self._language = language if language in ("ru", "en") else "ru"
        self._update_menu()

    def _t(self, key, **kwargs):
        return tr(key, self._language, **kwargs)


    def set_mic_list(self, mic_list):
        self._mic_list = mic_list
        self._update_menu()

    def set_mic_name(self, name):
        self._mic_name = name
        self._update_menu()

    def set_gpu_mode(self, use_gpu):
        self._use_gpu = use_gpu
        self._update_menu()

    def set_model_list(self, model_list):
        self._model_list = model_list
        self._update_menu()

    def set_model_name(self, name):
        self._model_name = name
        self._update_menu()

    def set_fix_settings(self, settings):
        """Applies text-fixing settings.
        Устанавливает настройки исправления текста."""
        self._fix_settings.update(settings)
        self._update_menu()

    def set_user_dict_count(self, count):
        """Sets the number of words in the user dictionary.
        Количество слов в пользовательском словаре."""
        self._user_dict_count = count
        self._update_menu()


    def set_commands_count(self, count):
        """Sets the number of loaded command triggers.
        Количество загруженных триггеров команд."""
        self._commands_count = count
        self._update_menu()


    def set_commands_enabled(self, value):
        """Enables or disables command recognition.
        Вкл/выкл распознавание команд."""
        self._commands_enabled = value
        self._update_menu()

    def set_show_recognition_result(self, value):
        """Controls whether recognized text is shown.
        Устанавливает режим показа распознанного текста."""
        self._show_recognition_result = value
        self._update_menu()

    def set_autostart_enabled(self, value):
        self._autostart_enabled = value
        self._update_menu()

    def set_log_enabled(self, value):
        self._log_enabled = value
        self._update_menu()

    def set_log_directory(self, path):
        self._log_directory = path
        self._update_menu()


    def set_math_mode(self, value):
        """Sets math mode.
        Устанавливает режим математики."""
        self._math_mode = value
        self._run_in_tk(self._sync_math_indicator_in_tk)
        self._update_menu()                

    def show_recognition_popup(self, text, is_command=False, command_name="", trigger_word=""):
        """Shows a popup with recognized text or a recognized command.
        Показывает всплывающее окно с распознанным текстом или командой."""
        if not self._show_recognition_result:
            return
        if not text.strip() and not trigger_word:
            return

        # For copy commands, grab the clipboard preview NOW.
        # Для команды копирования — захватываем превью буфера СЕЙЧАС
        # Do it before the async Tk call while the clipboard still holds the copied text.
        # (до async Tk-вызова, пока clipboard ещё содержит скопированный текст)
        clipboard_preview = ""
        if is_command and command_name and "ctrl+c" in command_name:
            try:
                from ui_copy_handler import get_clipboard_text
                content = get_clipboard_text()
                if content:
                    raw_lines = content.split('\n')
                    lines = [l.rstrip() for l in raw_lines if l.strip()]
                    if len(lines) <= 4:
                        clipboard_preview = '\n'.join(l[:80] for l in lines)
                    else:
                        top = '\n'.join(l[:80] for l in lines[:2])
                        bot = '\n'.join(l[:80] for l in lines[-2:])
                        clipboard_preview = f"{top}\n  ···({len(lines)} строк)···\n{bot}"
            except Exception:
                pass

        # Close the previous popup via a flag in a thread-safe way.
        # Закрываем предыдущий popup через флаг (thread-safe)
        self._popup_close_flag = True
        self._run_in_tk(
            self._do_show_popup_in_tk,
            text, is_command, command_name, trigger_word, clipboard_preview
        )

    def _close_active_popup(self):
        """Sets a close flag; the popup checks it and closes itself.
        Устанавливает флаг закрытия — popup сам проверит и закроется."""
        self._popup_close_flag = True

    def _cancel_math_indicator_follow_job(self):
        if not self._tk_root or not self._math_indicator_follow_job:
            self._math_indicator_follow_job = None
            return
        try:
            self._tk_root.after_cancel(self._math_indicator_follow_job)
        except Exception:
            pass
        self._math_indicator_follow_job = None

    def _close_math_indicator_in_tk(self):
        self._cancel_math_indicator_follow_job()
        if self._math_indicator_win is None:
            return
        try:
            if self._math_indicator_win.winfo_exists():
                self._math_indicator_win.destroy()
        except Exception:
            pass
        self._math_indicator_win = None

    def _position_math_indicator_in_tk(self):
        if not self._math_indicator_win:
            return
        try:
            if not self._math_indicator_win.winfo_exists():
                self._math_indicator_win = None
                return

            self._math_indicator_win.update_idletasks()
            screen_w = self._math_indicator_win.winfo_screenwidth()
            screen_h = self._math_indicator_win.winfo_screenheight()
            win_w = self._math_indicator_win.winfo_reqwidth()
            win_h = self._math_indicator_win.winfo_reqheight()

            x = screen_w - win_w - 20
            y = screen_h - win_h - 130
            self._math_indicator_win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        except Exception:
            pass

    def _schedule_math_indicator_follow_in_tk(self):
        self._cancel_math_indicator_follow_job()
        if not self._math_mode or not self._math_indicator_win or not self._tk_root:
            return

        def _refresh():
            try:
                if not self._math_mode or not self._math_indicator_win or not self._math_indicator_win.winfo_exists():
                    self._math_indicator_follow_job = None
                    return
                self._position_math_indicator_in_tk()
                self._math_indicator_follow_job = self._tk_root.after(2000, _refresh)
            except Exception:
                self._math_indicator_follow_job = None

        self._math_indicator_follow_job = self._tk_root.after(2000, _refresh)

    def _sync_math_indicator_in_tk(self):
        try:
            import tkinter as tk

            if not self._tk_root:
                return

            if not self._math_mode:
                self._close_math_indicator_in_tk()
                return

            if self._math_indicator_win and not self._math_indicator_win.winfo_exists():
                self._math_indicator_win = None

            if self._math_indicator_win is None:
                win = tk.Toplevel(self._tk_root)
                win.overrideredirect(True)
                win.attributes('-topmost', True)
                win.attributes('-alpha', 0.94)
                win.configure(bg='#1f2530')

                frame = tk.Frame(
                    win,
                    bg='#1f2530',
                    highlightbackground='#4FC3F7',
                    highlightthickness=1,
                    padx=8,
                    pady=5,
                )
                frame.pack(fill='both', expand=True)

                symbol = tk.Label(
                    frame,
                    text='∑',
                    font=('Segoe UI', 13, 'bold'),
                    fg='#4FC3F7',
                    bg='#1f2530',
                )
                symbol.pack(side='left')

                text = tk.Label(
                    frame,
                    text='MATH',
                    font=('Segoe UI', 9, 'bold'),
                    fg='#EAF6FF',
                    bg='#1f2530',
                )
                text.pack(side='left', padx=(6, 0))

                for widget in (win, frame, symbol, text):
                    widget.bind('<Button-1>', lambda event: 'break')

                self._math_indicator_win = win

            self._position_math_indicator_in_tk()
            self._math_indicator_win.deiconify()
            self._schedule_math_indicator_follow_in_tk()
        except Exception as e:
            print(f"[TRAY] Ошибка math-indicator: {e}")

    def _do_show_popup_in_tk(self, text, is_command=False, command_name="", trigger_word="", clipboard_preview=""):
        """Creates the popup as a Toplevel inside the single Tk thread.
        Создаёт popup как Toplevel внутри единого Tk-потока."""
        try:
            import tkinter as tk

            if not self._tk_root:
                return

            # Reset the close flag for the new popup.
            # Сбрасываем флаг закрытия для нового popup
            self._popup_close_flag = False

            win = tk.Toplevel(self._tk_root)
            win.overrideredirect(True)
            win.attributes('-topmost', True)
            win.attributes('-alpha', 0.92)
            win.withdraw()

            if is_command:
                bg_color = '#1a2e1a'
                border_color = '#4CAF50'
                header_color = '#4CAF50'
                display_text = trigger_word if trigger_word else text
                text_color = '#A5D6A7'
            else:
                bg_color = '#1e1e1e'
                border_color = '#4FC3F7'
                header_color = '#888888'
                display_text = text if len(text) <= 200 else text[:200] + "…"
                text_color = '#FFFFFF'

            win.configure(bg=bg_color)

            frame = tk.Frame(win, bg=bg_color, highlightbackground=border_color,
                             highlightthickness=2, padx=16, pady=12)
            frame.pack(fill='both', expand=True)

            if is_command:
                tk.Label(
                    frame, text=self._t("tray.popup_command"), font=("Segoe UI", 13, "bold"),
                    fg=header_color, bg=bg_color
                ).pack(anchor='center')
                if command_name:
                    tk.Label(
                        frame, text=command_name, font=("Segoe UI", 13),
                        fg=header_color, bg=bg_color
                    ).pack(anchor='center', pady=(2, 0))
                tk.Label(
                    frame, text=display_text, font=("Segoe UI", 13, "bold"),
                    fg=text_color, bg=bg_color, wraplength=450, justify='center'
                ).pack(anchor='center', pady=(8, 0))

                # Preview of copied text.
                # Превью скопированного текста
                if clipboard_preview:
                    tk.Frame(frame, bg='#3a5a3a', height=1).pack(
                        fill='x', pady=(8, 4)
                    )
                    tk.Label(
                        frame, text=self._t("tray.popup_copied"),
                        font=("Segoe UI", 9), fg='#6a9a6a', bg=bg_color, anchor='w'
                    ).pack(anchor='w')
                    tk.Label(
                        frame, text=clipboard_preview,
                        font=("Consolas", 9), fg='#8BC34A', bg=bg_color,
                        wraplength=450, justify='left', anchor='w'
                    ).pack(anchor='w', pady=(2, 0))
            else:
                tk.Label(
                    frame, text=self._t("tray.popup_recognized"), font=("Segoe UI", 10),
                    fg=header_color, bg=bg_color, anchor='w'
                ).pack(anchor='w')
                tk.Label(
                    frame, text=display_text, font=("Segoe UI", 13, "bold"),
                    fg=text_color, bg=bg_color, wraplength=450, justify='left', anchor='w'
                ).pack(anchor='w', pady=(4, 0))

            win.update_idletasks()

            screen_w = win.winfo_screenwidth()
            screen_h = win.winfo_screenheight()
            win_w = win.winfo_reqwidth()
            win_h = win.winfo_reqheight()
            x = screen_w - win_w - 20
            y = screen_h - win_h - 80
            win.geometry(f"+{x}+{y}")
            win.deiconify()

            def close_win(event=None):
                try:
                    win.destroy()
                except Exception:
                    pass

            win.bind('<Button-1>', close_win)
            frame.bind('<Button-1>', close_win)

            auto_close_ms = 3000 if is_command else 4000
            close_time = time.time() + auto_close_ms / 1000.0

            def _check_close():
                try:
                    if not win.winfo_exists():
                        return
                    if self._popup_close_flag or time.time() >= close_time:
                        win.destroy()
                        return
                    win.after(100, _check_close)
                except Exception:
                    pass

            win.after(100, _check_close)
        except Exception as e:
            print(f"[TRAY] Ошибка popup: {e}")

    def _update_menu(self):
        """Debounced menu update, limited to at most once every 0.3 seconds.
        Debounced обновление меню — не чаще раза в 0.3с."""
        now = time.time()
        with self._menu_update_lock:
            self._last_menu_update = now
            if self._menu_update_pending:
                return
            self._menu_update_pending = True

        def _delayed():
            time.sleep(0.3)
            with self._menu_update_lock:
                self._menu_update_pending = False
            self._enqueue_ui(self._do_update_menu)

        threading.Thread(target=_delayed, daemon=True).start()

    # --- Icon ---
    # --- Иконка ---

    def _get_icon_path(self, filename):
        """Returns the ICO path: frozen -> _MEIPASS/exe dir, dev -> src/ or project root.
        Путь к ICO файлу: frozen → _MEIPASS/exe dir, dev → src/ или корень."""
        if getattr(sys, 'frozen', False):
            meipass = Path(getattr(sys, '_MEIPASS', ''))
            if meipass and (meipass / filename).exists():
                return meipass / filename
            return Path(sys.executable).parent / filename
        # In dev mode, try src/ first and then the project root.
        # Dev: src/ → корень проекта
        src_path = Path(__file__).parent / filename
        if src_path.exists():
            return src_path
        root_path = Path(__file__).parent.parent / filename
        if root_path.exists():
            return root_path
        return src_path

    def _load_state_icons(self):
        """Loads bee icons for all application states.
        Загружает иконки пчелы для всех состояний."""
        self._state_icons = {}
        icon_map = {
            self.STATE_OFF: 'voxbee_off.ico',
            self.STATE_READY: 'voxbee.ico',
            self.STATE_RECORDING: 'voxbee_recording.ico',
        }
        for state, filename in icon_map.items():
            path = self._get_icon_path(filename)
            try:
                img = Image.open(str(path))
                img = img.resize((256, 256), Image.LANCZOS)
                img = img.convert('RGBA')
                self._state_icons[state] = img
                print(f"[TRAY] Иконка {filename} загружена")
            except Exception as e:
                print(f"[TRAY] Иконка {filename} не найдена: {e}")
                self._state_icons[state] = self._create_fallback_icon(state)

    def _create_fallback_icon(self, state):
        """Fallback icon: a simple circle when ICO files are missing.
        Fallback — простой круг если ICO файлы не найдены."""
        size = 256
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        colors = {
            self.STATE_OFF: '#444444',
            self.STATE_READY: '#2ECC71',
            self.STATE_RECORDING: '#E74C3C',
        }
        color = colors.get(state, '#444444')
        p = 8
        draw.ellipse([p, p, size - p, size - p], fill=color)
        return img

    def _get_state_icon(self, state):
        """Returns the loaded icon for the given state.
        Возвращает загруженную иконку для состояния."""
        if not hasattr(self, '_state_icons') or not self._state_icons:
            self._load_state_icons()
        return self._state_icons.get(state, self._state_icons.get(self.STATE_OFF))

    # --- Menu ---
    # --- Меню ---

    def _get_menu(self):

        def toggle_label(item):
            return self._t("tray.turn_off") if self.state != self.STATE_OFF else self._t("tray.turn_on")

        def mode_label(item):
            return self._t("tray.auto_mode_on") if self._vad_mode else self._t("tray.auto_mode_off")

        def gpu_label(item):
            return self._t("tray.gpu_on") if self._use_gpu else self._t("tray.gpu_off")

        # Submenus.
        # Подменю
        mic_submenu = pystray.Menu(*self._build_mic_items())
        model_submenu = pystray.Menu(*self._build_model_items())
        fix_submenu = pystray.Menu(*self._build_fix_items())
        trigger_submenu = pystray.Menu(*self._build_trigger_items())
        model_display = self._get_model_display_name()

        return pystray.Menu(
            pystray.MenuItem(toggle_label, self._on_toggle_click, default=True),
            pystray.MenuItem(mode_label, self._on_mode_click),
            pystray.MenuItem(
                self._trigger_menu_label(),
                trigger_submenu
            ), 
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                self._t("tray.microphone", name=self._mic_name[:25]),
                mic_submenu
            ),
            pystray.MenuItem(
                self._t("tray.model", name=model_display),
                model_submenu
            ),
            pystray.MenuItem(gpu_label, self._on_gpu_click),
            pystray.MenuItem(self._short_speech_label(), self._on_short_speech_click),
            pystray.MenuItem(self._warmup_label(), self._on_warmup_click),
            pystray.MenuItem(self._noise_filter_label(), self._on_noise_filter_click),
            pystray.MenuItem(self._math_mode_label(), self._on_math_mode_click),            
            pystray.MenuItem(self._show_recognition_label(), self._on_show_recognition_click),
            pystray.MenuItem(self._grid_overlay_label(), self._on_grid_overlay_click),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                self._get_fix_menu_label(),
                fix_submenu
            ),
            pystray.MenuItem(
                self._get_commands_menu_label(),
                pystray.Menu(*self._build_commands_items())
            ),
            pystray.MenuItem(
                self._t("tray.mouse_step", step=self._mouse_step),
                pystray.Menu(*self._build_mouse_step_items())
            ),

            pystray.MenuItem(
                self._script_label(),
                pystray.Menu(*self._build_script_items())
            ),
            pystray.MenuItem(
                self._focus_menu_label(),
                pystray.Menu(*self._build_focus_items())
            ),
            pystray.MenuItem(
                self._log_menu_label(),
                pystray.Menu(*self._build_log_items())
            ),
            pystray.MenuItem(
                self._t("tray.language"),
                pystray.Menu(*self._build_language_items())
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._t("tray.settings"), self._on_settings_click),
            pystray.MenuItem(self._t("tray.about"), self._on_about_click),
            pystray.MenuItem(self._autostart_label(), self._on_autostart_click),            
            pystray.MenuItem(self._t("tray.exit"), self._on_quit_click),
        )

    def _trigger_menu_label(self):
        from mouse_listener import config_to_trigger, trigger_to_label
        trigger = config_to_trigger(self._trigger_button)
        label = trigger_to_label(trigger, self._language)
        return self._t("tray.record_button", label=label)

    def _build_trigger_items(self):
        from mouse_listener import config_to_trigger, trigger_to_label
        items = []

        # Show the current trigger.
        # Показать текущую
        trigger = config_to_trigger(self._trigger_button)
        current_label = trigger_to_label(trigger, self._language)
        items.append(pystray.MenuItem(
            self._t("tray.current", label=current_label),
            None, enabled=False
        ))

        items.append(pystray.Menu.SEPARATOR)

        # "Assign" button.
        # Кнопка "Назначить"
        items.append(pystray.MenuItem(
            self._t("tray.assign_button"),
            self._on_capture_trigger
        ))

        # Quick reset back to the middle button.
        # Быстрый сброс на колёсико
        items.append(pystray.MenuItem(
            self._t("tray.reset_middle"),
            self._on_reset_trigger
        ))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem(
            self._t("tray.hold_modifier"),
            None, enabled=False
        ))

        return items

    def _build_language_items(self):
        def make_cb(lang):
            def cb(icon, item):
                self.set_language(lang)
                if self.on_language_change:
                    self.on_language_change(lang)
            return cb

        return [
            pystray.MenuItem(
                self._t("tray.language_ru") if self._language == "ru" else self._t("tray.language_ru_off"),
                make_cb("ru")
            ),
            pystray.MenuItem(
                self._t("tray.language_en_on") if self._language == "en" else self._t("tray.language_en"),
                make_cb("en")
            ),
        ]

    def _on_capture_trigger(self, icon, item):
        """Starts trigger capture in a separate thread.
        Запускает захват кнопки в отдельном потоке."""
        import threading
        threading.Thread(target=self._do_capture, daemon=True).start()
    
    def _do_capture(self):
        """Opens the trigger assignment window in the Tk thread.
        Открывает окно назначения кнопки — в Tk-потоке."""
        self._run_in_tk(self._do_capture_in_tk)

    def _do_capture_in_tk(self):
        """Creates the trigger assignment window as a Toplevel.
        Создаёт окно назначения кнопки как Toplevel."""
        import tkinter as tk
        from pynput import mouse as pmouse
        from pynput import keyboard as pkeyboard

        if not self._tk_root:
            return

        win = tk.Toplevel(self._tk_root)
        win.title(self._t("tray.assign_title"))
        win.overrideredirect(True)
        win.geometry("600x400")
        win.resizable(True, True)
        win.attributes('-topmost', True)
        win.configure(bg='#2b2b2b')

        win.update_idletasks()
        x = (win.winfo_screenwidth() - 420) // 2
        y = (win.winfo_screenheight() - 200) // 2
        win.geometry(f"+{x}+{y}")

        captured = {"button": None, "modifiers": []}
        mouse_listener = [None]
        key_listener = [None]

        tk.Label(
            win, text=self._t("tray.assign_hint"),
            font=("Segoe UI", 13), fg='#cccccc', bg='#2b2b2b'
        ).pack(pady=(18, 5))

        tk.Label(
            win, text=self._t("tray.assign_modifiers"),
            font=("Segoe UI", 9), fg='#888888', bg='#2b2b2b'
        ).pack()

        display_label = tk.Label(
            win, text=self._t("tray.waiting"),
            font=("Segoe UI", 16, "bold"), fg='#4FC3F7', bg='#2b2b2b'
        )
        display_label.pack(pady=(12, 2))

        warn_label = tk.Label(
            win, text="",
            font=("Segoe UI", 9), fg='#FFA726', bg='#2b2b2b'
        )
        warn_label.pack(pady=(0, 2))

        btn_frame = tk.Frame(win, bg='#2b2b2b')
        btn_frame.pack(pady=(8, 0))

        save_btn = tk.Button(
            btn_frame, text=self._t("common.save"), font=("Segoe UI", 11),
            state='disabled', width=14,
            command=lambda: _save_and_close(),
            bg='#3a3a3a', fg='#cccccc',
            activebackground='#4FC3F7', activeforeground='#000000',
            relief='flat', bd=0, cursor='hand2',
            disabledforeground='#555555'
        )
        save_btn.pack(side='left', padx=8)

        cancel_btn = tk.Button(
            btn_frame, text=self._t("common.cancel"), font=("Segoe UI", 11),
            width=10, command=lambda: _cancel(),
            bg='#3a3a3a', fg='#cccccc',
            activebackground='#FF5252', activeforeground='#FFFFFF',
            relief='flat', bd=0, cursor='hand2'
        )
        cancel_btn.pack(side='left', padx=8)

        def _update_display(trigger):
            from mouse_listener import trigger_to_label
            label = trigger_to_label(trigger, self._language)
            try:
                if win.winfo_exists():
                    display_label.config(text=label, fg='#4FC3F7')
                    warn_label.config(text="")
                    save_btn.config(state='normal')
            except Exception:
                pass

        def _on_mouse_capture(x_pos, y_pos, button, pressed):
            if not pressed:
                return
            from mouse_listener import get_button_name, get_current_modifiers
            btn = get_button_name(button)
            if btn == "left":
                return
            mods = get_current_modifiers()
            captured["button"] = btn
            captured["modifiers"] = mods
            try:
                win.after(0, lambda: _update_display(captured))
            except Exception:
                pass

        PYNPUT_KEY_MAP = {
            'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
            'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8',
            'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12',
            'insert': 'insert', 'delete': 'delete',
            'home': 'home', 'end': 'end',
            'page_up': 'page_up', 'page_down': 'page_down',
            'pause': 'pause', 'scroll_lock': 'scroll_lock',
            'num_lock': 'num_lock', 'caps_lock': 'caps_lock',
            'print_screen': 'print_screen',
        }

        def _on_pynput_key(key):
            if key in (pkeyboard.Key.ctrl_l, pkeyboard.Key.ctrl_r,
                       pkeyboard.Key.alt_l, pkeyboard.Key.alt_r, pkeyboard.Key.alt_gr,
                       pkeyboard.Key.shift_l, pkeyboard.Key.shift_r):
                return

            from mouse_listener import get_current_modifiers
            mods = get_current_modifiers()

            key_name = getattr(key, 'name', None)
            if key_name:
                mapped = PYNPUT_KEY_MAP.get(key_name.lower())
                if mapped:
                    captured["button"] = f"key:{mapped}"
                    captured["modifiers"] = mods
                    try:
                        win.after(0, lambda: _update_display(captured))
                    except Exception:
                        pass
                    return

            char = getattr(key, 'char', None)
            if char:
                char_name = char.lower()
                captured["button"] = f"key:{char_name}"
                captured["modifiers"] = mods
                try:
                    if mods:
                        win.after(0, lambda: _update_display(captured))
                    else:
                        def _show_warning():
                            _update_display(captured)
                            try:
                                if win.winfo_exists():
                                    display_label.config(fg='#FFA726')
                                    warn_text = self._t("tray.key_warning", key=char_name.upper())
                                    warn_label.config(text=warn_text)
                            except Exception:
                                pass
                        win.after(0, _show_warning)
                except Exception:
                    pass

        def _save_and_close():
            if captured["button"]:
                from mouse_listener import trigger_to_config, trigger_to_label
                config_str = trigger_to_config(captured)
                self._trigger_button = config_str
                if self.on_trigger_change:
                    self.on_trigger_change(config_str)
                self._update_menu()
                label = trigger_to_label(captured, self._language)
                if self.icon:
                    self.icon.title = self._t("tray.button_title", label=label)
                print(f"[TRAY] ✅ Record button: {label}")
            _cleanup()

        def _cancel():
            _cleanup()

        def _cleanup():
            if mouse_listener[0]:
                try:
                    mouse_listener[0].stop()
                except Exception:
                    pass
            if key_listener[0]:
                try:
                    key_listener[0].stop()
                except Exception:
                    pass
            try:
                if win.winfo_exists():
                    win.destroy()
            except Exception:
                pass

        ml = pmouse.Listener(on_click=_on_mouse_capture)
        ml.start()
        mouse_listener[0] = ml

        kl = pkeyboard.Listener(on_press=_on_pynput_key)
        kl.start()
        key_listener[0] = kl

        win.focus_force()
        win.protocol("WM_DELETE_WINDOW", _cancel)

    def _on_reset_trigger(self, icon, item):
        """Resets the trigger back to the middle mouse button.
        Сброс на среднюю кнопку."""
        self._trigger_button = "middle"
        if self.on_trigger_change:
            self.on_trigger_change("middle")
        self._update_menu()

    def _script_label(self):
        try:
            from script_manager import get_scripts_count
            count = get_scripts_count()
            if count > 0:
                return self._t("tray.scripts_count", count=count)
        except Exception:
            pass
        return self._t("tray.scripts")

    def _build_script_items(self):
        """Builds the scripts submenu: list plus management actions.
        Подменю скриптов: список + управление."""
        items = []

        # Script management UI entry.
        # Управление скриптами — GUI
        items.append(pystray.MenuItem(
            self._t("tray.script_manager"),
            self._on_open_scripts_manager
        ))

        items.append(pystray.MenuItem(
            self._t("tray.scripts_folder"),
            self._on_open_scripts_dir
        ))

        items.append(pystray.MenuItem(
            self._t("common.reload"),
            self._on_reload_scripts
        ))

        items.append(pystray.Menu.SEPARATOR)

        # Script list preview.
        # Список скриптов
        try:
            from script_manager import get_all_scripts
            scripts = get_all_scripts()
            if scripts:
                for sid, s in scripts.items():
                    enabled = s.get("enabled", True)
                    prefix = "✅" if enabled else "🔲"
                    name = s.get("name", sid)
                    triggers = s.get("triggers", [])
                    trigger_preview = triggers[0] if triggers else "?"
                    items.append(pystray.MenuItem(
                        f"  {prefix} {name} ({trigger_preview})",
                        None, enabled=False
                    ))
            else:
                items.append(pystray.MenuItem(
                    self._t("tray.no_scripts"),
                    None, enabled=False
                ))
        except Exception:
            items.append(pystray.MenuItem(
                self._t("tray.load_error"),
                None, enabled=False
            ))

        return items


    def _on_open_scripts_manager(self, icon, item):
        """Opens the script management UI.
        Открывает GUI управления скриптами."""
        self._run_in_tk(self._open_scripts_manager_in_tk)

    def _open_scripts_manager_in_tk(self):
        """Opens the script window in the Tk thread.
        Открывает окно скриптов в Tk-потоке."""
        try:
            from script_manager_ui import open_scripts_window
            from script_manager import reload_scripts

            def on_changed():
                reload_scripts()
                self._update_menu()

            open_scripts_window(self._tk_root, on_scripts_changed=on_changed)
        except Exception as e:
            print(f"[TRAY] Ошибка открытия менеджера скриптов: {e}")
            import traceback
            traceback.print_exc()

    def _on_open_scripts_dir(self, icon, item):
        """Opens the scripts folder.
        Открывает папку скриптов."""
        try:
            from script_manager import get_scripts_dir, ensure_scripts_dir
            ensure_scripts_dir()
            import os
            os.startfile(str(get_scripts_dir()))
        except Exception as e:
            print(f"[TRAY] Ошибка: {e}")

    def _on_reload_scripts(self, icon, item):
        """Reloads scripts from disk.
        Перезагружает скрипты."""
        try:
            from script_manager import reload_scripts
            reload_scripts()
            self._update_menu()
        except Exception as e:
            print(f"[TRAY] Ошибка: {e}")


    def _warmup_label(self):
        enabled = self._fix_settings.get("warmup_on_start", True)
        if enabled:
            return self._t("tray.warmup_on")
        return self._t("tray.warmup_off")

    def _on_warmup_click(self, icon, item):
        current = self._fix_settings.get("warmup_on_start", True)
        self._fix_settings["warmup_on_start"] = not current
        if self.on_warmup_toggle:
            self.on_warmup_toggle(not current)
        self._update_menu()

    def _get_fix_menu_label(self):
        """Returns the text-fixing submenu title.
        Заголовок подменю исправлений."""
        enabled = self._fix_settings.get("text_fix_enabled", True)
        if enabled:
            return self._t("tray.text_fix_on")
        return self._t("tray.text_fix_off")

    def _build_fix_items(self):
        """Builds the text-fixing submenu items.
        Пункты подменю исправления текста."""
        items = []
        s = self._fix_settings
        enabled = s.get("text_fix_enabled", True)

        # Main toggle.
        # Главный переключатель
        def make_toggle_main():
            def cb(icon, item):
                new_val = not s.get("text_fix_enabled", True)
                s["text_fix_enabled"] = new_val
                if self.on_fix_toggle:
                    self.on_fix_toggle("text_fix_enabled", new_val)
                self._update_menu()
            return cb

        main_prefix = "✅" if enabled else "🔲"
        items.append(pystray.MenuItem(
            self._t("tray.fix_all", prefix=main_prefix),
            make_toggle_main()
        ))

        items.append(pystray.Menu.SEPARATOR)

        # Individual stages.
        # Отдельные этапы
        stages = [
            ("text_fix_hallucinations", self._t("tray.fix_hallucinations"), "👻"),
            ("text_fix_dictionary", self._t("tray.fix_dictionary"), "📖"),
            ("text_fix_user_dict", self._t("tray.fix_user_dictionary", count=self._user_dict_count), "📝"),
            ("text_fix_repetitions", self._t("tray.fix_repetitions"), "🔁"),
            ("text_fix_punctuation", self._t("tray.fix_punctuation"), "✍️"),
        ]

        for key, label, emoji in stages:
            val = s.get(key, True)
            prefix = "✅" if (val and enabled) else "🔲"
            # Sub-stages stay disabled when the whole pipeline is off.
            # Подэтапы неактивны если всё выключено
            is_enabled = enabled

            def make_toggle(k):
                def cb(icon, item):
                    new_val = not s.get(k, True)
                    s[k] = new_val
                    if self.on_fix_toggle:
                        self.on_fix_toggle(k, new_val)
                    self._update_menu()
                return cb

            items.append(pystray.MenuItem(
                f"  {prefix} {emoji} {label}",
                make_toggle(key),
                enabled=is_enabled
            ))

        items.append(pystray.Menu.SEPARATOR)

        # Reload dictionary.
        # Перезагрузить словарь
        def on_reload(icon, item):
            if self.on_reload_dict:
                self.on_reload_dict()

        items.append(pystray.MenuItem(
            self._t("tray.reload_dictionary"),
            on_reload,
            enabled=enabled
        ))

        # Open dictionary folder.
        # Открыть папку словаря
        def on_open_dict_dir(icon, item):
            try:
                from text_fixer import get_user_dict_path
                dict_path = get_user_dict_path()
                parent_dir = dict_path.parent
                if parent_dir.exists():
                    import os
                    os.startfile(str(parent_dir))
            except Exception as e:
                print(f"[TRAY] Ошибка открытия папки: {e}")

        items.append(pystray.MenuItem(
            self._t("tray.dictionary_folder"),
            on_open_dict_dir
        ))

        return items

    def _get_commands_menu_label(self):
        """Returns the commands submenu title.
        Заголовок подменю команд."""
        if not self._commands_enabled:
            return self._t("tray.commands_off")
        if self._commands_count > 0:
            return self._t("tray.commands_count", count=self._commands_count)
        return self._t("tray.commands")

    def _build_commands_items(self):
        """Builds the commands and aliases submenu.
        Пункты подменю команд и алиасов."""
        items = []

        # Main toggle.
        # Главный переключатель
        def on_toggle_commands(icon, item):
            self._commands_enabled = not self._commands_enabled
            if self.on_commands_toggle:
                self.on_commands_toggle(self._commands_enabled)
            self._update_menu()

        prefix = "✅" if self._commands_enabled else "🔲"
        items.append(pystray.MenuItem(
            self._t("tray.recognize_commands", prefix=prefix),
            on_toggle_commands
        ))

        items.append(pystray.Menu.SEPARATOR)

        # Reload commands and aliases.
        # Перезагрузить
        def on_reload_all(icon, item):
            if self.on_reload_commands:
                self.on_reload_commands()

        items.append(pystray.MenuItem(
            self._t("tray.reload_commands"),
            on_reload_all,
            enabled=self._commands_enabled
        ))

        items.append(pystray.Menu.SEPARATOR)

        # Informational items.
        # Информация
        items.append(pystray.MenuItem(
            self._t("tray.triggers_count", count=self._commands_count),
            None, enabled=False
        ))

        items.append(pystray.Menu.SEPARATOR)

        # Open the folder with configuration files.
        # Открыть папку с файлами настроек
        def on_open_data_dir(icon, item):
            try:
                from app_paths import DATA_DIR
                import os
                os.makedirs(str(DATA_DIR), exist_ok=True)
                os.startfile(str(DATA_DIR))
            except Exception as e:
                print(f"[TRAY] Ошибка открытия папки: {e}")

        items.append(pystray.MenuItem(
            self._t("tray.settings_folder"),
            on_open_data_dir
        ))

        items.append(pystray.MenuItem(
            self._t("tray.commands_json"),
            None, enabled=False
        ))

        items.append(pystray.MenuItem(
            self._t("tray.aliases_json"),
            None, enabled=False
        ))

        return items
     

    def _get_model_display_name(self):
        if self._model_name == "auto":
            if self._model_list:
                return f"Auto ({self._model_list[0]['label']})"
            return "Auto"
        for m in self._model_list:
            if m['name'] == self._model_name:
                return m['label']
        return self._model_name.replace("ggml-", "").replace(".bin", "")

    def _build_mic_items(self):
        items = []
        
        # "Refresh list" button.
        # Кнопка "Обновить список"
        def on_refresh(icon, item):
            try:
                if self.on_mic_refresh:
                    self._mic_list = self.on_mic_refresh()
                else:
                    from mic_selector import list_microphones
                    self._mic_list = list_microphones()
                print(f"[TRAY] 🔄 Микрофоны обновлены: {len(self._mic_list)} шт.")
                self._update_menu()
            except Exception as e:
                print(f"[TRAY] Ошибка обновления: {e}")

        items.append(pystray.MenuItem(self._t("tray.refresh_list"), on_refresh))
        items.append(pystray.Menu.SEPARATOR)

        for mic in self._mic_list:
            idx = mic['index']
            name = mic['name']
            is_current = (name == self._mic_name)
            prefix = "✅ " if is_current else "🔲 "
            short_name = name[:35] + "…" if len(name) > 35 else name

            def make_cb(dev_idx, dev_name):
                def cb(icon, item):
                    self._mic_name = dev_name
                    if self.on_mic_change:
                        self.on_mic_change(dev_idx, dev_name)
                    self._update_menu()
                return cb

            items.append(pystray.MenuItem(
                f"{prefix}[{idx}] {short_name}", make_cb(idx, name)
            ))

        if len(items) <= 2:  # Только кнопка обновления + сепаратор
            items.append(pystray.MenuItem(self._t("tray.no_microphones"), None, enabled=False))
        
        return items

    def _build_model_items(self):
        items = []

        is_auto = (self._model_name == "auto")
        auto_label = self._t("tray.best_available")
        if self._model_list:
            auto_label += f" ({self._model_list[0]['label']})"

        def on_auto(icon, item):
            self._model_name = "auto"
            if self.on_model_change:
                self.on_model_change("auto")
            self._update_menu()

        items.append(pystray.MenuItem(
            f"{'✅' if is_auto else '🔲'} 🔄 Auto: {auto_label}", on_auto
        ))
        items.append(pystray.Menu.SEPARATOR)

        for m in self._model_list:
            name = m['name']
            is_current = (name == self._model_name)
            prefix = "✅ " if is_current else "🔲 "
            size = f"{m['size_mb']:.0f}MB"
            label = m['label']
            speed_short = m.get('speed', '').split(' ')[0]

            def make_cb(mn):
                def cb(icon, item):
                    self._model_name = mn
                    if self.on_model_change:
                        self.on_model_change(mn)
                    self._update_menu()
                return cb

            items.append(pystray.MenuItem(
                f"{prefix}{speed_short} {label} ({size})", make_cb(name)
            ))

        if len(items) <= 2:
            items.append(pystray.MenuItem(self._t("tray.no_models"), None, enabled=False))
        return items

    # --- Handlers ---
    # --- Обработчики ---

    def _on_toggle_click(self, icon, item):
        if self.state == self.STATE_OFF:
            self.set_state(self.STATE_READY)
            if self.on_toggle:
                self.on_toggle(True)
        else:
            self.set_state(self.STATE_OFF)
            if self.on_toggle:
                self.on_toggle(False)

    def _on_mode_click(self, icon, item):
        self._vad_mode = not self._vad_mode
        self._update_menu()
        if self.on_mode_change:
            self.on_mode_change(self._vad_mode)

    def _on_gpu_click(self, icon, item):
        self._use_gpu = not self._use_gpu
        self._update_menu()
        if self.on_gpu_toggle:
            self.on_gpu_toggle(self._use_gpu)

    def _on_quit_click(self, icon, item):
        self.set_state(self.STATE_OFF)
        if self.on_quit:
            self.on_quit()
        self.stop()

    def set_state(self, state):
        """Updates the tray icon state without blocking.
        Неблокирующее обновление состояния иконки."""
        self.state = state
        if self.icon:
            image = self._get_state_icon(state)
            tooltips = {
                self.STATE_OFF: self._t("tray.off"),
                self.STATE_READY: self._t("tray.ready"),
                self.STATE_RECORDING: self._t("tray.recording"),
            }
            title = tooltips.get(state, "VoxBee")
            self._enqueue_ui(self._do_set_icon, image)
            self._enqueue_ui(self._do_set_title, title)
            self._update_menu()

    def start(self):
        global _tray_instance
        _tray_instance = self
        self._load_state_icons()
        # Initialize pystray.Icon with the YELLOW ready icon
        # so Windows caches it in "Other system tray icons".
        # The visible off/ready/recording state will then be applied via set_state().
        # Для инициализации pystray.Icon используем ЖЁЛТУЮ иконку (ready),
        # чтобы Windows закэшировала её в "Другие значки панели задач".
        # Визуальное состояние (off/ready/recording) обновится через set_state().
        init_icon = self._get_state_icon(self.STATE_READY)
        self.icon = pystray.Icon(
            name="voxbee",
            icon=init_icon,
            title=self._t("tray.off"),
            menu=self._get_menu(),
        )
        self._start_ui_worker()
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()
        time.sleep(0.5)
        # Now apply the real OFF state: the tray icon becomes gray,
        # while Windows keeps the yellow cached icon for the settings list.
        # Теперь ставим реальное состояние OFF — иконка в трее станет серой,
        # но Windows уже закэшировала жёлтую для списка настроек.
        self.set_state(self.STATE_OFF)

    def stop(self):
        # Stop the Tk thread.
        # Останавливаем Tk-поток
        if self._tk_root:
            try:
                self._tk_root.after(0, self._close_math_indicator_in_tk)
            except Exception:
                pass
            try:
                self._tk_root.after(0, self._tk_root.quit)
            except Exception:
                pass

        self._ui_running = False

        global _tray_instance
        _tray_instance = None        
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    def _short_speech_label(self):
        enabled = self._fix_settings.get("vad_accept_short_speech", False)
        return self._t("tray.short_speech_on") if enabled else self._t("tray.short_speech_off")

    def _on_short_speech_click(self, icon, item):
        current = self._fix_settings.get("vad_accept_short_speech", False)
        self._fix_settings["vad_accept_short_speech"] = not current
        if self.on_short_speech_toggle:
            self.on_short_speech_toggle(not current)
        self._update_menu()

    def _noise_filter_label(self):
        return self._t("tray.noise_on") if self._noise_filter_enabled else self._t("tray.noise_off")

    def _on_noise_filter_click(self, icon, item):
        self._noise_filter_enabled = not self._noise_filter_enabled
        if self.on_noise_filter_toggle:
            self.on_noise_filter_toggle(self._noise_filter_enabled)
        self._update_menu()

    def _show_recognition_label(self):
        return self._t("tray.show_recognition_on") if self._show_recognition_result else self._t("tray.show_recognition_off")

    def _on_show_recognition_click(self, icon, item):
        self._show_recognition_result = not self._show_recognition_result
        if self.on_show_recognition_toggle:
            self.on_show_recognition_toggle(self._show_recognition_result)
        self._update_menu()


    def _math_mode_label(self):
        return self._t("tray.math_on") if self._math_mode else self._t("tray.math_off")

    def _on_math_mode_click(self, icon, item):
        self._math_mode = not self._math_mode
        if self.on_math_mode_toggle:
            self.on_math_mode_toggle(self._math_mode)
        self._update_menu()
        
    def _grid_overlay_label(self):
        from mouse_controller import is_grid_overlay_visible
        return self._t("tray.grid_on") if is_grid_overlay_visible() else self._t("tray.grid_off")

    def _on_grid_overlay_click(self, icon, item):
        from mouse_controller import is_grid_overlay_visible, show_grid_overlay, hide_grid_overlay
        if is_grid_overlay_visible():
            hide_grid_overlay()
        else:
            show_grid_overlay()
        self._update_menu() 

    def _autostart_label(self):
        return self._t("tray.autostart_on") if self._autostart_enabled else self._t("tray.autostart_off")

    def _on_autostart_click(self, icon, item):
        self._autostart_enabled = not self._autostart_enabled
        if self.on_autostart_toggle:
            self.on_autostart_toggle(self._autostart_enabled)
        self._update_menu()


    def _on_settings_click(self, icon, item):
        """Opens the settings window in the Tk thread.
        Открывает окно настроек в Tk-потоке."""
        if self.on_open_settings:
            self._run_in_tk(self.on_open_settings)        

    def _on_about_click(self, icon, item):
        if self.on_open_about:
            self._run_in_tk(self.on_open_about)

    def _log_menu_label(self):
        if self._log_enabled:
            return self._t("tray.logging_on")
        return self._t("tray.logging_off")

    def _build_log_items(self):
        items = []

        # Enable/disable logging.
        # Вкл/выкл
        def on_toggle_log(icon, item):
            self._log_enabled = not self._log_enabled
            if self.on_log_toggle:
                self.on_log_toggle(self._log_enabled)
            self._update_menu()

        prefix = "✅" if self._log_enabled else "🔲"
        items.append(pystray.MenuItem(
            self._t("tray.write_log", prefix=prefix),
            on_toggle_log
        ))

        items.append(pystray.Menu.SEPARATOR)

        # Current log directory.
        # Текущая папка
        if self._log_directory:
            display_dir = self._log_directory
            if len(display_dir) > 40:
                display_dir = "..." + display_dir[-37:]
        else:
            display_dir = self._t("tray.logs_default")

        items.append(pystray.MenuItem(
            f"  📂 {display_dir}",
            None, enabled=False
        ))

        # Choose folder.
        # Выбрать папку
        items.append(pystray.MenuItem(
            self._t("tray.select_folder"),
            self._on_select_log_dir
        ))

        # Reset to default.
        # Сбросить на стандартную
        items.append(pystray.MenuItem(
            self._t("tray.reset_default"),
            self._on_reset_log_dir
        ))

        # Open the logs folder.
        # Открыть папку логов
        items.append(pystray.MenuItem(
            self._t("tray.open_log_folder"),
            self._on_open_log_dir
        ))

        return items

    def _on_select_log_dir(self, icon, item):
        import threading
        threading.Thread(target=self._pick_log_dir, daemon=True).start()

    def _pick_log_dir(self):
        self._run_in_tk(self._pick_log_dir_in_tk)

    def _pick_log_dir_in_tk(self):
        try:
            from tkinter import filedialog
            if not self._tk_root:
                return
            self._tk_root.attributes('-topmost', True)
            path = filedialog.askdirectory(
                parent=self._tk_root,
                title=self._t("settings.select_log_folder"),
                initialdir=self._log_directory or None,
            )
            self._tk_root.attributes('-topmost', False)
            if path:
                self._log_directory = path
                if self.on_log_dir_change:
                    self.on_log_dir_change(path)
                self._update_menu()
        except Exception as e:
            print(f"[TRAY] Ошибка выбора папки: {e}")

    def _on_reset_log_dir(self, icon, item):
        self._log_directory = ""
        if self.on_log_dir_change:
            self.on_log_dir_change("")
        self._update_menu()

    def _on_open_log_dir(self, icon, item):
        try:
            import os
            if self._log_directory:
                log_dir = self._log_directory
            else:
                from app_paths import LOGS_DIR
                log_dir = str(LOGS_DIR)
            os.makedirs(log_dir, exist_ok=True)
            os.startfile(log_dir)
        except Exception as e:
            print(f"[TRAY] Ошибка открытия папки: {e}")

    def _build_mouse_step_items(self):
        items = []
        steps = [50, 100, 150, 200, 300, 500]

        for s in steps:
            is_current = (s == self._mouse_step)
            prefix = "✅" if is_current else "🔲"

            def make_cb(step):
                def cb(icon, item):
                    self._mouse_step = step
                    if self.on_mouse_step_change:
                        self.on_mouse_step_change(step)
                    self._update_menu()
                return cb

            items.append(pystray.MenuItem(
                f"{prefix} {s}px", make_cb(s)
            ))

        return items


    def _focus_menu_label(self):
        count = len(self._focus_positions) if self._focus_positions else 0
        if count:
            return self._t("tray.focus_points_count", count=count)
        return self._t("tray.focus_points")

    def set_focus_positions(self, positions):
        """Updates focus positions shown in the tray menu.
        Обновляет позиции фокуса для отображения в меню."""
        self._focus_positions = positions
        self._update_menu()

    def _build_focus_items(self):
        """Builds the focus-management submenu items.
        Пункты подменю управления фокусом."""
        items = []

        if not self._focus_positions:
            items.append(pystray.MenuItem(
                self._t("tray.no_focus_points"),
                None, enabled=False
            ))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem(
                self._t("tray.focus_hint_save"),
                None, enabled=False
            ))
            items.append(pystray.MenuItem(
                self._t("tray.focus_hint_voice"),
                None, enabled=False
            ))
        else:
            for label, data in self._focus_positions.items():
                short_label = label[:40] + "…" if len(label) > 40 else label

                # Support both the new and the legacy data formats.
                # Поддержка нового и старого формата
                if isinstance(data, dict):
                    pos = data.get("pos", [0, 0])
                    slot = data.get("slot", 0)
                else:
                    pos = data if isinstance(data, (list, tuple)) else [0, 0]
                    slot = 0

                x, y = pos[0], pos[1]

                def make_goto_cb(lbl):
                    def cb(icon, item):
                        if self.on_focus_position_goto:
                            self.on_focus_position_goto(lbl)
                    return cb

                def make_delete_cb(lbl):
                    def cb(icon, item):
                        if self.on_focus_position_delete:
                            self.on_focus_position_delete(lbl)
                    return cb

                def make_rename_cb(s):
                    def cb(icon, item):
                        if s:
                            self._run_in_tk(self._edit_voice_names_dialog, s)
                    return cb

                sub_items = [
                    pystray.MenuItem(self._t("tray.goto"), make_goto_cb(label)),
                    pystray.MenuItem(self._t("tray.voice_names"), make_rename_cb(slot)),
                    pystray.MenuItem(self._t("common.delete"), make_delete_cb(label)),
                ]

                items.append(pystray.MenuItem(
                    f"  📍 {short_label}",
                    pystray.Menu(*sub_items)
                ))

            items.append(pystray.Menu.SEPARATOR)

            def on_reset(icon, item):
                if self.on_focus_positions_reset:
                    self.on_focus_positions_reset()

            items.append(pystray.MenuItem(
                self._t("tray.reset_all_points"),
                on_reset
            ))

        return items

    def _edit_voice_names_dialog(self, slot):
        """Dialog for editing spoken names of a focus point.
        Диалог редактирования голосовых имён точки фокуса."""
        import tkinter as tk

        if not self._tk_root or not slot:
            return

        from focus_manager import get_voice_names, set_voice_names

        current_names = get_voice_names(slot)

        win = tk.Toplevel(self._tk_root)
        win.title(self._t("tray.voice_names_title", slot=slot))
        win.overrideredirect(True)
        win.geometry("800x600")
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.configure(bg='#2b2b2b')

        win.update_idletasks()
        cx = (win.winfo_screenwidth() - 450) // 2
        cy = (win.winfo_screenheight() - 220) // 2
        win.geometry(f"+{cx}+{cy}")
        # --- Window dragging logic via the title area ---
        # --- Логика перетаскивания окна (за заголовок) ---
        def _start_move(event):
            win.x = event.x
            win.y = event.y
        def _do_move(event):
            deltax = event.x - win.x
            deltay = event.y - win.y
            x = win.winfo_x() + deltax
            y = win.winfo_y() + deltay
            win.geometry(f"+{x}+{y}")
        
        # --- Window resize logic via the corner grip ---
        # --- Логика изменения размера (за уголок) ---
        def _start_resize(event):
            win.start_w = win.winfo_width()
            win.start_h = win.winfo_height()
            win.start_x = event.x_root
            win.start_y = event.y_root
        def _do_resize(event):
            w = win.start_w + (event.x_root - win.start_x)
            h = win.start_h + (event.y_root - win.start_y)
            win.geometry(f"{w}x{h}")        

        # Drag-style cursor.
        # Курсор в виде цветка для указания на перетаскивание
        header_label = tk.Label(
            win, text=self._t("tray.voice_commands_title", slot=slot),
            font=("Segoe UI", 13, "bold"), fg='#4FC3F7', bg='#2b2b2b',
            cursor='fleur'
        )
        header_label.pack(pady=(16, 4))
        # Bind mouse events to drag the window by the header.
        # Привязываем события мыши для перетаскивания к заголовку
        header_label.bind("<ButtonPress-1>", _start_move)
        header_label.bind("<B1-Motion>", _do_move)

        tk.Label(
            win, text=self._t("tray.voice_commands_hint"),
            font=("Segoe UI", 9), fg='#888888', bg='#2b2b2b'
        ).pack(pady=(0, 8))

        entry = tk.Entry(
            win, font=("Segoe UI", 13), width=35,
            bg='#3a3a3a', fg='#ffffff', insertbackground='#ffffff',
            relief='flat', bd=2
        )
        entry.pack(pady=(0, 12), padx=20)
        entry.insert(0, ", ".join(current_names))
        entry.focus_set()
        entry.select_range(0, 'end')

        btn_frame = tk.Frame(win, bg='#2b2b2b')
        btn_frame.pack(pady=(8, 0))

        def _save():
            raw = entry.get()
            names = [n.strip() for n in raw.split(",") if n.strip()]
            set_voice_names(slot, names)
            win.destroy()

        def _cancel():
            win.destroy()

        tk.Button(
            btn_frame, text=self._t("common.save"), font=("Segoe UI", 11),
            width=14, command=_save,
            bg='#3a3a3a', fg='#cccccc',
            activebackground='#4FC3F7', activeforeground='#000000',
            relief='flat', bd=0, cursor='hand2'
        ).pack(side='left', padx=8)

        tk.Button(
            btn_frame, text=self._t("common.cancel"), font=("Segoe UI", 11),
            width=10, command=_cancel,
            bg='#3a3a3a', fg='#cccccc',
            activebackground='#FF5252', activeforeground='#FFFFFF',
            relief='flat', bd=0, cursor='hand2'
        ).pack(side='left', padx=8)

        entry.bind('<Return>', lambda e: _save())
        # Add a visible grip for resizing.
        # Добавляем видимый уголок для изменения размера
        grip = tk.Label(
            win, text='⤢', bg='#2b2b2b', fg='#555555', 
            cursor='bottom_right_corner', font=("Segoe UI", 10)
        )
        grip.pack(side='bottom', anchor='se')
        # Bind mouse events for resizing.
        # Привязываем события мыши для изменения размера
        grip.bind("<ButtonPress-1>", _start_resize)
        grip.bind("<B1-Motion>", _do_resize)  
              
        entry.bind('<Escape>', lambda e: _cancel())

        return items










