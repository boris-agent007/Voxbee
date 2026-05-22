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
Voice-driven mouse cursor control.
Управление курсором мыши голосом.

Supports movement, monitor jumps, clicks, and grid navigation.
Поддерживает сдвиг, переход на монитор, клики и grid-навигацию.
"""

import ctypes
import ctypes.wintypes
import time
import threading
from collections import deque


# === Cursor beacon throttling ===
# === Защита маячка курсора от спама ===
_beacon_lock = threading.Lock()
_beacon_last_time = 0
_beacon_cooldown = 0.15  # Minimum 150 ms between beacons. / Минимум 150 мс между маячками.
_beacon_pending = None   # Last queued request: (x, y, radius, flashes). / Последний отложенный запрос: (x, y, radius, flashes).


def _flash_cursor_beacon(x, y, radius=60, flashes=3):
    """
    Draws a beacon around the cursor through a layered Win32 window.
    Показывает маячок вокруг курсора через layered-окно Win32.

    Защита от спама: при быстрых вызовах показывает только последний.
    При частых вызовах защита от спама оставляет только последний запрос.
    """
    global _beacon_last_time, _beacon_pending

    now = time.time()

    with _beacon_lock:
        if now - _beacon_last_time < _beacon_cooldown:
            _beacon_pending = (x, y, radius, flashes)
            return
        _beacon_last_time = now
        _beacon_pending = None

    def _run():
        try:
            from ctypes import wintypes, POINTER, WINFUNCTYPE, sizeof, byref, cast
            from ctypes import c_void_p, c_uint, c_int, c_wchar_p, c_long

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            kernel32 = ctypes.windll.kernel32

            # Define WinAPI types explicitly so ctypes uses the correct calling convention.
            # Явно задаём типы WinAPI, чтобы ctypes использовал правильные сигнатуры.
            LRESULT = ctypes.c_longlong
            WPARAM = ctypes.c_ulonglong
            LPARAM = ctypes.c_longlong
            HWND = c_void_p
            UINT = c_uint
            
            # Window procedure callback for the temporary beacon window.
            # Callback оконной процедуры для временного окна маячка.
            WNDPROC = WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

            # Configure argtypes/restype for every WinAPI call used below.
            # Настраиваем argtypes/restype для всех WinAPI-вызовов ниже.
            user32.CreateWindowExW.argtypes = [
                wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                c_int, c_int, c_int, c_int,
                HWND, c_void_p, c_void_p, c_void_p
            ]
            user32.CreateWindowExW.restype = HWND

            user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
            user32.DefWindowProcW.restype = LRESULT

            user32.ShowWindow.argtypes = [HWND, c_int]
            user32.ShowWindow.restype = wintypes.BOOL

            user32.UpdateWindow.argtypes = [HWND]
            user32.UpdateWindow.restype = wintypes.BOOL

            user32.DestroyWindow.argtypes = [HWND]
            user32.DestroyWindow.restype = wintypes.BOOL

            user32.SetTimer.argtypes = [HWND, ctypes.c_ulonglong, UINT, c_void_p]
            user32.SetTimer.restype = ctypes.c_ulonglong

            user32.KillTimer.argtypes = [HWND, ctypes.c_ulonglong]
            user32.KillTimer.restype = wintypes.BOOL

            user32.GetMessageW.argtypes = [POINTER(wintypes.MSG), HWND, UINT, UINT]
            user32.GetMessageW.restype = wintypes.BOOL

            user32.TranslateMessage.argtypes = [POINTER(wintypes.MSG)]
            user32.TranslateMessage.restype = wintypes.BOOL

            user32.DispatchMessageW.argtypes = [POINTER(wintypes.MSG)]
            user32.DispatchMessageW.restype = LRESULT

            user32.PostQuitMessage.argtypes = [c_int]
            user32.PostQuitMessage.restype = None

            user32.BeginPaint.argtypes = [HWND, c_void_p]
            user32.BeginPaint.restype = c_void_p

            user32.EndPaint.argtypes = [HWND, c_void_p]
            user32.EndPaint.restype = wintypes.BOOL

            user32.FillRect.argtypes = [c_void_p, c_void_p, c_void_p]
            user32.FillRect.restype = c_int

            user32.SetLayeredWindowAttributes.argtypes = [HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
            user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

            user32.RegisterClassExW.restype = wintypes.ATOM
            user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, c_void_p]

            gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
            gdi32.CreateSolidBrush.restype = c_void_p

            gdi32.DeleteObject.argtypes = [c_void_p]
            gdi32.DeleteObject.restype = wintypes.BOOL

            gdi32.CreatePen.argtypes = [c_int, c_int, wintypes.DWORD]
            gdi32.CreatePen.restype = c_void_p

            gdi32.SelectObject.argtypes = [c_void_p, c_void_p]
            gdi32.SelectObject.restype = c_void_p

            gdi32.GetStockObject.argtypes = [c_int]
            gdi32.GetStockObject.restype = c_void_p

            gdi32.Ellipse.argtypes = [c_void_p, c_int, c_int, c_int, c_int]
            gdi32.Ellipse.restype = wintypes.BOOL

            sz = radius * 2 + 4
            center = sz // 2
            blink_count = [0]
            max_blinks = flashes * 2

            def wnd_proc(hwnd, msg, wp, lp):
                try:
                    if msg == 0x000F:  # WM_PAINT
                        class PAINTSTRUCT(ctypes.Structure):
                            _fields_ = [
                                ('hdc', c_void_p),
                                ('fErase', c_int),
                                ('rcPaint', wintypes.RECT),
                                ('fRestore', c_int),
                                ('fIncUpdate', c_int),
                                ('rgb', ctypes.c_byte * 32),
                            ]
                        ps = PAINTSTRUCT()
                        hdc = user32.BeginPaint(hwnd, byref(ps))

                        brush = gdi32.CreateSolidBrush(0x00FF00FF)
                        rc = wintypes.RECT(0, 0, sz, sz)
                        user32.FillRect(hdc, byref(rc), brush)
                        gdi32.DeleteObject(brush)

                        colors = [0x004444FF, 0x000088FF, 0x0000CCFF]
                        for i, clr in enumerate(colors):
                            rr = radius - i * 12
                            if rr < 10:
                                break
                            pen = gdi32.CreatePen(0, 3, clr)
                            old_pen = gdi32.SelectObject(hdc, pen)
                            old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(5))
                            gdi32.Ellipse(hdc, center - rr, center - rr, center + rr, center + rr)
                            gdi32.SelectObject(hdc, old_pen)
                            gdi32.SelectObject(hdc, old_brush)
                            gdi32.DeleteObject(pen)

                        user32.EndPaint(hwnd, byref(ps))
                        return 0

                    elif msg == 0x0113:  # WM_TIMER
                        blink_count[0] += 1
                        if blink_count[0] >= max_blinks:
                            user32.KillTimer(hwnd, 1)
                            user32.DestroyWindow(hwnd)
                        else:
                            show = 0 if blink_count[0] % 2 == 0 else 8
                            user32.ShowWindow(hwnd, show)
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
                    ("cbSize", c_uint),
                    ("style", c_uint),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", c_int),
                    ("cbWndExtra", c_int),
                    ("hInstance", c_void_p),
                    ("hIcon", c_void_p),
                    ("hCursor", c_void_p),
                    ("hbrBackground", c_void_p),
                    ("lpszMenuName", c_wchar_p),
                    ("lpszClassName", c_wchar_p),
                    ("hIconSm", c_void_p),
                ]

            class_name = f"BeaconWnd{id(proc)}"
            hinst = kernel32.GetModuleHandleW(None)

            wc = WNDCLASSEXW()
            wc.cbSize = sizeof(WNDCLASSEXW)
            wc.style = 0x0003
            wc.lpfnWndProc = proc
            wc.hInstance = hinst
            wc.lpszClassName = class_name

            atom = user32.RegisterClassExW(byref(wc))
            if not atom:
                return

            ex_style = 0x00000008 | 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000
            style = 0x80000000

            hwnd = user32.CreateWindowExW(
                ex_style, class_name, None, style,
                x - sz // 2, y - sz // 2, sz, sz,
                None, None, hinst, None
            )

            if not hwnd:
                user32.UnregisterClassW(class_name, hinst)
                return

            user32.SetLayeredWindowAttributes(hwnd, 0x00FF00FF, 0, 0x00000001)
            user32.ShowWindow(hwnd, 8)
            user32.UpdateWindow(hwnd)
            user32.SetTimer(hwnd, 1, 100, None)

            msg = wintypes.MSG()
            while user32.GetMessageW(byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(byref(msg))
                user32.DispatchMessageW(byref(msg))

            user32.UnregisterClassW(class_name, hinst)

            # When the current beacon finishes, replay the latest queued request if any.
            # После завершения текущего маячка запускаем последний отложенный запрос, если он есть.
            global _beacon_pending
            with _beacon_lock:
                pending = _beacon_pending
                _beacon_pending = None

            if pending:
                px, py, pr, pf = pending
                # Replay the postponed beacon once the cooldown window is clear.
                # Показываем отложенный маячок, когда окно защиты от спама освободилось.
                _flash_cursor_beacon(px, py, pr, pf)

        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()



STEP = 150  # Default movement step; changed from the tray. / Шаг движения по умолчанию; меняется из трея.



# === Grid overlay ===
# === Отладочная сетка ===

_grid_overlay_running = False


def show_grid_overlay():
    """Shows the overlay grid across all monitors.
    Показывает overlay-сетку поверх всех мониторов."""
    global _grid_overlay_running
    
    if _grid_overlay_running:
        return
    
    _grid_overlay_running = True
    threading.Thread(target=_create_grid_overlay, daemon=True).start()
    print("[GRID] 📊 Сетка показана")


def hide_grid_overlay():
    """Hides the overlay grid.
    Скрывает overlay-сетку."""
    global _grid_overlay_running
    _grid_overlay_running = False


def is_grid_overlay_visible():
    """Checks whether the overlay grid is visible.
    Проверяет, видна ли overlay-сетка."""
    return _grid_overlay_running


def _create_grid_overlay():
    """Creates the grid overlay window through the shared TrayIcon Tk thread.
    Создаёт окно grid-overlay через общий Tk-поток TrayIcon."""
    global _grid_overlay_running
    
    try:
        # Reuse the single Tk thread to avoid cross-thread Tk access.
        # Используем единый Tk-поток, чтобы не трогать Tk из разных потоков.
        from tray_icon import _get_tray_instance
        tray = _get_tray_instance()
        if tray:
            tray._run_in_tk(_create_grid_overlay_in_tk)
        else:
            print("[GRID] ⚠️ Tray не инициализирован — сетка недоступна")
            _grid_overlay_running = False
    except Exception as e:
        print(f"[GRID] Ошибка: {e}")
        _grid_overlay_running = False


def _create_grid_overlay_in_tk():
    """Builds the overlay as a Toplevel inside the shared Tk thread.
    Создаёт overlay как Toplevel внутри общего Tk-потока."""
    global _grid_overlay_running
    
    try:
        import tkinter as tk
        from tray_icon import _get_tray_instance
        
        tray = _get_tray_instance()
        if not tray or not tray._tk_root:
            _grid_overlay_running = False
            return
        
        controller = MouseController()
        monitors = controller._get_monitors()
        
        if not monitors:
            _grid_overlay_running = False
            return
        
        min_x = min(m[0] for m in monitors)
        min_y = min(m[1] for m in monitors)
        max_x = max(m[2] for m in monitors)
        max_y = max(m[3] for m in monitors)
        
        total_w = max_x - min_x
        total_h = max_y - min_y
        
        root = tk.Toplevel(tray._tk_root)
        try:
            from config import load_config
            from ui_strings import tr
            lang = load_config().get("language", "ru")
            root.title(tr("grid.title", lang))
        except Exception:
            root.title("Grid")
        root.attributes('-alpha', 0.75)
        root.attributes('-topmost', True)
        root.overrideredirect(True)
        root.geometry(f"{total_w}x{total_h}+{min_x}+{min_y}")
        root.configure(bg='black')
        root.attributes('-transparentcolor', 'black')
        
        canvas = tk.Canvas(root, width=total_w, height=total_h, bg='black', highlightthickness=0)
        canvas.pack()
        
        cell_num = 1
        
        for mon_idx, (left, top, right, bottom) in enumerate(monitors):
            mon_w = right - left
            mon_h = bottom - top
            offset_x = left - min_x
            offset_y = top - min_y
            
            cell_w = mon_w / GRID_COLS
            cell_h = mon_h / GRID_ROWS
            
            canvas.create_rectangle(
                offset_x + 2, offset_y + 2,
                offset_x + mon_w - 2, offset_y + mon_h - 2,
                outline='#00FFFF', width=3
            )
            
            try:
                from config import load_config
                from ui_strings import tr
                lang = load_config().get("language", "ru")
                monitor_text = tr("grid.monitor", lang, num=mon_idx + 1)
            except Exception:
                monitor_text = f"Monitor {mon_idx + 1}"

            canvas.create_text(
                offset_x + 60, offset_y + 25,
                text=monitor_text,
                font=("Arial", 12, "bold"),
                fill='#00FFFF'
            )
            
            for row in range(GRID_ROWS):
                for col in range(GRID_COLS):
                    x1 = offset_x + col * cell_w
                    y1 = offset_y + row * cell_h
                    x2 = x1 + cell_w
                    y2 = y1 + cell_h
                    
                    canvas.create_rectangle(x1, y1, x2, y2, outline='#FF6600', width=2)
                    
                    cx = x1 + cell_w / 2
                    cy = y1 + cell_h / 2
                    
                    canvas.create_oval(cx - 20, cy - 20, cx + 20, cy + 20, fill='#222222', outline='#FF6600', width=2)
                    canvas.create_text(cx, cy, text=str(cell_num), font=("Arial", 14, "bold"), fill='#FFFFFF')
                    
                    cell_num += 1
        
        def on_close(event=None):
            global _grid_overlay_running
            _grid_overlay_running = False
            try:
                root.destroy()
            except Exception:
                pass
        
        root.bind('<Escape>', on_close)
        root.bind('<Button-1>', on_close)
        
        def check_close():
            if not _grid_overlay_running:
                try:
                    root.destroy()
                except Exception:
                    pass
                return
            try:
                if root.winfo_exists():
                    root.after(100, check_close)
            except Exception:
                pass
        
        root.after(100, check_close)
        
    except Exception as e:
        print(f"[GRID] Ошибка: {e}")
        _grid_overlay_running = False



# Grid dimensions per monitor.
# Размер сетки на один монитор.
GRID_COLS = 6
GRID_ROWS = 4


class MouseController:

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self._last_grid_cell = None  # Last selected grid bounds. / Границы последней выбранной ячейки.
                
        # State for continuous cursor movement.
        # Состояние непрерывного движения курсора.
        self._moving = False
        self._move_direction = None
        self._move_thread = None
        self._move_speed = 8       # Pixels per step. / Пикселей за шаг.
        self._move_interval = 0.016  # Seconds between steps (~60 FPS). / Секунд между шагами (~60 FPS).
        self._stop_position = None  # Return position for stop. / Позиция возврата при стопе.
        self._position_history = deque()  # Timed cursor history. / История позиций курсора с метками времени.

    def move(self, direction, step=None):
        """Moves the cursor by step pixels in the given direction.
        Сдвигает курсор в указанном направлении на step пикселей."""
        if step is None:
            step = STEP
        x, y = self._get_pos()
        dx, dy = 0, 0

        if direction == "right":
            dx = step
        elif direction == "left":
            dx = -step
        elif direction == "up":
            dy = -step
        elif direction == "down":
            dy = step

        self.user32.SetCursorPos(x + dx, y + dy)
        print(f"[MOUSE] ➡️ {direction} на {step}px → ({x + dx}, {y + dy})")


    def start_continuous_move(self, direction):
        """Starts continuous cursor movement in the given direction.
        Начинает непрерывное движение курсора в указанном направлении."""
        if self._moving and self._move_direction == direction:
            print(f"[MOUSE] ⚠️ Уже двигаюсь {direction}")
            return
        
        # Stop the previous movement first so only one worker thread remains active.
        # Сначала останавливаем предыдущее движение, чтобы не осталось второго рабочего потока.
        self.stop_move()
        
        self._moving = True
        self._move_direction = direction
        self._move_thread = threading.Thread(target=self._continuous_move_loop, daemon=True)
        self._move_thread.start()
        print(f"[MOUSE] 🚀 Начал движение: {direction}")

    def stop_move(self):
        """Stops continuous movement and returns to the saved pre-command position.
        Останавливает непрерывное движение и возвращает к сохранённой позиции до команды."""
        if not self._moving:
            return False
        
        self._moving = False
        if self._move_thread:
            self._move_thread.join(timeout=0.2)
            self._move_thread = None
        
        # Return to the saved position captured near the start of the spoken command.
        # Возвращаемся к позиции, сохранённой примерно в начале голосовой команды.
        if self._stop_position:
            x, y = self._stop_position
            self.user32.SetCursorPos(x, y)
            print(f"[MOUSE] ⏹️ Возврат к ({x}, {y})")
            self._stop_position = None
        else:
            x, y = self._get_pos()
            print(f"[MOUSE] ⏹️ Остановлен на ({x}, {y})")
        
        return True

    def mark_stop_position(self):
        """Captures the rollback position with human reaction-time compensation.
        Запоминает позицию возврата с учётом человеческой задержки реакции."""
        if not self._moving:
            return
        
        # Approximate human reaction delay between seeing the cursor and saying "stop".
        # Оценка задержки реакции человека между тем, как он увидел курсор и сказал «стоп».
        reaction_delay = 0.25
        target_time = time.time() - reaction_delay
        
        # Find the latest recorded position that is old enough.
        # Ищем последнюю записанную позицию, которая уже старше нужной задержки.
        best_pos = None
        for t, x, y in self._position_history:
            if t <= target_time:
                best_pos = (x, y)
            else:
                break
        
        if best_pos:
            self._stop_position = best_pos
            print(f"[MOUSE] 📍 Позиция для стопа (−{reaction_delay}с): {self._stop_position}")
        elif self._position_history:
            # If the history is shorter than reaction_delay, use the earliest known point.
            # Если история короче reaction_delay, берём самую раннюю доступную точку.
            self._stop_position = (self._position_history[0][1], self._position_history[0][2])
            print(f"[MOUSE] 📍 Позиция для стопа (ранняя): {self._stop_position}")
        else:
            self._stop_position = self._get_pos()
            print(f"[MOUSE] 📍 Позиция для стопа (текущая): {self._stop_position}")

    def is_moving(self):
        """Returns whether the cursor is currently moving continuously.
        Возвращает, движется ли курсор сейчас в непрерывном режиме."""
        return self._moving

    def _continuous_move_loop(self):
        """Background loop for continuous movement with position history.
        Фоновый цикл непрерывного движения с историей позиций."""
        direction = self._move_direction
        
        # Map logical directions to per-tick deltas.
        # Преобразуем направление в смещение на один такт.
        deltas = {
            "right": (1, 0),
            "left": (-1, 0),
            "up": (0, -1),
            "down": (0, 1),
        }
        
        dx, dy = deltas.get(direction, (0, 0))
        dx *= self._move_speed
        dy *= self._move_speed
        
        monitors = self._get_monitors()
        if monitors:
            min_x = min(m[0] for m in monitors)
            min_y = min(m[1] for m in monitors)
            max_x = max(m[2] for m in monitors)
            max_y = max(m[3] for m in monitors)
        else:
            min_x, min_y = 0, 0
            max_x, max_y = 3840, 2160
        
        # Start with a clean movement history for the new session.
        # Для новой сессии движения очищаем историю позиций.
        self._position_history.clear()
        
        while self._moving:
            x, y = self._get_pos()
            
            # Record the current cursor position with a timestamp.
            # Сохраняем текущую позицию курсора вместе с временной меткой.
            now = time.time()
            self._position_history.append((now, x, y))
            
            # Keep only the recent history needed for rollback.
            # Оставляем только недавнюю историю, нужную для возврата.
            while self._position_history and now - self._position_history[0][0] > 1.0:
                self._position_history.popleft()
            
            new_x = x + dx
            new_y = y + dy
            
            new_x = max(min_x, min(max_x - 1, new_x))
            new_y = max(min_y, min(max_y - 1, new_y))
            
            if new_x == x and new_y == y:
                print(f"[MOUSE] 🛑 Достигнут край экрана")
                self._moving = False
                break
            
            self.user32.SetCursorPos(new_x, new_y)
            time.sleep(self._move_interval)

    def set_move_speed(self, speed):
        """Sets the continuous movement speed in pixels per step.
        Устанавливает скорость непрерывного движения в пикселях за шаг."""
        self._move_speed = max(5, min(100, speed))
        print(f"[MOUSE] 🏃 Скорость: {self._move_speed}px/шаг")        

    def click(self, button="left"):
        """Clicks the requested mouse button at the current cursor position.
        Выполняет клик указанной кнопкой в текущей позиции курсора."""
        x, y = self._get_pos()

        if button == "left":
            self.user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            self.user32.mouse_event(0x0004, 0, 0, 0, 0)
            print(f"[MOUSE] 🖱️ Клик ЛКМ ({x}, {y})")
        elif button == "right":
            self.user32.mouse_event(0x0008, 0, 0, 0, 0)
            time.sleep(0.05)
            self.user32.mouse_event(0x0010, 0, 0, 0, 0)
            print(f"[MOUSE] 🖱️ Клик ПКМ ({x}, {y})")
        elif button == "double":
            self.user32.mouse_event(0x0002, 0, 0, 0, 0)
            self.user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.05)
            self.user32.mouse_event(0x0002, 0, 0, 0, 0)
            self.user32.mouse_event(0x0004, 0, 0, 0, 0)
            print(f"[MOUSE] 🖱️ Двойной клик ({x}, {y})")


    def scroll(self, direction, amount=3):
        """
        Scrolls the mouse wheel through SendInput.
        Прокручивает колесо мыши через SendInput.

        direction: "up" или "down"
        amount: количество щелчков колеса (1 щелчок ≈ 3 строки)
        """
        MOUSEEVENTF_WHEEL = 0x0800
        WHEEL_DELTA = 120
        INPUT_MOUSE = 0

        if direction == "up":
            delta = WHEEL_DELTA
        elif direction == "down":
            delta = -WHEEL_DELTA
        else:
            print(f"[MOUSE] ❌ Неизвестное направление скролла: {direction}")
            return

        x, y = self._get_pos()
        amount = max(1, min(amount, 50))

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("mi", MOUSEINPUT),
            ]

        input_size = ctypes.sizeof(INPUT)

        for _ in range(amount):
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.mi.mouseData = delta
            inp.mi.dwFlags = MOUSEEVENTF_WHEEL
            self.user32.SendInput(1, ctypes.byref(inp), input_size)
            time.sleep(0.05)

        print(f"[MOUSE] 🔄 Scroll {direction} x{amount} ({x}, {y})")  



    def scroll_to_edge(self, direction="down"):
        """
        Scrolls to the start or end of a page using a long wheel burst.
        Прокручивает страницу до конца или начала длинной серией прокруток.

        direction: "up" или "down"
        """
        MOUSEEVENTF_WHEEL = 0x0800
        WHEEL_DELTA = 120
        INPUT_MOUSE = 0

        if direction == "up":
            delta = WHEEL_DELTA
        elif direction == "down":
            delta = -WHEEL_DELTA
        else:
            print(f"[MOUSE] ❌ Неизвестное направление: {direction}")
            return

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("mi", MOUSEINPUT),
            ]

        input_size = ctypes.sizeof(INPUT)
        x, y = self._get_pos()

        # A long burst approximates "scroll to edge" without app-specific automation.
        # Длинная серия прокруток имитирует переход к краю без привязки к конкретному приложению.
        for _ in range(30):
            for _ in range(50):
                inp = INPUT()
                inp.type = INPUT_MOUSE
                inp.mi.mouseData = delta
                inp.mi.dwFlags = MOUSEEVENTF_WHEEL
                self.user32.SendInput(1, ctypes.byref(inp), input_size)
            time.sleep(0.02)

        print(f"[MOUSE] 📜 Scroll to {direction} edge ({x}, {y})")        

    def go_to_monitor(self, monitor_num):
        """Moves the cursor to the center of the selected monitor.
        Перемещает курсор в центр выбранного монитора."""
        monitors = self._get_monitors()

        if not monitors:
            print("[MOUSE] ❌ Мониторы не найдены")
            return

        idx = monitor_num - 1  # Convert 1-based UI numbering to a 0-based list index. / Преобразуем нумерацию из UI (с 1) в индекс списка (с 0).
        if idx < 0 or idx >= len(monitors):
            print(f"[MOUSE] ❌ Монитор {monitor_num} не найден (всего {len(monitors)})")
            return

        left, top, right, bottom = monitors[idx]
        cx = (left + right) // 2
        cy = (top + bottom) // 2
        self.user32.SetCursorPos(cx, cy)
        self._last_grid_cell = None
        _flash_cursor_beacon(cx, cy)
        print(f"[MOUSE] 🖥️ Монитор {monitor_num}: ({cx}, {cy})")

    def grid_go(self, cell_num):
        """
        Grid navigation moves the cursor into the requested cell.
        Grid-навигация перемещает курсор в указанную ячейку.

        Cell numbering is continuous across all monitors:
        Нумерация сквозная по всем мониторам:
        Монитор 1: ячейки 1..24 (6x4)
        Монитор 2: ячейки 25..48
        Монитор 3: ячейки 49..72

        It also works with a single monitor if the cell index stays within one grid.
        На одном мониторе это тоже работает, если индекс остаётся в пределах одной сетки.
        """
        monitors = self._get_monitors()
        if not monitors:
            print("[GRID] ❌ Мониторы не найдены")
            return False

        cells_per_monitor = GRID_COLS * GRID_ROWS  # Cells per monitor. / Количество ячеек на монитор.

        if cell_num < 1:
            print(f"[GRID] ❌ Ячейка {cell_num} < 1")
            return False

        total_cells = cells_per_monitor * len(monitors)
        if cell_num > total_cells:
            print(f"[GRID] ❌ Ячейка {cell_num} > {total_cells}")
            return False

        # Split the global cell number into monitor index and local cell coordinates.
        # Разбиваем глобальный номер ячейки на индекс монитора и локальные координаты.
        monitor_idx = (cell_num - 1) // cells_per_monitor
        local_cell = (cell_num - 1) % cells_per_monitor

        row = local_cell // GRID_COLS
        col = local_cell % GRID_COLS

        left, top, right, bottom = monitors[monitor_idx]
        mon_w = right - left
        mon_h = bottom - top

        cell_w = mon_w / GRID_COLS
        cell_h = mon_h / GRID_ROWS

        # Move to the center of the resolved cell.
        # Переходим в центр найденной ячейки.
        cx = int(left + col * cell_w + cell_w / 2)
        cy = int(top + row * cell_h + cell_h / 2)

        # Store cell bounds so grid_zoom() can refine inside the same region.
        # Запоминаем границы ячейки, чтобы grid_zoom() мог уточнить позицию внутри неё.
        cell_left = int(left + col * cell_w)
        cell_top = int(top + row * cell_h)
        cell_right = int(cell_left + cell_w)
        cell_bottom = int(cell_top + cell_h)
        self._last_grid_cell = (monitor_idx, cell_left, cell_top, cell_right, cell_bottom)

        self.user32.SetCursorPos(cx, cy)
        _flash_cursor_beacon(cx, cy)
        mon_num = monitor_idx + 1
        print(f"[GRID] 📍 Ячейка {cell_num} → монитор {mon_num}, "
              f"строка {row + 1}, столбец {col + 1} → ({cx}, {cy})")
        return True

    def grid_zoom(self, sub_cell):
        """
        Refines the last selected cell using a 3x3 sub-grid.
        Уточняет последнюю выбранную ячейку через подсетку 3x3.

        sub_cell: 1-9 (сверху вниз, слева направо):
          1 2 3
          4 5 6
          7 8 9
        """
        if not self._last_grid_cell:
            print("[GRID] ❌ Сначала выберите ячейку (сетка N)")
            return False

        if sub_cell < 1 or sub_cell > 9:
            print(f"[GRID] ❌ Подячейка {sub_cell} должна быть 1-9")
            return False

        _, cell_left, cell_top, cell_right, cell_bottom = self._last_grid_cell
        cell_w = cell_right - cell_left
        cell_h = cell_bottom - cell_top
        sub_w = cell_w / 3
        sub_h = cell_h / 3

        grid_map = {
            1: (0, 0), 2: (1, 0), 3: (2, 0),
            4: (0, 1), 5: (1, 1), 6: (2, 1),
            7: (0, 2), 8: (1, 2), 9: (2, 2),
        }

        col, row = grid_map[sub_cell]
        cx = int(cell_left + col * sub_w + sub_w / 2)
        cy = int(cell_top + row * sub_h + sub_h / 2)

        new_left = int(cell_left + col * sub_w)
        new_top = int(cell_top + row * sub_h)
        new_right = int(new_left + sub_w)
        new_bottom = int(new_top + sub_h)
        self._last_grid_cell = (self._last_grid_cell[0], new_left, new_top, new_right, new_bottom)

        self.user32.SetCursorPos(cx, cy)
        _flash_cursor_beacon(cx, cy, radius=30, flashes=2)
        print(f"[GRID] 🔍 Zoom подячейка {sub_cell} → ({cx}, {cy})")
        return True

    def get_grid_info(self):
        """Returns grid metadata for UI display.
        Возвращает метаданные сетки для отображения в UI."""
        monitors = self._get_monitors()
        total_cells = GRID_COLS * GRID_ROWS * len(monitors)
        return {
            "monitors": len(monitors),
            "cols": GRID_COLS,
            "rows": GRID_ROWS,
            "cells_per_monitor": GRID_COLS * GRID_ROWS,
            "total_cells": total_cells,
        }

    def _get_pos(self):
        point = ctypes.wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def _get_monitors(self):
        """Returns monitors as [(left, top, right, bottom), ...].
        Возвращает список мониторов в виде [(left, top, right, bottom), ...]."""
        monitors = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            monitors.append((rect.left, rect.top, rect.right, rect.bottom))
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.wintypes.LPARAM,
        )
        callback_fn = MONITORENUMPROC(callback)
        self.user32.EnumDisplayMonitors(0, 0, callback_fn, 0)

        # Keep monitor order stable from left to right.
        # Стабилизируем порядок мониторов слева направо.
        monitors.sort(key=lambda m: m[0])
        return monitors

    def set_step(self, step):
        global STEP
        STEP = step
        print(f"[MOUSE] 📏 Шаг: {step}px")

# Shared singleton used across the application.
# Глобальный singleton, используемый по всему приложению.
_controller = MouseController()


def get_mouse_controller():
    return _controller
