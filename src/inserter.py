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

import time
import ctypes
import ctypes.wintypes
import win32gui
import win32con
import win32api
import win32process
import threading
import os


# === Last dictated text buffer ===
# === Буфер последнего надиктованного текста ===
_last_dictated_text = ""
_dictated_lock = threading.Lock()
_last_insert_target = None
_last_insert_ended_with_whitespace = True
_last_insert_time = 0.0

# === ctypes type configuration for 64-bit Windows ===
# === Настройка типов ctypes для 64-bit Windows ===
# Without these signatures, pointers may be truncated to 32 bits and crash clipboard calls.
# Без этих сигнатур указатели могут обрезаться до 32 бит и ломать вызовы буфера обмена.

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_user32.GetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
_user32.SetClipboardData.restype = ctypes.c_void_p

_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.restype = ctypes.c_bool
_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.restype = ctypes.c_void_p


def _is_vscode_window(hwnd):
    """Checks whether the target window is VS Code (Electron/code.exe).
    Проверяет, является ли целевое окно VS Code (Electron/code.exe)."""
    try:
        class_name = win32gui.GetClassName(hwnd)
        if class_name != "Chrome_WidgetWin_1":
            return False
        pid = ctypes.wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = _kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
            )
            if handle:
                try:
                    buf = ctypes.create_unicode_buffer(512)
                    size = ctypes.wintypes.DWORD(512)
                    ok = _kernel32.QueryFullProcessImageNameW(
                        handle, 0, buf, ctypes.byref(size)
                    )
                    if ok and buf.value:
                        exe_name = os.path.basename(buf.value).lower()
                        return exe_name == "code.exe"
                finally:
                    _kernel32.CloseHandle(handle)
        return False
    except Exception:
        return False


def _is_explorer_window(hwnd):
    """Checks whether the window is Windows Explorer or the desktop shell.
    Проверяет, является ли окно Проводником Windows или оболочкой рабочего стола."""
    try:
        class_name = win32gui.GetClassName(hwnd)
        return class_name in ("CabinetWClass", "Progman", "WorkerW")
    except Exception:
        return False


def _find_explorer_rename_edit(hwnd):
    """
    Finds the active rename Edit control in Explorer or on the desktop.
    Ищет активное поле переименования (Edit) в Explorer или на рабочем столе.

    When the user renames a file, Windows creates a child Edit control.
    If we focus the parent window instead, the rename box closes as if Enter was pressed.

    Когда пользователь переименовывает файл, Windows создаёт дочерний Edit-контрол.
    Если сфокусировать родительское окно вместо него, rename-бокс закроется как по Enter.

    Returns: HWND Edit-контрола или None.
    """
    try:
        foreground = _user32.GetForegroundWindow()
        if not foreground:
            return None

        fg_class = win32gui.GetClassName(foreground)

        if fg_class == "CabinetWClass":
            return _find_edit_child(foreground)

        if fg_class in ("Progman", "WorkerW"):
            return _find_edit_child(foreground)

        if fg_class == "Progman":
            def _enum_worker(hwnd_child, _):
                if win32gui.GetClassName(hwnd_child) == "WorkerW":
                    edit = _find_edit_child(hwnd_child)
                    if edit:
                        results.append(edit)
                return True
            results = []
            win32gui.EnumWindows(_enum_worker, None)
            if results:
                return results[0]

        if hwnd and hwnd != foreground:
            try:
                hwnd_class = win32gui.GetClassName(hwnd)
                if hwnd_class in ("CabinetWClass", "Progman", "WorkerW"):
                    edit = _find_edit_child(hwnd)
                    if edit:
                        return edit
            except Exception:
                pass

        return None

    except Exception as e:
        print(f"[INSERT] Ошибка поиска rename edit: {e}")
        return None


def _find_edit_child(parent_hwnd):
    """
    Finds a visible child window of class Edit inside parent_hwnd.
    Поле переименования в Explorer представляет собой видимый дочерний Edit-контрол.
    """
    found = [None]

    def _enum_callback(hwnd, _):
        try:
            class_name = win32gui.GetClassName(hwnd)
            if class_name == "Edit":
                if win32gui.IsWindowVisible(hwnd):
                    found[0] = hwnd
                    return False
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(parent_hwnd, _enum_callback, None)
    except Exception:
        pass

    return found[0]


