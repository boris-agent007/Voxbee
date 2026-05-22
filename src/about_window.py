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

import tkinter as tk
from tkinter import ttk
import webbrowser
from pathlib import Path

from ui_strings import tr


def _legal_notice(language):
    if language == "ru":
        return (
            "\n\n"
            "GNU GPL v3\n"
            "Copyright (C) 2026 Boris Shkylnikov\n"
            "Этот файл и программа Vox Bee распространяются по GNU General Public License, version 3.\n"
            "Программа поставляется БЕЗ КАКИХ-ЛИБО ГАРАНТИЙ.\n"
            "Полный текст лицензии находится в файле LICENSE в корне проекта."
        )

    return (
        "\n\n"
        "GNU GPL v3\n"
        "Copyright (C) 2026 Boris Shkylnikov\n"
        "This file and the Vox Bee program are distributed under the GNU General Public License, version 3.\n"
        "The program is provided WITHOUT ANY WARRANTY.\n"
        "The full license text is available in the LICENSE file at the project root."
    )


def _apply_window_icon(win):
    """Ставит окну фирменную иконку VoxBee в лучшем доступном качестве."""
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


def open_about_window(tk_root, language="ru"):
    _t = lambda key, **kwargs: tr(key, language, **kwargs)
    repo_url = "https://github.com/<your-account>/<your-repo>"

    win = tk.Toplevel(tk_root)
    _apply_window_icon(win)
    win.title(_t("about.title"))
    win.geometry("860x620")
    win.resizable(True, True)
    win.attributes('-topmost', True)

    frame = ttk.Frame(win, padding=16)
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text=_t("about.heading"), font=("Segoe UI", 16, "bold")).pack(anchor='w', pady=(0, 8))
    subtitle = ttk.Label(frame, text=_t("about.subtitle"), font=("Segoe UI", 10), wraplength=800)
    subtitle.pack(anchor='w', fill='x', pady=(0, 12))

    text = tk.Text(
    frame, 
    wrap='word', 
    height=22, 
    font=("Segoe UI", 10), 
    padx=15,     
    pady=15,       
    relief=tk.SOLID,
    borderwidth=1    
)
    text.pack(fill='both', expand=True)
    text.insert('1.0', _t("about.body") + _legal_notice(language))
    text.config(state='disabled')

    links = ttk.Frame(frame)
    links.pack(fill='x', pady=(12, 8))

    def _open(url):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    ttk.Button(links, text=_t("about.site"), command=lambda: _open(repo_url)).pack(side='left', padx=(0, 8))
    ttk.Button(links, text=_t("about.docs"), command=lambda: _open(f"{repo_url}#readme")).pack(side='left', padx=8)
    ttk.Button(links, text=_t("about.support"), command=lambda: _open(f"{repo_url}/issues")).pack(side='left', padx=8)

    ttk.Button(frame, text=_t("common.close"), command=win.destroy).pack(anchor='e')

    win.update_idletasks()
    subtitle.configure(wraplength=max(400, win.winfo_width() - 60))
    win.bind("<Configure>", lambda event: subtitle.configure(wraplength=max(400, event.width - 60)))
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    ww, wh = win.winfo_width(), win.winfo_height()
    win.geometry(f"+{(sw - ww)//2}+{(sh - wh)//2}")
    win.focus_force()
