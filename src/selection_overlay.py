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
Visual overlay for UI selection plus keyboard/tree navigation.
Визуальная рамка выделения UI-элемента и навигация по дереву/клавиатуре.

Two modes:
Два режима:
  keyboard — Shift+Up/Down для расширения/сужения выделения (Блокнот, VS Code, терминал)
  ui_tree  — навигация по UI-дереву (браузер, UI Automation)

The mode is detected automatically:
Режим определяется автоматически:
  - EditControl / DocumentControl → keyboard
  - Нет элемента (Ctrl+C сработал) → keyboard
  - GroupControl / CustomControl → ui_tree
"""

import ctypes
import ctypes.wintypes as wintypes
import threading
import time


# === Selection state ===
# === Состояние выделения ===
_current_element = None       # Current UI element under the overlay. / Текущий UI-элемент под рамкой.
_child_before_up = []         # Stack of children before moving up. / Стек элементов до подъёма.
_overlay_hwnd = None          # Overlay window handle. / HWND окна-рамки.
_overlay_lock = threading.Lock()
_auto_hide_timer = None       # Overlay auto-hide timer. / Таймер автоскрытия рамки.
_AUTO_HIDE_SEC = 5.0

# Timer that clears the remembered element after inactivity.
# Таймер, который очищает запомненный элемент после бездействия.
_element_reset_timer = None
_ELEMENT_RESET_SEC = 30.0

# Current selection mode.
# Текущий режим выделения.
_selection_mode = None        # None / "keyboard" / "ui_tree"
_kb_lines_up = 0              # Number of extra keyboard lines. / Сколько строк расширено в keyboard-режиме.


def get_current_element():
    """Returns the currently selected UI element or None.
    Возвращает текущий выделенный UI-элемент или None."""
    return _current_element


def set_current_element(element):
    """
    Sets the current element, shows the overlay, and copies its text to the clipboard.
    Called from smart_copy -> _copy_via_ui_automation.

    Устанавливает текущий элемент, показывает рамку и копирует его текст в буфер.
    Вызывается из smart_copy -> _copy_via_ui_automation.
    """
    global _current_element, _selection_mode, _kb_lines_up
    _current_element = element
    _child_before_up.clear()
    _selection_mode = None
    _kb_lines_up = 0

    if element is None:
        hide_overlay()
        return

    # Edit-like controls are handled by keyboard expansion instead of UI-tree traversal.
    # Для edit-подобных контролов используем keyboard-режим вместо обхода UI-дерева.
    try:
        ct = element.ControlTypeName
        if ct in ('EditControl', 'DocumentControl'):
            _selection_mode = "keyboard"
            print(f"[SELECT] 📝 Режим: keyboard ({ct})")
            _reset_element_timer()
            # Skip the overlay and extra UI copy because the editor already shows the selection.
            # Не рисуем рамку и не копируем через UI, потому что редактор уже показывает выделение.
            return
    except Exception:
        pass

    _selection_mode = "ui_tree"
    print("[SELECT] 🌐 Режим: ui_tree")

    rect = _get_element_rect(element)
    if rect:
        show_overlay(*rect)
        _reset_auto_hide()
        _reset_element_timer()
        _copy_element_to_clipboard(element)


# === Expand selection ===
# === Больше ===

def selection_more():
    """
    Expands the current selection.
    Расширяет текущее выделение.

    keyboard: Shift+Up → Ctrl+C
    ui_tree: подъём к родителю
    """
    global _selection_mode, _kb_lines_up, _current_element

    # If the mode is already known, stay on that path.
    # Если режим уже определён, продолжаем по нему.
    if _selection_mode == "keyboard":
        return _keyboard_more()

    if _selection_mode == "ui_tree" and _current_element is not None:
        return _ui_tree_more()

    # Otherwise infer the mode from the current element.
    # Иначе определяем режим по текущему элементу.
    if _current_element is not None:
        try:
            ct = _current_element.ControlTypeName
            if ct not in ('EditControl', 'DocumentControl'):
                _selection_mode = "ui_tree"
                return _ui_tree_more()
        except Exception:
            pass

    # Edit controls or missing elements fall back to keyboard selection logic.
    # EditControl, DocumentControl или отсутствие элемента ведут в keyboard-режим.
    _selection_mode = "keyboard"
    _kb_lines_up = 0
    return _keyboard_more()


def _keyboard_more():
    """Expands keyboard selection downward by one full line.
    Расширяет выделение клавиатурой вниз на одну полную строку."""
    global _kb_lines_up
    from input_sender import send_hotkey
    from ui_copy_handler import get_clipboard_text

    if _kb_lines_up == 0:
        # The first call selects the current line before extending further.
        # При первом вызове выделяем текущую строку, а уже потом расширяем дальше.
        send_hotkey("home")
        time.sleep(0.03)
        send_hotkey("shift+end")
        time.sleep(0.03)
    
    # Extend the selection to include the next full line.
    # Расширяем выделение так, чтобы захватить следующую строку целиком.
    send_hotkey("shift+down")
    time.sleep(0.03)
    send_hotkey("shift+end")
    time.sleep(0.03)

    _kb_lines_up += 1

    send_hotkey("ctrl+c")
    time.sleep(0.1)

    _reset_element_timer()

    text = get_clipboard_text()
    chars = len(text) if text else 0
    lines = text.count('\n') + 1 if text else 0
    print(f"[SELECT] ⬇️ Больше (keyboard): +{_kb_lines_up} строк вниз, ~{lines} строк, {chars} символов")
    return True


def _ui_tree_more():
    """Expands selection by moving to the parent in the UI tree.
    Расширяет выделение, поднимаясь к родителю в UI-дереве."""
    global _current_element

    if _current_element is None:
        print("[SELECT] ⚠️ Нет активного выделения — сначала скажите «копировать»")
        return False

    try:
        parent = _current_element.GetParentControl()
        if parent is None:
            print("[SELECT] ⚠️ Достигнут корень дерева")
            return False

        parent_area = _get_element_area(parent)
        current_area = _get_element_area(_current_element)

        # Never escalate to the desktop root element.
        # Не поднимаемся до корневого элемента Desktop.
        try:
            if parent.GetParentControl() is None:
                print("[SELECT] ⚠️ Достигнут корень дерева")
                return False
        except Exception:
            pass

        # Skip visually identical parents and jump to the grandparent instead.
        # Если родитель визуально того же размера, пропускаем его и пробуем дедушку.
        if parent_area > 0 and current_area > 0:
            ratio = abs(parent_area - current_area) / max(parent_area, current_area)
            if ratio < 0.05:
                grandparent = parent.GetParentControl()
                if grandparent and grandparent.GetParentControl() is not None:
                    _child_before_up.append(_current_element)
                    _current_element = grandparent
                    area = _get_element_area(grandparent)
                    print(f"[SELECT] ⬆️ Пропуск одинакового → дедушка ({area} px²)")
                    rect = _get_element_rect(grandparent)
                    if rect:
                        show_overlay(*rect)
                        _reset_auto_hide()
                        _reset_element_timer()
                        _copy_element_to_clipboard(grandparent)
                    return True

        _child_before_up.append(_current_element)
        _current_element = parent

        rect = _get_element_rect(parent)
        if rect:
            show_overlay(*rect)
            _reset_auto_hide()
            _reset_element_timer()
            _copy_element_to_clipboard(parent)

        print(f"[SELECT] ⬆️ Больше (ui_tree) → ({parent_area} px²)")
        return True

    except Exception as e:
        print(f"[SELECT] ❌ Ошибка: {e}")
        return False


# === Shrink selection ===
# === Меньше ===

def selection_less():
    """
    Shrinks the current selection.
    Сужает текущее выделение.

    keyboard: Shift+Down → Ctrl+C
    ui_tree: спуск к ребёнку
    """
    if _selection_mode == "keyboard":
        return _keyboard_less()

    if _selection_mode == "ui_tree":
        return _ui_tree_less()

    print("[SELECT] ⚠️ Нет активного выделения — сначала скажите «копировать»")
    return False


def _keyboard_less():
    """Shrinks keyboard selection by removing the last line from the bottom.
    Сужает keyboard-выделение, убирая последнюю строку снизу."""
    global _kb_lines_up
    from input_sender import send_hotkey
    from ui_copy_handler import get_clipboard_text

    if _kb_lines_up <= 0:
        print("[SELECT] ⚠️ Минимальное выделение")
        return False

    _kb_lines_up -= 1

    # Shift+Up removes the bottom line from the current selection.
    # Shift+Up убирает нижнюю строку из текущего выделения.
    send_hotkey("shift+up")
    time.sleep(0.03)

    send_hotkey("ctrl+c")
    time.sleep(0.1)

    _reset_element_timer()

    text = get_clipboard_text()
    chars = len(text) if text else 0
    lines = text.count('\n') + 1 if text else 0
    print(f"[SELECT] ⬆️ Меньше (keyboard): -{1} строка, осталось ~{lines} строк, {chars} символов")
    return True


def _ui_tree_less():
    """Shrinks selection by descending to a child in the UI tree.
    Сужает выделение, спускаясь к дочернему элементу в UI-дереве."""
    global _current_element

    if _current_element is None:
        print("[SELECT] ⚠️ Нет активного выделения")
        return False

    # First undo the previous "more" step if we have history.
    # Приоритет 1: вернуться к предыдущему элементу, отменяя «больше».
    if _child_before_up:
        prev = _child_before_up.pop()
        _current_element = prev

        rect = _get_element_rect(prev)
        if rect:
            show_overlay(*rect)
            _reset_auto_hide()
            _reset_element_timer()
            _copy_element_to_clipboard(prev)

        area = _get_element_area(prev)
        print(f"[SELECT] ⬇️ Меньше (возврат) → ({area} px²)")
        return True

    # Otherwise choose the child closest to the cursor position.
    # Приоритет 2: ищем дочерний элемент, ближайший к курсору.
    try:
        children = _current_element.GetChildren()
        if not children:
            print("[SELECT] ⚠️ Нет дочерних элементов")
            return False

        cx, cy = _get_cursor_pos()
        best_child = None
        best_dist = float('inf')

        for child in children:
            child_area = _get_element_area(child)
            if child_area < 500:
                continue

            r = _get_element_rect(child)
            if not r:
                continue

            if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                best_child = child
                best_dist = 0
                continue

            center_x = (r[0] + r[2]) / 2
            center_y = (r[1] + r[3]) / 2
            dist = ((center_x - cx) ** 2 + (center_y - cy) ** 2) ** 0.5
            if dist < best_dist:
                best_child = child
                best_dist = dist

        if best_child is None:
            print("[SELECT] ⚠️ Нет подходящих дочерних элементов")
            return False

        _child_before_up.clear()
        _current_element = best_child

        rect = _get_element_rect(best_child)
        if rect:
            show_overlay(*rect)
            _reset_auto_hide()
            _reset_element_timer()
            _copy_element_to_clipboard(best_child)

        area = _get_element_area(best_child)
        print(f"[SELECT] ⬇️ Меньше → ({area} px²)")
        return True

    except Exception as e:
        print(f"[SELECT] ❌ Ошибка: {e}")
        return False


# === Timers ===
# === Таймеры ===

def _reset_auto_hide():
    """Resets the auto-hide timer for the overlay only, not for the selected element.
    Сбрасывает таймер автоскрытия только для рамки, а не для выбранного элемента."""
    global _auto_hide_timer
    if _auto_hide_timer:
        _auto_hide_timer.cancel()
    _auto_hide_timer = threading.Timer(_AUTO_HIDE_SEC, _on_auto_hide_overlay)
    _auto_hide_timer.daemon = True
    _auto_hide_timer.start()


def _on_auto_hide_overlay():
    """Auto-hides only the overlay while keeping the current element selected.
    Автоматически скрывает только рамку, сохраняя выбранный элемент."""
    print("[SELECT] ⏱️ Автоскрытие рамки (элемент сохранён)")
    hide_overlay()


def _reset_element_timer():
    """Resets the inactivity timer that clears the current element.
    Сбрасывает таймер бездействия, который очищает текущий элемент."""
    global _element_reset_timer
    if _element_reset_timer:
        _element_reset_timer.cancel()
    _element_reset_timer = threading.Timer(_ELEMENT_RESET_SEC, _on_element_reset)
    _element_reset_timer.daemon = True
    _element_reset_timer.start()


def _on_element_reset():
    """Clears the current element and mode after 30 seconds of inactivity.
    Сбрасывает текущий элемент и режим после 30 секунд бездействия."""
    global _current_element, _selection_mode, _kb_lines_up
    print("[SELECT] ⏱️ Состояние сброшено (30 сек без активности)")
    _current_element = None
    _selection_mode = None
    _kb_lines_up = 0
    _child_before_up.clear()
    hide_overlay()


# === Overlay window ===
# === Окно рамки ===

def show_overlay(left, top, right, bottom):
    """Shows a frame around the target rectangle.
    Показывает рамку вокруг целевой области."""
    threading.Thread(
        target=_draw_overlay,
        args=(left, top, right, bottom),
        daemon=True,
    ).start()


def hide_overlay():
    """Hides the overlay frame.
    Скрывает рамку."""
    global _overlay_hwnd
    with _overlay_lock:
        hwnd = _overlay_hwnd
        _overlay_hwnd = None
    if hwnd:
        try:
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
        except Exception:
            pass


def _draw_overlay(left, top, right, bottom):
    """Draws the overlay frame through a layered Win32 window.
    Рисует рамку через layered-окно Win32."""
    global _overlay_hwnd

    hide_overlay()
    time.sleep(0.03)

    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        kernel32 = ctypes.windll.kernel32

        LRESULT = ctypes.c_longlong
        WPARAM = ctypes.c_ulonglong
        LPARAM = ctypes.c_longlong
        HWND = ctypes.c_void_p
        UINT = ctypes.c_uint

        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        ]
        user32.CreateWindowExW.restype = HWND
        user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.RegisterClassExW.restype = wintypes.ATOM
        user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
        user32.SetLayeredWindowAttributes.argtypes = [HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
        user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.UpdateWindow.argtypes = [HWND]
        user32.UpdateWindow.restype = wintypes.BOOL
        user32.DestroyWindow.argtypes = [HWND]
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), HWND, UINT, UINT]
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = LRESULT
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostQuitMessage.restype = None
        user32.BeginPaint.argtypes = [HWND, ctypes.c_void_p]
        user32.BeginPaint.restype = ctypes.c_void_p
        user32.EndPaint.argtypes = [HWND, ctypes.c_void_p]
        user32.EndPaint.restype = wintypes.BOOL
        user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        user32.FillRect.restype = ctypes.c_int
        user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL

        gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
        gdi32.CreateSolidBrush.restype = ctypes.c_void_p
        gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        gdi32.DeleteObject.restype = wintypes.BOOL
        gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.DWORD]
        gdi32.CreatePen.restype = ctypes.c_void_p
        gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.SelectObject.restype = ctypes.c_void_p
        gdi32.MoveToEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        gdi32.MoveToEx.restype = wintypes.BOOL
        gdi32.LineTo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        gdi32.LineTo.restype = wintypes.BOOL

        BORDER = 3
        win_left = left - BORDER - 1
        win_top = top - BORDER - 1
        win_w = (right - left) + (BORDER + 1) * 2
        win_h = (bottom - top) + (BORDER + 1) * 2

        def wnd_proc(hwnd, msg, wp, lp):
            try:
                if msg == 0x000F:  # WM_PAINT
                    class PAINTSTRUCT(ctypes.Structure):
                        _fields_ = [
                            ('hdc', ctypes.c_void_p),
                            ('fErase', ctypes.c_int),
                            ('rcPaint', wintypes.RECT),
                            ('fRestore', ctypes.c_int),
                            ('fIncUpdate', ctypes.c_int),
                            ('rgb', ctypes.c_byte * 32),
                        ]
                    ps = PAINTSTRUCT()
                    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))

                    bg_brush = gdi32.CreateSolidBrush(0x00FF00FF)
                    rc = wintypes.RECT(0, 0, win_w, win_h)
                    user32.FillRect(hdc, ctypes.byref(rc), bg_brush)
                    gdi32.DeleteObject(bg_brush)

                    pen = gdi32.CreatePen(0, BORDER, 0x0000A5FF)
                    old_pen = gdi32.SelectObject(hdc, pen)

                    b = BORDER // 2 + 1
                    x1, y1 = b, b
                    x2, y2 = win_w - b, win_h - b

                    gdi32.MoveToEx(hdc, x1, y1, None)
                    gdi32.LineTo(hdc, x2, y1)
                    gdi32.LineTo(hdc, x2, y2)
                    gdi32.LineTo(hdc, x1, y2)
                    gdi32.LineTo(hdc, x1, y1)

                    gdi32.SelectObject(hdc, old_pen)
                    gdi32.DeleteObject(pen)

                    user32.EndPaint(hwnd, ctypes.byref(ps))
                    return 0

                elif msg == 0x0010:  # WM_CLOSE
                    user32.DestroyWindow(hwnd)
                    return 0

                elif msg == 0x0002:  # WM_DESTROY
                    user32.PostQuitMessage(0)
                    return 0

            except Exception:
                pass
            return user32.DefWindowProcW(hwnd, msg, wp, lp)

        proc = WNDPROC(wnd_proc)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
                ("hIconSm", ctypes.c_void_p),
            ]

        class_name = f"SelectOverlay{id(proc)}"
        hinst = kernel32.GetModuleHandleW(None)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0x0003
        wc.lpfnWndProc = proc
        wc.hInstance = hinst
        wc.lpszClassName = class_name

        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            return

        ex_style = 0x00000008 | 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000
        style = 0x80000000

        hwnd = user32.CreateWindowExW(
            ex_style, class_name, None, style,
            win_left, win_top, win_w, win_h,
            None, None, hinst, None
        )

        if not hwnd:
            user32.UnregisterClassW(class_name, hinst)
            return

        with _overlay_lock:
            _overlay_hwnd = hwnd

        user32.SetLayeredWindowAttributes(hwnd, 0x00FF00FF, 0, 0x00000001)
        user32.ShowWindow(hwnd, 8)
        user32.UpdateWindow(hwnd)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnregisterClassW(class_name, hinst)

        with _overlay_lock:
            if _overlay_hwnd == hwnd:
                _overlay_hwnd = None

    except Exception as e:
        print(f"[SELECT] ❌ Overlay ошибка: {e}")


# === Utilities ===
# === Утилиты ===

def _get_element_rect(element):
    """Returns (left, top, right, bottom) or None.
    Возвращает (left, top, right, bottom) или None."""
    try:
        rect = element.BoundingRectangle
        if rect:
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    return None


def _get_element_area(element):
    """Returns the element area in pixels.
    Возвращает площадь элемента в пикселях."""
    try:
        rect = element.BoundingRectangle
        if rect:
            return (rect.right - rect.left) * (rect.bottom - rect.top)
    except Exception:
        pass
    return 0


def _get_cursor_pos():
    """Returns the current mouse cursor position.
    Возвращает текущую позицию курсора мыши."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _copy_element_to_clipboard(element):
    """Collects text from the element and writes it to the clipboard with a 3-second timeout.
    Собирает текст из элемента и кладёт его в буфер обмена с таймаутом 3 секунды."""
    from ui_copy_handler import _collect_lines, set_clipboard_text
    import threading as _thr

    result = [None]

    def _do_collect():
        try:
            lines = []
            _collect_lines(element, lines)

            if lines:
                text = '\n'.join(lines)
                set_clipboard_text(text)
                if len(lines) <= 4:
                    preview = ' | '.join(l[:60] for l in lines)
                else:
                    top_lines = ' | '.join(l[:60] for l in lines[:2])
                    bot_lines = ' | '.join(l[:60] for l in lines[-2:])
                    preview = f"{top_lines} ... {bot_lines}"
                print(f"[SELECT] 📋 {len(lines)} строк, {len(text)} символов")
                print(f"[SELECT] 📄 {preview[:200]}")
                result[0] = text
                return

            name = element.Name
            if name and name.strip():
                set_clipboard_text(name)
                print(f"[SELECT] 📋 Name: {len(name)} символов")
                result[0] = name
                return

            print("[SELECT] ⚠️ Элемент без текста")
        except Exception as e:
            print(f"[SELECT] ❌ Ошибка сбора текста: {e}")

    t = _thr.Thread(target=_do_collect, daemon=True)
    t.start()
    t.join(timeout=3.0)

    if t.is_alive():
        print("[SELECT] ⚠️ Сбор текста таймаут 3с — пропускаем")
        return None

    return result[0]
