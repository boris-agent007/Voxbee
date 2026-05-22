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
Smart text copying from UI elements.
Умное копирование текста из UI-элементов.

Supports multiple browsers through UI Automation.
Поддерживает разные браузеры через UI Automation.

Element selection strategies:
Стратегии поиска элемента:
  A. Focused маленький → используем
  B. Focused большой → ищем блок кода ПОД КУРСОРОМ (contains_point)
  C. Не нашли → сканируем ВСЕ блоки кода, берём ближайший к курсору
  D. Нет блоков → ControlFromPoint + подъём вверх
  E. Fallback → focused целиком
"""

import ctypes
import ctypes.wintypes as wintypes
import time


# === Clipboard ===
# === Буфер обмена ===

def get_clipboard_text():
    """Reads the current clipboard text.
    Читает текущее текстовое содержимое буфера обмена."""
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    try:
        user32.OpenClipboard(None)
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        if not p:
            return ""
        text = ctypes.wstring_at(p)
        kernel32.GlobalUnlock(h)
        return text
    except Exception:
        return ""
    finally:
        try:
            user32.CloseClipboard()
        except Exception:
            pass


def set_clipboard_text(text):
    """Writes text into the clipboard with retries and a timeout.
    Записывает текст в буфер обмена с повторами и таймаутом."""
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
    kernel32.GlobalFree.restype = wintypes.HANDLE

    text_bytes = (text + '\0').encode('utf-16-le')
    size = len(text_bytes)

    deadline = time.time() + 2.0  # Maximum wait: 2 seconds. / Максимальное ожидание: 2 секунды.

    while time.time() < deadline:
        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()

                h = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
                if not h:
                    return False

                p = kernel32.GlobalLock(h)
                if not p:
                    kernel32.GlobalFree(h)
                    return False

                ctypes.memmove(p, text_bytes, size)
                kernel32.GlobalUnlock(h)

                result = user32.SetClipboardData(CF_UNICODETEXT, h)
                if not result:
                    kernel32.GlobalFree(h)
                    return False

                return True
            except Exception as e:
                print(f"[CLIPBOARD ERROR] {e}")
                return False
            finally:
                user32.CloseClipboard()
        else:
            time.sleep(0.05)

    print("[CLIPBOARD] Таймаут 2с — буфер обмена занят")
    return False


# === Utilities ===
# === Утилиты ===

def _detect_browser():
    """Detects the browser from the active window.
    Определяет браузер по активному окну."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown"

        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        cls = class_name.value.lower()

        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, 512)
        ttl = title.value.lower()

        if 'yandex' in ttl or 'яндекс' in ttl:
            return 'yandex'
        if 'chrome_widgetwin' in cls or 'chrome' in cls:
            if 'edge' in ttl or 'microsoft' in ttl:
                return 'edge'
            return 'chrome'
        if 'mozillawindowclass' in cls or 'firefox' in ttl:
            return 'firefox'
        return "unknown"
    except Exception:
        return "unknown"


