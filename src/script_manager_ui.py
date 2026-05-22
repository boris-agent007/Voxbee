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
Tkinter GUI for managing voice scripts.
GUI-окно tkinter для управления голосовыми скриптами.

Shows the script list and supports add/edit/delete actions.
Показывает список скриптов и поддерживает добавление, редактирование и удаление.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

from ui_strings import tr


def open_scripts_window(tk_root, on_scripts_changed=None):
    """
    Opens the script-management window as a Toplevel.
    Открывает окно управления скриптами как Toplevel.

    tk_root: корневой Tk (из tray_icon._tk_root).
    tk_root: root Tk instance from tray_icon._tk_root.

    on_scripts_changed: callback при изменении скриптов.
    on_scripts_changed: callback triggered after script changes.
    """
    from script_manager import (
        get_all_scripts, add_script, delete_script, toggle_script,
        reload_scripts, generate_script_id, get_scripts_dir, ensure_scripts_dir,
    )

    if not tk_root:
        return

    lang = "ru"
    try:
        from config import load_config
        lang = load_config().get("language", "ru")
    except Exception:
        pass
    _t = lambda key, **kwargs: tr(key, lang, **kwargs)

    win = tk.Toplevel(tk_root)
    win.title(_t("scripts.title"))
    win.geometry("1400x640")
    win.minsize(700, 400)
    win.resizable(True, True)
    win.attributes('-topmost', True)
    win.configure(bg='#2b2b2b')
    win.overrideredirect(True)

    # Use a custom title bar because the window is borderless.
    # Используем собственную шапку, потому что окно без системной рамки.
    title_bar = tk.Frame(win, bg='#1e1e1e', height=72)
    title_bar.pack(fill='x', side='top')
    title_bar.pack_propagate(False)

    title_label = tk.Label(
        title_bar, text=_t("scripts.title_bar"),
        font=("Segoe UI", 12, "bold"), fg='#cccccc', bg='#1e1e1e', anchor='w'
    )
    title_label.pack(side='left', fill='x', expand=True, padx=5, pady=5)

    close_btn = tk.Label(
        title_bar, text=" ✕ ", font=("Segoe UI", 14, "bold"),
        fg='#cccccc', bg='#1e1e1e', cursor='hand2'
    )
    close_btn.pack(side='right', padx=10, pady=5)
    close_btn.bind('<Button-1>', lambda e: win.destroy())
    close_btn.bind('<Enter>', lambda e: close_btn.config(fg='#ff5555', bg='#3a3a3a'))
    close_btn.bind('<Leave>', lambda e: close_btn.config(fg='#cccccc', bg='#1e1e1e'))

    # Dragging is implemented manually for the custom title bar.
    # Перетаскивание окна реализовано вручную для собственной шапки.
    def start_drag(event):
        win._drag_x = event.x
        win._drag_y = event.y

    def do_drag(event):
        x = win.winfo_x() + event.x - win._drag_x
        y = win.winfo_y() + event.y - win._drag_y
        win.geometry(f"+{x}+{y}")

    title_bar.bind('<Button-1>', start_drag)
    title_bar.bind('<B1-Motion>', do_drag)
    title_label.bind('<Button-1>', start_drag)
    title_label.bind('<B1-Motion>', do_drag)

    # Add a resize grip because overrideredirect disables the native window frame.
    # Добавляем уголок изменения размера, потому что overrideredirect отключает системную рамку.
    resize_grip = tk.Frame(win, bg='#555555', width=16, height=16, cursor='bottom_right_corner')
    resize_grip.place(relx=1.0, rely=1.0, anchor='se')

    def start_resize(event):
        win._resize_x = event.x_root
        win._resize_y = event.y_root
        win._resize_w = win.winfo_width()
        win._resize_h = win.winfo_height()

    def do_resize(event):
        dw = event.x_root - win._resize_x
        dh = event.y_root - win._resize_y
        new_w = max(700, win._resize_w + dw)
        new_h = max(400, win._resize_h + dh)
        win.geometry(f"{new_w}x{new_h}")

    resize_grip.bind('<Button-1>', start_resize)
    resize_grip.bind('<B1-Motion>', do_resize)

    win.update_idletasks()
    x = (win.winfo_screenwidth() - 900) // 2
    y = (win.winfo_screenheight() - 500) // 2
    win.geometry(f"+{x}+{y}")
    win.bind('<Escape>', lambda e: win.destroy())

    # Script list area.
    # Область со списком скриптов.
    list_frame = tk.Frame(win, bg='#2b2b2b')
    list_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))

    tk.Label(
        list_frame, text=_t("scripts.list"), font=("Segoe UI", 11, "bold"),
        fg='#cccccc', bg='#2b2b2b', anchor='w'
    ).pack(anchor='w')

    # Pair the listbox with a scrollbar for long script lists.
    # Используем listbox вместе со scrollbar для длинных списков скриптов.
    lb_frame = tk.Frame(list_frame, bg='#2b2b2b')
    lb_frame.pack(fill='both', expand=True, pady=(5, 0))

    scrollbar = tk.Scrollbar(lb_frame, width=0)
    scrollbar.pack(side='right', fill='y')

    listbox = tk.Listbox(
        lb_frame, font=("Segoe UI", 10),
        bg='#1e1e1e', fg='#cccccc',
        selectbackground='#4FC3F7', selectforeground='#000000',
        yscrollcommand=scrollbar.set,
        height=10,
    )
    listbox.pack(side='left', fill='both', expand=True)
    scrollbar.config(command=listbox.yview)

    # Keep a parallel mapping from listbox row index to script_id.
    # Храним отдельное соответствие между индексом строки listbox и script_id.
    script_ids = []

    def refresh_list():
        try:
            listbox.delete(0, tk.END)
            script_ids.clear()
            scripts = get_all_scripts()
            for sid, s in scripts.items():
                enabled = s.get("enabled", True)
                prefix = "✅" if enabled else "🔲"
                name = s.get("name", sid)
                triggers = s.get("triggers", [])
                trigger_preview = ", ".join(triggers[:3])
                if len(triggers) > 3:
                    trigger_preview += f" (+{len(triggers)-3})"
                path_name = Path(s.get("path", "")).name or "?"
                listbox.insert(tk.END, f"{prefix} {name}  │  📄 {path_name}  │  🎙 {trigger_preview}")
                script_ids.append(sid)
        except Exception as e:
            print(f"[SCRIPTS UI] Ошибка обновления списка: {e}")

    refresh_list()

    # Action buttons under the list.
    # Кнопки действий под списком.
    btn_frame = tk.Frame(win, bg='#2b2b2b')
    btn_frame.pack(fill='x', padx=10, pady=5)

    btn_style = {
        'font': ("Segoe UI", 10),
        'bg': '#3a3a3a', 'fg': '#cccccc',
        'activebackground': '#4FC3F7', 'activeforeground': '#000000',
        'relief': 'flat', 'bd': 0, 'cursor': 'hand2',
        'padx': 12, 'pady': 4,
    }

    def on_add():
        _open_edit_dialog(win, None, None, refresh_list, on_scripts_changed)

    def on_edit():
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        sid = script_ids[idx]
        scripts = get_all_scripts()
        script_data = scripts.get(sid)
        if script_data:
            _open_edit_dialog(win, sid, script_data, refresh_list, on_scripts_changed)

    def on_delete():
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        sid = script_ids[idx]
        scripts = get_all_scripts()
        name = scripts.get(sid, {}).get("name", sid)
        if messagebox.askyesno(_t("scripts.delete_title"), _t("scripts.delete_confirm", name=name), parent=win):
            delete_script(sid)
            refresh_list()
            if on_scripts_changed:
                on_scripts_changed()

    def on_toggle():
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        sid = script_ids[idx]
        scripts = get_all_scripts()
        current = scripts.get(sid, {}).get("enabled", True)
        toggle_script(sid, not current)
        refresh_list()
        if on_scripts_changed:
            on_scripts_changed()

    def on_open_folder():
        ensure_scripts_dir()
        import os
        os.startfile(str(get_scripts_dir()))

    tk.Button(btn_frame, text=_t("scripts.add"), command=on_add, **btn_style).pack(side='left', padx=(0, 5))
    tk.Button(btn_frame, text=_t("scripts.edit"), command=on_edit, **btn_style).pack(side='left', padx=5)
    tk.Button(btn_frame, text=_t("scripts.delete"), command=on_delete, **btn_style).pack(side='left', padx=5)
    tk.Button(btn_frame, text=_t("scripts.toggle"), command=on_toggle, **btn_style).pack(side='left', padx=5)
    tk.Button(btn_frame, text=_t("scripts.folder"), command=on_open_folder, **btn_style).pack(side='right', padx=0)

    # Double click opens the edit dialog for the selected script.
    # Двойной клик открывает редактирование выбранного скрипта.
    listbox.bind('<Double-Button-1>', lambda e: on_edit())

    win.focus_force()