def insert_text_at_cursor(hwnd, text, replace_left_chars=0, smart_spacing=True):
    """
    Inserts text through clipboard + Ctrl+V at the WinAPI level.
    Preserves and restores the original clipboard contents.

    Вставляет текст через буфер обмена и Ctrl+V на уровне WinAPI.
    Сохраняет и восстанавливает исходное содержимое буфера обмена.
    """
    old_clipboard = None
    try:
        # Keep the dictated text in memory so Ctrl+Alt+V can replay it later.
        # Сохраняем надиктованный текст в памяти, чтобы Ctrl+Alt+V мог вставить его повторно.
        with _dictated_lock:
            global _last_dictated_text
            _last_dictated_text = text
        # Trailing space is no longer injected automatically; spacing is decided contextually below.
        # Хвостовой пробел больше не добавляется автоматически; ниже пробел решается по контексту.
        if text and text[-1] not in (' ', '\n', '\r', '\t'):
            pass

        # Preserve the clipboard because paste-based insertion overwrites it temporarily.
        # Сохраняем текущее содержимое буфера обмена, потому что вставка через paste временно его перезаписывает.
        old_clipboard = _get_clipboard_text()
        if smart_spacing:
            text = _prepare_text_for_insertion(hwnd, text)

        if not _set_clipboard_text(text):
            print("[INSERT] Fallback: pyperclip")
            import pyperclip
            pyperclip.copy(text)

        time.sleep(0.05)

        # Explorer/Desktop rename boxes must be handled directly without refocusing the parent window.
        # Поля переименования в Explorer/Desktop обрабатываем напрямую, не переводя фокус на родительское окно.
        rename_edit = _find_explorer_rename_edit(hwnd)
        if rename_edit:
            print(f"[INSERT] Explorer rename edit: {rename_edit}")
            if replace_left_chars > 0:
                _send_backspace(replace_left_chars)
                time.sleep(0.03)
            _send_ctrl_v()
            time.sleep(0.1)
            print(f"[INSERT] Вставлено (rename): '{text}'")
            _remember_insert_context(hwnd, text)
            _restore_clipboard(old_clipboard)
            return True

        # VS Code can lose its inner editor focus if we force the top-level window again.
        # У VS Code можно сбить внутренний фокус редактора, если повторно форсировать top-level окно.
        if _is_vscode_window(hwnd):
            print("[INSERT] VS Code — пропускаем force_foreground")
        else:
            _force_foreground(hwnd)
            time.sleep(0.15)

        if replace_left_chars > 0:
            _send_backspace(replace_left_chars)
            time.sleep(0.03)

        _send_ctrl_v()
        time.sleep(0.1)

        print(f"[INSERT] Вставлено: '{text}'")
        _remember_insert_context(hwnd, text)
        _restore_clipboard(old_clipboard)
        return True

    except Exception as e:
        print(f"[INSERT ERROR] {e}")
        import traceback
        traceback.print_exc()
        _restore_clipboard(old_clipboard)
        return False



def get_last_dictated_text():
    """Возвращает последний надиктованный текст."""
    with _dictated_lock:
        return _last_dictated_text


def insert_last_dictated(hwnd):
    """
    Вставляет последний надиктованный текст (Ctrl+Alt+V).
    Сохраняет и восстанавливает clipboard.
    """
    with _dictated_lock:
        text = _last_dictated_text

    if not text:
        print("[INSERT] Нет надиктованного текста для вставки")
        return False

    preview = f"'{text[:50]}...'" if len(text) > 50 else f"'{text}'"
    print(f"[INSERT] Ctrl+Alt+V -> повторная вставка: {preview}")
    return insert_text_at_cursor(hwnd, text)


def clear_insert_context():
    """Reset smart-spacing history after manual editing or caret movement."""
    global _last_insert_target, _last_insert_ended_with_whitespace, _last_insert_time

    _last_insert_target = None
    _last_insert_ended_with_whitespace = True
    _last_insert_time = 0.0