def _get_cursor_pos():
    """Returns the current mouse cursor position.
    Возвращает текущую позицию курсора мыши."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def _click_at_cursor():
    """
    Clicks the left mouse button at the current cursor position.
    Used to move focus to the element under the cursor.

    Выполняет клик левой кнопкой в текущей позиции курсора.
    Используется, чтобы перевести фокус на элемент под курсором.
    """
    user32 = ctypes.windll.user32
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

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


def _contains_point(element, x, y):
    """Checks whether the element rectangle contains the point (x, y).
    Проверяет, содержит ли BoundingRectangle точку (x, y)."""
    r = _get_element_rect(element)
    if not r:
        return False
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


# === Text collection ===
# === Сбор текста ===

def _collect_lines(element, lines, depth=0):
    """
    Recursively collects text line by line.
    A group of leaf elements is merged into a single line.

    Рекурсивно собирает текст построчно.
    Группа листовых элементов считается одной склеенной строкой.
    """
    if depth > 15:
        return

    try:
        children = element.GetChildren()
    except Exception:
        children = []

    if not children:
        name = element.Name
        if name and name.strip():
            lines.append(name)
        return

    # If every child is a leaf, treat them as fragments of the same rendered line.
    # Если все дети листовые, считаем их фрагментами одной визуальной строки.
    child_names = []
    all_leaf = True
    for child in children:
        try:
            grandchildren = child.GetChildren()
        except Exception:
            grandchildren = []
        if grandchildren:
            all_leaf = False
            break
        if child.Name:
            child_names.append(child.Name)

    if all_leaf and child_names:
        line = ''.join(child_names)
        if line.strip():
            lines.append(line)
        return

    for child in children:
        _collect_lines(child, lines, depth + 1)


# === Code-block detection ===
# === Определение блока кода ===

def _is_likely_code_block(element):
    """
    Heuristically detects whether an element looks like a code block.
    Эвристически проверяет, похож ли элемент на блок кода.

    Heuristics used for ChatGPT, Arena, Claude, and similar UIs:
    Эвристики, которые работают для ChatGPT, Arena, Claude и похожих UI:
    - Высота > 100px (код обычно многострочный)
    - Ширина > 300px (код занимает ширину контента)
    - Имеет вложенные дети с текстом (строки кода)
    """
    try:
        r = _get_element_rect(element)
        if not r:
            return False
        h = r[3] - r[1]
        w = r[2] - r[0]

        if h < 100 or w < 300 or h > 5000:
            return False

        children = element.GetChildren()
        child_count = len(children)

        # Pattern 1: wrapper with a single inner container holding code lines.
        # Паттерн 1: обёртка с одним внутренним контейнером, в котором лежат строки кода.
        if child_count == 1:
            inner = children[0]
            try:
                inner_children = inner.GetChildren()
                if len(inner_children) >= 3:
                    return True
            except Exception:
                pass

        # Pattern 2: code-like direct children.
        # Паттерн 2: прямые дети, похожие на строки кода.
        if child_count >= 3:
            text_children = 0
            for child in children[:15]:
                try:
                    ct = child.ControlTypeName
                    if ct in ('TextControl', 'GroupControl', 'EditControl'):
                        text_children += 1
                except Exception:
                    pass
            if text_children >= 3:
                return True

        return False
    except Exception:
        return False


# === Strategy A: search under the cursor ===
# === Стратегия A: поиск под курсором ===

def _find_code_block_at_cursor(root, cx, cy):
    """
    Recursively searches for a code block that contains the cursor point.
    Works well in Edge and Chrome; may fail in Yandex Browser.

    Рекурсивно ищет блок кода, содержащий точку курсора.
    Хорошо работает в Edge и Chrome, но может не сработать в Яндекс Браузере.
    """
    best = None
    best_area = float('inf')

    def _search(element, depth=0):
        nonlocal best, best_area
        if depth > 12:
            return

        try:
            children = element.GetChildren()
        except Exception:
            return

        for child in children:
            if not _contains_point(child, cx, cy):
                continue

            area = _get_element_area(child)

            # Narrow candidates by area before running the heavier heuristics.
            # Сначала отсеиваем кандидатов по площади, а потом применяем более тяжёлую эвристику.
            if 10_000 < area < 2_000_000:
                if _is_likely_code_block(child):
                    if area < best_area:
                        best = child
                        best_area = area
                        print(f"[COPY]   📦 Кандидат (cursor): "
                              f"{area} px²")

            # Continue descending to find the smallest matching block.
            # Продолжаем обход вглубь, чтобы найти самый узкий подходящий блок.
            _search(child, depth + 1)

    _search(root)
    return best


# === Strategy B: scan all code blocks ===
# === Стратегия B: сканирование всех блоков кода ===

def _find_all_code_blocks(root):
    """
    Scans the entire tree and collects all elements that look like code blocks.
    Returns a list of elements.

    Сканирует всё дерево и находит все элементы, похожие на блоки кода.
    Возвращает список элементов.
    """
    blocks = []

    def _search(element, depth=0):
        if depth > 12:
            return

        try:
            children = element.GetChildren()
        except Exception:
            return

        for child in children:
            if _is_likely_code_block(child):
                blocks.append(child)
                # Do not recurse into a block once it is already accepted as a whole.
                # Не рекурсируем внутрь блока, если уже приняли его целиком.
                continue

            _search(child, depth + 1)

    _search(root)
    return blocks


def _pick_closest_to_cursor(blocks, cursor_y):
    """
    Picks the block whose vertical position is closest to the cursor.
    Выбирает блок, который ближе всего к курсору по вертикали.
    """
    best = None
    best_dist = float('inf')

    for block in blocks:
        r = _get_element_rect(block)
        if not r:
            continue

        # Measure distance from the cursor to the block center.
        # Меряем расстояние от курсора до центра блока.
        center_y = (r[1] + r[3]) / 2
        dist = abs(center_y - cursor_y)

        # If the cursor is already inside the block, treat it as an exact hit.
        # Если курсор уже внутри блока, считаем это точным попаданием.
        if r[1] <= cursor_y <= r[3]:
            dist = 0

        if dist < best_dist:
            best = block
            best_dist = dist

    return best


# === Main element lookup ===
# === Главный поиск элемента ===

def _find_best_element():
    """
    Finds the best UI element to copy from.
    Находит лучший UI-элемент для копирования.

    Strategies in priority order:
    Стратегии по приоритету:
    A. Focused маленький → используем
    B. Ищем блок кода содержащий курсор (contains_point)
    C. Сканируем ВСЕ блоки кода → берём ближайший к курсору
    D. ControlFromPoint + подъём вверх
    E. Focused целиком (fallback)
    """
    try:
        import uiautomation as auto
    except ImportError:
        return None

    focused = auto.GetFocusedControl()
    if not focused:
        return None

    focused_area = _get_element_area(focused)
    cx, cy = _get_cursor_pos()

    # If the focused element is the whole window, focus may still be stale after the click.
    # Wait briefly and query focus again.
    # Если focused — это целое окно, значит фокус мог ещё не обновиться после клика.
    # Немного ждём и перезапрашиваем фокус.
    if focused_area > 3_000_000:
        print(f"[COPY] ⏳ Focused слишком большой ({focused_area} px²) — жду обновления...")
        for attempt in range(3):
            time.sleep(0.2)
            focused2 = auto.GetFocusedControl()
            if focused2:
                area2 = _get_element_area(focused2)
                if area2 < focused_area:
                    focused = focused2
                    focused_area = area2
                    print(f"[COPY] 🔄 Retry {attempt+1}: focused ({focused_area} px²)")
                    if focused_area < 3_000_000:
                        break

    # A small focused element is already precise enough.
    # Если focused маленький, он уже достаточно точен.
    if focused_area < 500_000:
        print(f"[COPY] 📌 Focused ({focused_area} px²) — используем")
        return focused

    print(f"[COPY] ⚠️ Focused большой ({focused_area} px²)")
    print(f"[COPY] 📍 Курсор: ({cx}, {cy})")

    # Strategy B: first try a block directly under the cursor.
    # Стратегия B: сначала ищем блок кода прямо под курсором.
    print("[COPY] 🔍 Стратегия B: поиск блока кода под курсором...")
    block = _find_code_block_at_cursor(focused, cx, cy)
    if block:
        area = _get_element_area(block)
        print(f"[COPY] ✅ Найден под курсором ({area} px²)")
        return block

    # Strategy C: scan all code blocks and choose the closest one.
    # Стратегия C: сканируем все блоки кода и берём ближайший.
    print("[COPY] 🔍 Стратегия C: сканирование всех блоков кода...")
    blocks = _find_all_code_blocks(focused)
    if blocks:
        print(f"[COPY] 📦 Найдено {len(blocks)} блоков кода")
        for i, b in enumerate(blocks):
            r = _get_element_rect(b)
            if r:
                print(f"[COPY]   [{i+1}] y={r[1]}-{r[3]}, "
                      f"h={r[3]-r[1]}, w={r[2]-r[0]}")

        closest = _pick_closest_to_cursor(blocks, cy)
        if closest:
            r = _get_element_rect(closest)
            area = _get_element_area(closest)
            print(f"[COPY] ✅ Выбран ближайший к курсору ({area} px²)")
            return closest

    # Strategy D: start from the element under the cursor and climb up.
    # Стратегия D: берём элемент под курсором и поднимаемся вверх по дереву.
    print("[COPY] 🔍 Стратегия D: ControlFromPoint...")
    try:
        at_cursor = auto.ControlFromPoint(cx, cy)
        if at_cursor:
            cursor_area = _get_element_area(at_cursor)

            if cursor_area < 5_000:
                current = at_cursor
                for _ in range(10):
                    try:
                        parent = current.GetParentControl()
                        if not parent:
                            break
                        if _get_element_area(parent) > 1_000_000:
                            break
                        if _is_likely_code_block(parent):
                            area = _get_element_area(parent)
                            print(f"[COPY] ✅ Найден вверх по дереву "
                                  f"({area} px²)")
                            return parent
                        current = parent
                    except Exception:
                        break

            if cursor_area < 500_000:
                return at_cursor
    except Exception:
        pass

    # Final fallback: return the focused element as-is.
    # Последний fallback: используем focused как есть.
    print("[COPY] ⚠️ Блоки кода не найдены, используем focused целиком")
    return focused


# === Copy pipeline ===
# === Копирование ===

def _copy_via_ui_automation():
    """Finds an element, shows the overlay, and collects its text line by line.
    Находит элемент, показывает рамку и собирает его текст построчно."""
    browser = _detect_browser()
    print(f"[COPY] 🌐 Браузер: {browser}")

    element = _find_best_element()
    if not element:
        return None

    # Store the selected element so the "more/less" navigation can keep working.
    # Сохраняем элемент в selection_overlay, чтобы продолжала работать навигация «больше/меньше».
    try:
        from selection_overlay import set_current_element
        set_current_element(element)
    except Exception as e:
        print(f"[COPY] ⚠️ Overlay: {e}")

    # Collect text line by line to preserve structure better than plain Name.
    # Собираем текст построчно, чтобы лучше сохранить структуру, чем через один Name.
    lines = []
    _collect_lines(element, lines)

    if lines:
        text = '\n'.join(lines)
        # Build a compact preview for logs without printing the whole block.
        # Собираем короткое превью для лога, не печатая весь блок целиком.
        if len(lines) <= 4:
            preview = ' | '.join(l[:60] for l in lines)
        else:
            top = ' | '.join(l[:60] for l in lines[:2])
            bot = ' | '.join(l[:60] for l in lines[-2:])
            preview = f"{top} ... {bot}"
        print(f"[COPY] ✅ {len(lines)} строк, {len(text)} символов")
        print(f"[COPY] 📄 {preview[:200]}")
        return text

    # If structured extraction is empty, fall back to the element Name.
    # Если структурированный сбор пуст, используем Name элемента.
    name = element.Name
    if name and name.strip():
        print(f"[COPY] ⚠️ Fallback Name ({len(name)} символов)")
        return name

    return None

# === Public entry point ===
# === Главная функция ===

def smart_copy(send_hotkey_fn):
    """
    Smart copy flow:
    1. Ctrl+C (если есть выделение)
    2. If the clipboard did not change, click for focus and fall back to UI Automation.

    Returns: (True, method) or (False, None)

    Умное копирование:
    1. Ctrl+C, если уже есть выделение
    2. Если буфер не изменился, кликаем для фокуса и переходим на UI Automation

    Возвращает: (True, метод) или (False, None)
    """
    import threading as _threading

    before = get_clipboard_text()

    # Try the normal copy shortcut first because it is the cheapest and most accurate path.
    # Сначала пробуем обычный Ctrl+C, потому что это самый дешёвый и точный путь.
    send_hotkey_fn("ctrl+c")
    time.sleep(0.15)

    after = get_clipboard_text()

    if after and after != before:
        print(f"[COPY] 📋 Ctrl+C: {len(after)} символов")
        return True, "ctrl+c"

    # If Ctrl+C produced no new clipboard data, there is no selection or the element blocks copy.
    # Если Ctrl+C не дал новых данных в буфере, значит выделения нет или элемент не поддерживает копирование.
    print("[COPY] ⚠️ Ctrl+C не сработал")

    # Move focus to the element under the cursor before querying UI Automation.
    # Перед UI Automation переводим фокус на элемент под курсором.
    print("[COPY] 🖱️ Клик для установки фокуса...")
    _click_at_cursor()
    time.sleep(0.25)

    # Run UI Automation in a separate thread so the main flow is protected by a timeout.
    # Запускаем UI Automation в отдельном потоке, чтобы основной поток был защищён таймаутом.
    print("[COPY] 🔍 UI Automation...")
    result = [None]

    def _do_ui_copy():
        try:
            result[0] = _copy_via_ui_automation()
        except Exception as e:
            print(f"[COPY] ❌ UI Automation ошибка: {e}")

    t = _threading.Thread(target=_do_ui_copy, daemon=True)
    t.start()
    t.join(timeout=5.0)

    if t.is_alive():
        print("[COPY] ⚠️ UI Automation таймаут 5с — пропускаем")
        return False, None

    text = result[0]
    if text:
        set_clipboard_text(text)
        print(f"[COPY] 📋 UI Automation: {len(text)} символов")
        return True, "ui_automation"

    print("[COPY] ❌ Не удалось скопировать")
    return False, None