def _open_edit_dialog(parent, script_id, script_data, on_save_callback, on_scripts_changed):
    """
    Opens the add/edit dialog for a script.
    Открывает диалог добавления или редактирования скрипта.

    script_id=None — добавление нового.
    script_id=None означает создание нового скрипта.
    """
    from script_manager import add_script, generate_script_id, get_scripts_dir

    is_new = script_id is None

    lang = "ru"
    try:
        from config import load_config
        lang = load_config().get("language", "ru")
    except Exception:
        pass
    _t = lambda key, **kwargs: tr(key, lang, **kwargs)

    dlg = tk.Toplevel(parent)
    dlg.title(_t("scripts.add_title") if is_new else _t("scripts.edit_title"))
    dlg.geometry("680x680")
    dlg.minsize(500, 450)
    dlg.resizable(True, True)
    dlg.attributes('-topmost', True)
    dlg.configure(bg='#2b2b2b')
    dlg.overrideredirect(True)

    # Borderless dialog uses the same custom title bar pattern as the main window.
    # Диалог без рамки использует ту же кастомную шапку, что и главное окно.
    title_text = _t("scripts.add_title_bar") if is_new else _t("scripts.edit_title_bar")
    title_bar = tk.Frame(dlg, bg='#1e1e1e', height=72)
    title_bar.pack(fill='x', side='top')
    title_bar.pack_propagate(False)

    title_label = tk.Label(
        title_bar, text=title_text,
        font=("Segoe UI", 12, "bold"), fg='#cccccc', bg='#1e1e1e', anchor='w'
    )
    title_label.pack(side='left', fill='x', expand=True, padx=5, pady=8)

    close_btn = tk.Label(
        title_bar, text=" ✕ ", font=("Segoe UI", 14, "bold"),
        fg='#cccccc', bg='#1e1e1e', cursor='hand2'
    )
    close_btn.pack(side='right', padx=10, pady=8)
    close_btn.bind('<Button-1>', lambda e: dlg.destroy())
    close_btn.bind('<Enter>', lambda e: close_btn.config(fg='#ff5555', bg='#3a3a3a'))
    close_btn.bind('<Leave>', lambda e: close_btn.config(fg='#cccccc', bg='#1e1e1e'))

    # Manual dragging for the custom title bar.
    # Ручное перетаскивание для собственной шапки.
    def start_drag(event):
        dlg._drag_x = event.x
        dlg._drag_y = event.y

    def do_drag(event):
        x = dlg.winfo_x() + event.x - dlg._drag_x
        y = dlg.winfo_y() + event.y - dlg._drag_y
        dlg.geometry(f"+{x}+{y}")

    title_bar.bind('<Button-1>', start_drag)
    title_bar.bind('<B1-Motion>', do_drag)
    title_label.bind('<Button-1>', start_drag)
    title_label.bind('<B1-Motion>', do_drag)

    # Resize grip for the borderless dialog.
    # Уголок изменения размера для диалога без рамки.
    resize_grip = tk.Frame(dlg, bg='#555555', width=16, height=16, cursor='bottom_right_corner')
    resize_grip.place(relx=1.0, rely=1.0, anchor='se')

    def start_resize(event):
        dlg._resize_x = event.x_root
        dlg._resize_y = event.y_root
        dlg._resize_w = dlg.winfo_width()
        dlg._resize_h = dlg.winfo_height()

    def do_resize(event):
        dw = event.x_root - dlg._resize_x
        dh = event.y_root - dlg._resize_y
        new_w = max(500, dlg._resize_w + dw)
        new_h = max(450, dlg._resize_h + dh)
        dlg.geometry(f"{new_w}x{new_h}")

    resize_grip.bind('<Button-1>', start_resize)
    resize_grip.bind('<B1-Motion>', do_resize)

    dlg.update_idletasks()
    x = (dlg.winfo_screenwidth() - 650) // 2
    y = (dlg.winfo_screenheight() - 580) // 2
    dlg.geometry(f"+{x}+{y}")

    # Escape closes the dialog quickly.
    # Escape быстро закрывает диалог.
    dlg.bind('<Escape>', lambda e: dlg.destroy())

    lbl_style = {
        'font': ("Segoe UI", 10), 'fg': '#cccccc', 'bg': '#2b2b2b', 'anchor': 'w'
    }
    entry_style = {
        'font': ("Segoe UI", 10), 'bg': '#1e1e1e', 'fg': '#cccccc',
        'insertbackground': '#4FC3F7', 'relief': 'flat', 'bd': 2,
    }

    # Pack the bottom buttons first so they remain visible even when the dialog shrinks.
    # Кнопки снизу pack'аем первыми, чтобы они гарантированно оставались видимыми при уменьшении окна.
    btn_frame = tk.Frame(dlg, bg='#2b2b2b')
    btn_frame.pack(side='bottom', fill='x', padx=15, pady=(0, 15))

    save_btn_style = {
        'font': ("Segoe UI", 11), 'bg': '#4CAF50', 'fg': '#FFFFFF',
        'activebackground': '#66BB6A', 'activeforeground': '#FFFFFF',
        'relief': 'flat', 'bd': 0, 'cursor': 'hand2',
        'padx': 20, 'pady': 6,
    }
    cancel_btn_style = {
        'font': ("Segoe UI", 11), 'bg': '#3a3a3a', 'fg': '#cccccc',
        'activebackground': '#FF5252', 'activeforeground': '#FFFFFF',
        'relief': 'flat', 'bd': 0, 'cursor': 'hand2',
        'padx': 20, 'pady': 6,
    }

    def on_save():
        name = name_var.get().strip()
        path = path_var.get().strip()
        raw_triggers = triggers_text.get('1.0', 'end').strip()

        if not name:
            messagebox.showwarning(_t("scripts.error"), _t("scripts.warn_name"), parent=dlg)
            return
        if not path:
            messagebox.showwarning(_t("scripts.error"), _t("scripts.warn_path"), parent=dlg)
            return

        triggers = [t.strip() for t in raw_triggers.split('\n') if t.strip()]
        if not triggers:
            messagebox.showwarning(_t("scripts.error"), _t("scripts.warn_triggers"), parent=dlg)
            return

        sid = script_id if script_id else generate_script_id(name)
        enabled = script_data.get("enabled", True) if script_data else True

        try:
            add_script(sid, name, path, triggers, enabled)
        except ValueError as e:
            messagebox.showerror(_t("scripts.error"), str(e), parent=dlg)
            return

        if on_save_callback:
            on_save_callback()
        if on_scripts_changed:
            on_scripts_changed()

        dlg.destroy()

    def on_cancel():
        dlg.destroy()

    tk.Button(btn_frame, text=_t("common.save"), command=on_save, **save_btn_style).pack(side='left', padx=(0, 10))
    tk.Button(btn_frame, text=_t("common.cancel"), command=on_cancel, **cancel_btn_style).pack(side='left')

    # === Разделитель перед кнопками ===
    sep = tk.Frame(dlg, bg='#444444', height=1)
    sep.pack(side='bottom', fill='x', padx=15, pady=(10, 0))

    # === ПОЛЯ — pack сверху вниз ===

    # --- Название ---
    tk.Label(dlg, text=_t("scripts.name"), **lbl_style).pack(side='top', anchor='w', padx=15, pady=(15, 2))
    name_var = tk.StringVar(value=script_data.get("name", "") if script_data else "")
    name_entry = tk.Entry(dlg, textvariable=name_var, **entry_style)
    name_entry.pack(side='top', fill='x', padx=15)

    # --- Путь к файлу ---
    tk.Label(dlg, text=_t("scripts.path"), **lbl_style).pack(side='top', anchor='w', padx=15, pady=(10, 2))
    path_frame = tk.Frame(dlg, bg='#2b2b2b')
    path_frame.pack(side='top', fill='x', padx=15)

    path_var = tk.StringVar(value=script_data.get("path", "") if script_data else "")
    path_entry = tk.Entry(path_frame, textvariable=path_var, **entry_style)
    path_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

    def browse_file():
        initial_dir = str(get_scripts_dir())
        filepath = filedialog.askopenfilename(
            parent=dlg,
            title=_t("scripts.select_script"),
            initialdir=initial_dir,
            filetypes=[
                (_t("settings.all_scripts"), "*.py *.bat *.cmd *.ps1 *.exe *.sh"),
                ("Python", "*.py"),
                ("Batch", "*.bat *.cmd"),
                ("PowerShell", "*.ps1"),
                ("Executable", "*.exe"),
                ("Shell", "*.sh"),
                (_t("settings.all_files"), "*.*"),
            ],
        )
        if filepath:
            path_var.set(filepath)

    tk.Button(
        path_frame, text="📂", command=browse_file,
        font=("Segoe UI", 10), bg='#3a3a3a', fg='#cccccc',
        activebackground='#4FC3F7', relief='flat', bd=0, cursor='hand2',
        width=3,
    ).pack(side='right')

    # --- Голосовые команды ---
    tk.Label(
        dlg, text=_t("scripts.voice_commands"),
        **lbl_style
    ).pack(side='top', anchor='w', padx=15, pady=(10, 2))

    tk.Label(
        dlg, text=_t("scripts.voice_hint"),
        font=("Segoe UI", 8), fg='#888888', bg='#2b2b2b', anchor='w'
    ).pack(side='top', anchor='w', padx=15)

    triggers_text = tk.Text(
        dlg, font=("Segoe UI", 10), bg='#1e1e1e', fg='#cccccc',
        insertbackground='#4FC3F7', relief='flat', bd=2,
        height=8, wrap='word',
    )
    triggers_text.pack(side='top', fill='both', expand=True, padx=15, pady=(2, 0))

    if script_data:
        triggers = script_data.get("triggers", [])
        triggers_text.insert('1.0', '\n'.join(triggers))

    name_entry.focus_set()
    dlg.grab_set()