def _prepare_text_for_insertion(hwnd, text):
    """Strips trailing space and adds a leading separator only when the caret context requires it.
    Убирает хвостовой пробел и добавляет ведущий разделитель только когда этого требует контекст каретки."""
    if not text:
        return text

    text = text.rstrip(' ')
    if not text or text[0].isspace():
        return text

    left_char = _get_char_left_of_caret(hwnd)
    if left_char is None:
        if _should_add_prefix_from_history(hwnd):
            return " " + text
        return text
    if left_char == "" or left_char.isspace():
        return text
    return " " + text


def _get_char_left_of_caret(hwnd):
    """
    Tries to read one character to the left of the caret through Win32 for standard
    text controls, without selecting or modifying any text.

    Пытается прочитать один символ слева от каретки через Win32 для стандартных
    текстовых контролов, без выделения и без вмешательства в содержимое поля.

    Возвращает:
    - "" если слева начало поля;
    - один символ, если удалось прочитать;
    - None, если контрол не отдаёт текст/каретку через Win32.
    """
    try:
        target = _get_text_target_hwnd(hwnd)
        if not target:
            return None
        return _get_char_left_from_edit_control(target)
    except Exception as e:
        print(f"[INSERT] Не удалось определить символ слева от курсора: {e}")
        return None


def _get_text_target_hwnd(hwnd):
    """Returns the focused text control inside the target window.
    Возвращает сфокусированный текстовый контрол внутри целевого окна."""
    rename_edit = _find_explorer_rename_edit(hwnd)
    if rename_edit:
        return rename_edit

    try:
        target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)

        class GUITHREADINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.DWORD),
                ("flags", ctypes.wintypes.DWORD),
                ("hwndActive", ctypes.wintypes.HWND),
                ("hwndFocus", ctypes.wintypes.HWND),
                ("hwndCapture", ctypes.wintypes.HWND),
                ("hwndMenuOwner", ctypes.wintypes.HWND),
                ("hwndMoveSize", ctypes.wintypes.HWND),
                ("hwndCaret", ctypes.wintypes.HWND),
                ("rcCaret", ctypes.wintypes.RECT),
            ]

        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if _user32.GetGUIThreadInfo(target_thread_id, ctypes.byref(info)):
            return info.hwndFocus or info.hwndCaret or hwnd
    except Exception:
        pass

    return hwnd


def _is_edit_like_class(class_name):
    class_name = (class_name or "").lower()
    return (
        class_name == "edit"
        or class_name.startswith("richedit")
    )


def _get_char_left_from_edit_control(hwnd):
    """Reads the character left of the caret for Edit/RichEdit controls.
    Читает символ слева от каретки для контролов Edit/RichEdit."""
    try:
        class_name = win32gui.GetClassName(hwnd)
        if not _is_edit_like_class(class_name):
            return None

        WM_GETTEXT = 0x000D
        WM_GETTEXTLENGTH = 0x000E
        EM_GETSEL = 0x00B0
        EM_GETPASSWORDCHAR = 0x00D2

        # Password controls must never be inspected or copied from.
        # В password-поля не лезем вообще.
        if win32gui.SendMessage(hwnd, EM_GETPASSWORDCHAR, 0, 0):
            return None

        start = ctypes.wintypes.DWORD()
        end = ctypes.wintypes.DWORD()
        win32gui.SendMessage(hwnd, EM_GETSEL, ctypes.byref(start), ctypes.byref(end))

        caret = int(start.value)
        if caret <= 0:
            return ""

        text_len = int(win32gui.SendMessage(hwnd, WM_GETTEXTLENGTH, 0, 0))
        if text_len <= 0:
            return ""

        buf = ctypes.create_unicode_buffer(text_len + 1)
        win32gui.SendMessage(hwnd, WM_GETTEXT, text_len + 1, buf)
        text = buf.value

        if caret - 1 >= len(text):
            return None

        return text[caret - 1]
    except Exception:
        return None


def _should_add_prefix_from_history(hwnd):
    """
    Fallback for windows where reading the left-of-caret character is unreliable.
    If the previous insert went to the same control and did not end with whitespace,
    add a separating space.

    Fallback для окон, где нельзя надёжно прочитать символ слева от каретки.
    Если предыдущая вставка была в тот же контрол и не заканчивалась пробелом,
    добавляем разделяющий пробел.
    """
    target = _get_text_target_hwnd(hwnd)
    if not target:
        return False

    if target != _last_insert_target:
        return False

    if _last_insert_ended_with_whitespace:
        return False

    return (time.time() - _last_insert_time) <= 15.0


def _remember_insert_context(hwnd, text):
    global _last_insert_target, _last_insert_ended_with_whitespace, _last_insert_time

    _last_insert_target = _get_text_target_hwnd(hwnd)
    _last_insert_ended_with_whitespace = (not text) or text[-1].isspace()
    _last_insert_time = time.time()




def _get_clipboard_text():
    """Reads Unicode text from the clipboard or returns None if it is empty or non-text.
    Получает Unicode-текст из буфера обмена или возвращает None, если буфер пуст или там не текст."""
    CF_UNICODETEXT = 13
    result = None
    deadline = time.time() + 1.0

    while time.time() < deadline:
        if _user32.OpenClipboard(0):
            try:
                if _user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                    h_data = _user32.GetClipboardData(CF_UNICODETEXT)
                    if h_data:
                        ptr = _kernel32.GlobalLock(h_data)
                        if ptr:
                            try:
                                result = ctypes.wstring_at(ptr)
                            finally:
                                _kernel32.GlobalUnlock(h_data)
                return result
            except Exception as e:
                print(f"[CLIPBOARD] Ошибка чтения: {e}")
                return None
            finally:
                _user32.CloseClipboard()
        else:
            time.sleep(0.05)

    return None


def _restore_clipboard(old_text):
    """Restores the clipboard contents after paste-based insertion.
    Восстанавливает содержимое буфера обмена после вставки через paste."""
    if old_text is None:
        return

    time.sleep(0.05)

    try:
        if _set_clipboard_text(old_text):
            print(f"[INSERT] 📋 Буфер восстановлен ({len(old_text)} симв.)")
        else:
            print("[INSERT] ⚠️ Не удалось восстановить буфер")
    except Exception as e:
        print(f"[INSERT] ⚠️ Ошибка восстановления буфера: {e}")


def _set_clipboard_text(text):
    """Writes text to the clipboard through the Win32 API with retries and a timeout.
    Устанавливает текст в буфер обмена через Win32 API с повторами и таймаутом."""
    CF_UNICODETEXT = 13
    deadline = time.time() + 2.0

    while time.time() < deadline:
        if _user32.OpenClipboard(0):
            try:
                _user32.EmptyClipboard()

                data = text.encode('utf-16-le') + b'\x00\x00'
                GMEM_MOVEABLE = 0x0002
                h_mem = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                if not h_mem:
                    return False

                ptr = _kernel32.GlobalLock(h_mem)
                if not ptr:
                    _kernel32.GlobalFree(h_mem)
                    return False

                ctypes.memmove(ptr, data, len(data))
                _kernel32.GlobalUnlock(h_mem)

                result = _user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                if not result:
                    _kernel32.GlobalFree(h_mem)
                    return False

                return True
            except Exception as e:
                print(f"[CLIPBOARD ERROR] {e}")
                return False
            finally:
                _user32.CloseClipboard()
        else:
            time.sleep(0.05)

    print("[CLIPBOARD] Таймаут 2с — буфер обмена занят")
    return False


def _force_foreground(hwnd, timeout=2.0):
    """Force-activates a window with a timeout so insertion never hangs forever.
    Принудительно активирует окно с таймаутом, чтобы вставка никогда не зависала навсегда."""
    result = [False]

    def _do():
        try:
            if not _user32.IsWindow(hwnd):
                print(f"[INSERT] Окно {hwnd} не существует!")
                return

            # Release any stuck modifiers before switching foreground threads.
            # Перед активацией окна отпускаем залипшие модификаторы.
            _release_all_modifiers()

            if _user32.IsIconic(hwnd):
                _user32.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)

            current_thread = win32api.GetCurrentThreadId()
            target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)

            attached = False
            if current_thread != target_thread_id:
                attached = bool(
                    _user32.AttachThreadInput(current_thread, target_thread_id, True)
                )

            try:
                _user32.SetForegroundWindow(hwnd)
                _user32.BringWindowToTop(hwnd)
                _user32.SetFocus(hwnd)
                result[0] = True
            finally:
                if attached:
                    _user32.AttachThreadInput(
                        current_thread, target_thread_id, False
                    )

            # Release them again afterwards in case AttachThreadInput dragged modifier state across threads.
            # После активации повторяем сброс на случай, если AttachThreadInput протащил состояние модификаторов между потоками.
            _release_all_modifiers()

        except Exception as e:
            print(f"[FOREGROUND ERROR] {e}")
            try:
                win32gui.SetForegroundWindow(hwnd)
                result[0] = True
            except Exception:
                pass

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        print(f"[INSERT] ⚠️ _force_foreground таймаут {timeout}с — продолжаем без фокуса")
        return False

    return result[0]



def _release_all_modifiers():
    """Force-releases Alt, Ctrl, Shift, and Win through SendInput.
    Принудительно отпускает Alt, Ctrl, Shift и Win через SendInput."""
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _fields_ = [
            ("type", ctypes.c_ulong),
            ("_input", _INPUT),
        ]

    modifiers = [
        (0x12, 0x38),  # Alt,   scan=0x38
        (0x10, 0x2A),  # Shift, scan=0x2A
        (0x11, 0x1D),  # Ctrl,  scan=0x1D
        (0x5B, 0x5B),  # Win,   scan=0x5B
    ]

    inputs = []
    for vk, scan in modifiers:
        ki = KEYBDINPUT(
            wVk=vk, wScan=scan, dwFlags=KEYEVENTF_KEYUP,
            time=0, dwExtraInfo=None
        )
        inp = INPUT(type=INPUT_KEYBOARD)
        inp._input.ki = ki
        inputs.append(inp)

    if inputs:
        arr = (INPUT * len(inputs))(*inputs)
        _user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _send_ctrl_v():
    """Sends Ctrl+V, or Ctrl+Shift+V for terminals embedded inside VS Code.
    Отправляет Ctrl+V, а для терминала внутри VS Code — Ctrl+Shift+V."""
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_V = 0x56
    KEYEVENTF_KEYUP = 0x0002

    SCAN_CTRL = 0x1D
    SCAN_SHIFT = 0x2A
    SCAN_ALT = 0x38
    SCAN_V = 0x2F

    # Start from a clean modifier state so paste is not polluted by user-held keys.
    # Начинаем с чистого состояния модификаторов, чтобы вставка не испортилась пользовательскими зажатыми клавишами.
    _release_all_modifiers()
    time.sleep(0.02)

    is_vscode_terminal = False
    try:
        hwnd = _user32.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd).lower()
        class_name = win32gui.GetClassName(hwnd)

        if class_name == "Chrome_WidgetWin_1":
            is_editor = "visual studio code" in title
            is_vscode_terminal = not is_editor
            print(f"[INSERT] VS Code {'редактор' if is_editor else 'терминал'}: '{title}'")
    except Exception:
        pass

    if is_vscode_terminal:
        _user32.keybd_event(VK_CONTROL, SCAN_CTRL, 0, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_SHIFT, SCAN_SHIFT, 0, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_V, SCAN_V, 0, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_V, SCAN_V, KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_SHIFT, SCAN_SHIFT, KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_CONTROL, SCAN_CTRL, KEYEVENTF_KEYUP, 0)
    else:
        _user32.keybd_event(VK_CONTROL, SCAN_CTRL, 0, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_V, SCAN_V, 0, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_V, SCAN_V, KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)
        _user32.keybd_event(VK_CONTROL, SCAN_CTRL, KEYEVENTF_KEYUP, 0)

    time.sleep(0.02)


def _send_backspace(count):
    """Deletes count characters to the left of the caret through Backspace key events.
    Удаляет count символов слева от каретки через события клавиши Backspace."""
    if count <= 0:
        return

    VK_BACK = 0x08
    KEYEVENTF_KEYUP = 0x0002
    SCAN_BACK = 0x0E

    _release_all_modifiers()
    time.sleep(0.02)

    for _ in range(count):
        _user32.keybd_event(VK_BACK, SCAN_BACK, 0, 0)
        time.sleep(0.005)
        _user32.keybd_event(VK_BACK, SCAN_BACK, KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)
