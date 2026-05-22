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
Voice input converter for mathematical expressions.
Конвертер голосового ввода в математические выражения.

Converts Russian numerals, operators, and symbols into formulas.
Преобразует русские числительные, операторы и знаки в формулы.

Examples:
Примеры:
    "один плюс два"                    → "1 + 2"
    "тысяча двести тридцать два"       → "1232"
    "скобка открыть три умножить пять скобка закрыть" → "(3 * 5)"
    "одна четвёртая"                   → "1/4"
    "десять в квадрате"                → "10²"
"""
import ast
import re


# ═══════════════════════════════════════
#  NUMERAL DICTIONARIES
#  СЛОВАРИ ЧИСЛИТЕЛЬНЫХ
# ═══════════════════════════════════════

ONES = {
    'ноль': 0, 'нуль': 0,
    'один': 1, 'одна': 1, 'одно': 1,
    'два': 2, 'две': 2,
    'три': 3, 'четыре': 4, 'пять': 5,
    'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9,
    'десять': 10, 'одиннадцать': 11, 'двенадцать': 12,
    'тринадцать': 13, 'четырнадцать': 14, 'пятнадцать': 15,
    'шестнадцать': 16, 'семнадцать': 17, 'восемнадцать': 18,
    'девятнадцать': 19,
}

TENS = {
    'двадцать': 20, 'тридцать': 30, 'сорок': 40,
    'пятьдесят': 50, 'шестьдесят': 60, 'семьдесят': 70,
    'восемьдесят': 80, 'девяносто': 90,
}

HUNDREDS = {
    'сто': 100, 'двести': 200, 'триста': 300,
    'четыреста': 400, 'пятьсот': 500, 'шестьсот': 600,
    'семьсот': 700, 'восемьсот': 800, 'девятьсот': 900,
}

MULTIPLIERS = {
    'тысяча': 1000, 'тысячи': 1000, 'тысяч': 1000, 'тысячу': 1000,
    'миллион': 1_000_000, 'миллиона': 1_000_000, 'миллионов': 1_000_000,
    'миллиард': 1_000_000_000, 'миллиарда': 1_000_000_000, 'миллиардов': 1_000_000_000,
}

# Combined dictionary of number words without multipliers.
# Объединённый словарь числовых слов (без множителей)
ALL_NUMBERS = {}
ALL_NUMBERS.update(ONES)
ALL_NUMBERS.update(TENS)
ALL_NUMBERS.update(HUNDREDS)

# Ordinal numerals used as fraction denominators.
# Порядковые числительные (знаменатели дробей)
# Base ordinals for units and teens.
# Базовые порядковые — единицы и подростки
ORDINALS_BASE = {
    'вторая': 2, 'второй': 2, 'вторых': 2,
    'третья': 3, 'третий': 3, 'третьих': 3, 'третей': 3,
    'четвёртая': 4, 'четвертая': 4, 'четвёртый': 4, 'четвертый': 4,
    'четвёртых': 4, 'четвертых': 4,
    'пятая': 5, 'пятый': 5, 'пятых': 5,
    'шестая': 6, 'шестой': 6, 'шестых': 6,
    'седьмая': 7, 'седьмой': 7, 'седьмых': 7,
    'восьмая': 8, 'восьмой': 8, 'восьмых': 8,
    'девятая': 9, 'девятый': 9, 'девятых': 9,
    'одиннадцатая': 11, 'одиннадцатый': 11, 'одиннадцатых': 11,
    'двенадцатая': 12, 'двенадцатый': 12, 'двенадцатых': 12,
    'тринадцатая': 13, 'тринадцатый': 13, 'тринадцатых': 13,
    'четырнадцатая': 14, 'четырнадцатый': 14, 'четырнадцатых': 14,
    'пятнадцатая': 15, 'пятнадцатый': 15, 'пятнадцатых': 15,
    'шестнадцатая': 16, 'шестнадцатый': 16, 'шестнадцатых': 16,
    'семнадцатая': 17, 'семнадцатый': 17, 'семнадцатых': 17,
    'восемнадцатая': 18, 'восемнадцатый': 18, 'восемнадцатых': 18,
    'девятнадцатая': 19, 'девятнадцатый': 19, 'девятнадцатых': 19,
}

# Ordinal tens.
# Порядковые десятки
ORDINALS_TENS = {
    'двадцатая': 20, 'двадцатый': 20, 'двадцатых': 20,
    'тридцатая': 30, 'тридцатый': 30, 'тридцатых': 30,
    'сороковая': 40, 'сороковой': 40, 'сороковых': 40,
    'пятидесятая': 50, 'пятидесятый': 50, 'пятидесятых': 50,
    'шестидесятая': 60, 'шестидесятый': 60, 'шестидесятых': 60,
    'семидесятая': 70, 'семидесятый': 70, 'семидесятых': 70,
    'восьмидесятая': 80, 'восьмидесятый': 80, 'восьмидесятых': 80,
    'девяностая': 90, 'девяностый': 90, 'девяностых': 90,
}

# Ordinal hundreds.
# Порядковые сотни
ORDINALS_HUNDREDS = {
    'сотая': 100, 'сотый': 100, 'сотых': 100,
    'двухсотая': 200, 'двухсотый': 200, 'двухсотых': 200,
    'трёхсотая': 300, 'трехсотая': 300, 'трёхсотый': 300, 'трехсотый': 300,
    'трёхсотых': 300, 'трехсотых': 300,
}

# Ordinal thousands.
# Порядковые тысячные
ORDINALS_MULT = {
    'тысячная': 1000, 'тысячный': 1000, 'тысячных': 1000,
    'миллионная': 1_000_000, 'миллионный': 1_000_000, 'миллионных': 1_000_000,
}

# "Tenth" is a special case: both ordinal and decimal.
# Десятая — особый случай (и порядковое, и десятичная)
ORDINALS_SPECIAL = {
    'десятая': 10, 'десятый': 10, 'десятых': 10,
}

# Combined dictionary of all ordinal forms.
# Объединённый словарь всех порядковых
ORDINALS_DENOM = {}
ORDINALS_DENOM.update(ORDINALS_BASE)
ORDINALS_DENOM.update(ORDINALS_TENS)
ORDINALS_DENOM.update(ORDINALS_HUNDREDS)
ORDINALS_DENOM.update(ORDINALS_MULT)
ORDINALS_DENOM.update(ORDINALS_SPECIAL)


def _is_ordinal_word(word):
    """Checks whether the word is an ordinal numeral.
    Проверяет, является ли слово порядковым числительным."""
    return word.lower() in ORDINALS_DENOM


def _parse_denominator(tokens, start):
    """
    Parses a compound denominator starting at position start.
    Парсит составной знаменатель из позиции start.
    'сорок девятых' → (49, количество_съеденных_токенов)
    'пятых' → (5, 1)
    'двести тридцать седьмых' → (237, 3)

    Returns (denominator, count) or (None, 0).
    Возвращает (denominator, count) или (None, 0).
    """
    # Collect cardinal numerals (tens, hundreds) before the final ordinal.
    # Собираем обычные числительные (десятки, сотни) перед финальным порядковым
    num_words = []
    j = start
    while j < len(tokens):
        w = tokens[j].lower()
        if _is_number_word(w):
            num_words.append(w)
            j += 1
        elif w in ORDINALS_DENOM:
            # Final ordinal word.
            # Финальное порядковое слово
            base = ORDINALS_DENOM[w]
            prefix = _parse_number_sequence(num_words) if num_words else 0
            denominator = prefix + base
            count = j - start + 1
            return denominator, count
        else:
            break

    return None, 0


# ═══════════════════════════════════════
#  OPERATORS AND SYMBOLS
#  ОПЕРАТОРЫ И ЗНАКИ
# ═══════════════════════════════════════

# Multi-word phrases; process them first from longest to shortest.
# Мультисловные фразы (обрабатываются первыми, порядок: длинные → короткие)
MULTI_WORD_OPS = [
    ('больше или равно', ' >= '),
    ('меньше или равно', ' <= '),
    ('не равно', ' != '),
    ('точка с запятой', ';'),
    ('скобка открыть', '('),
    ('скобка закрыть', ')'),
    ('открыть скобку', '('),
    ('закрыть скобку', ')'),
    ('открыть скобка', '('),
    ('закрыть скобка', ')'),
    ('открыть скобу', '('),
    ('закрыть скобу', ')'),
    ('скобку открыть', '('),
    ('скобку закрыть', ')'),
    ('скобу открыть', '('),
    ('скобу закрыть', ')'),
    ('в квадрате', '²'),
    ('в кубе', '³'),
    ('в первой степени', '^1'),
    ('в второй степени', '²'),
    ('в третьей степени', '³'),
    ('в четвёртой степени', '^4'),
    ('в четвертой степени', '^4'),
    ('в пятой степени', '^5'),
    ('в шестой степени', '^6'),
    ('в седьмой степени', '^7'),
    ('в восьмой степени', '^8'),
    ('в девятой степени', '^9'),
    ('в десятой степени', '^10'),
    ('в степени', '^'),
    # Operations with the preposition "на".
    # Операции с предлогом "на"
    ('умножить на', ' * '),
    ('умножь на', ' * '),
    ('помножить на', ' * '),
    ('помножь на', ' * '),
    ('разделить на', ' / '),
    ('раздели на', ' / '),
    ('поделить на', ' / '),
    ('подели на', ' / '),
    ('делить на', ' / '),
    ('дели на', ' / '),
]

# Single-word operators.
# Односложные операторы
SINGLE_OPS = {
    'плюс': '+',
    'минус': '-',
    'умножить': '*',
    'умножение': '*',
    'разделить': '/',
    'делить': '/',
    'деление': '/',
    'равно': '=',
    'равняется': '=',
    'больше': '>',
    'меньше': '<',
    'процент': '%',
    'процентов': '%',
    'корень': '√',
    'пи': 'π',
    'бесконечность': '∞',
    'точка': '.',
    'запятая': ',',
    'двоеточие': ':',
    # Variables.
    # Переменные
    'икс': 'x',
    'игрек': 'y',
    'зет': 'z',
    'альфа': 'α',
    'бета': 'β',
    'гамма': 'γ',
    'дельта': 'δ',
    'лямбда': 'λ',
    'сигма': 'σ',
    'тета': 'θ',
    'фи': 'φ',
    'омега': 'ω',
}

# Symbols that are already final and should not be converted again.
# Символы, которые уже не нужно конвертировать
_PASSTHROUGH_SYMBOLS = frozenset({
    '+', '-', '*', '/', '=', '>', '<', '>=', '<=', '!=',
    '(', ')', '[', ']', '{', '}',
    ';', ':', '.', ',',
    '²', '³', '^', '√', 'π', '∞', '%',
})
_KEYBOARD_TOKEN_PREFIX = "__kb__:"
_SPACE_TOKEN = "__space__"
_LIST_BREAK_TOKEN = "__list_break__"

KEYBOARD_WORDS = {
    'а': 'а',
    'б': 'б', 'бэ': 'б',
    'в': 'в', 'вэ': 'в',
    'г': 'г', 'гэ': 'г',
    'д': 'д', 'дэ': 'д',
    'е': 'е',
    'ж': 'ж', 'же': 'ж',
    'з': 'з', 'зэ': 'з',
    'и': 'и',
    'й': 'й',
    'к': 'к', 'ка': 'к',
    'л': 'л', 'эль': 'л',
    'м': 'м', 'эм': 'м',
    'н': 'н', 'эн': 'н',
    'о': 'о',
    'п': 'п', 'пэ': 'п',
    'р': 'р', 'эр': 'р',
    'с': 'с', 'эс': 'с',
    'т': 'т', 'тэ': 'т',
    'у': 'у',
    'ф': 'ф', 'эф': 'ф',
    'х': 'х', 'ха': 'х',
    'ц': 'ц', 'це': 'ц',
    'ч': 'ч', 'че': 'ч',
    'ш': 'ш', 'ша': 'ш',
    'щ': 'щ', 'ща': 'щ',
    'ы': 'ы',
    'э': 'э',
    'ю': 'ю',
    'я': 'я',
    'слэш': '/',
    'правый_слэш': '/',
    'обратный_слэш': '\\',
    'левый_слэш': '\\',
    'бэкслэш': '\\',
    'собака': '@',
    'решетка': '#',
    'решётка': '#',
    'хеш': '#',
    'доллар': '$',
    'амперсанд': '&',
    'звездочка': '*',
    'звёздочка': '*',
    'подчеркивание': '_',
    'подчёркивание': '_',
    'дефис': '-',
    'тире': '-',
    'плюсик': '+',
    'восклицательный_знак': '!',
    'вопросительный_знак': '?',
    'апостроф': "'",
    'кавычка': '"',
    'обратная_кавычка': '`',
    'тильда': '~',
    'левая_скобка': '(',
    'правая_скобка': ')',
    'левая_квадратная_скобка': '[',
    'правая_квадратная_скобка': ']',
    'левая_фигурная_скобка': '{',
    'правая_фигурная_скобка': '}',
}

# Phonetic names of Latin letters.
# Фонетические названия латинских букв.
# They are used ONLY when an uppercase/lowercase/title-case modifier is present.
# Применяются ТОЛЬКО при наличии модификатора большая/маленькая/заглавная.
# Without a modifier, Cyrillic KEYBOARD_WORDS take priority.
# Без модификатора — приоритет у кириллических KEYBOARD_WORDS.
LATIN_PHONETIC_WORDS = {
    'эй': 'a', 'ай': 'a',
    'би': 'b', 'бии': 'b',
    'си': 'c', 'сии': 'c',
    'ди': 'd', 'дии': 'd',
    'и': 'e',
    'эф': 'f',
    'джи': 'g', 'же': 'g',
    'эйч': 'h', 'аш': 'h',
    'ай': 'i',
    'джей': 'j',
    'кей': 'k',
    'эл': 'l', 'эль': 'l',
    'эм': 'm',
    'эн': 'n',
    'оу': 'o',
    'пи': 'p',
    'кью': 'q', 'кю': 'q',
    'ар': 'r', 'эр': 'r',
    'эс': 's',
    'ти': 't', 'тии': 't',
    'ю': 'u',
    'ви': 'v', 'вии': 'v',
    'дабл': 'w',
    'экс': 'x', 'икс': 'x',
    'вай': 'y',
    'зет': 'z', 'зэт': 'z',
}

# The modifier "маленькая" is an explicit request for lowercase Latin letters.
# Модификатор «маленькая» — явный запрос строчной латиницы
_LOWERCASE_WORDS = frozenset({'маленькая', 'строчная', 'маленький', 'строчный'})

KEYBOARD_MULTI_WORDS = [
    ('восклицательный знак', '!'),
    ('вопросительный знак', '?'),
    ('обратный слэш', '\\'),
    ('левый слэш', '\\'),
    ('правый слэш', '/'),
    ('левая квадратная скобка', '['),
    ('правая квадратная скобка', ']'),
    ('левая фигурная скобка', '{'),
    ('правая фигурная скобка', '}'),
    ('левая скобка', '('),
    ('правая скобка', ')'),
    ('точка с запятой', ';'),
]

_MATH_BINARY_OPERATORS = frozenset({'+', '-', '*', '/', '=', '>', '<', '>=', '<=', '!='})
_UPPERCASE_WORDS = frozenset({'большая', 'заглавная', 'прописная', 'большой', 'заглавный', 'прописной'})
_LOWERCASE_WORDS = frozenset({'маленькая', 'строчная', 'маленький', 'строчный'})
_ALL_CASE_WORDS = _UPPERCASE_WORDS | _LOWERCASE_WORDS
_pending_math_compact = ""
_MATH_HINT_WORDS = frozenset(
    set(SINGLE_OPS.keys())
    | set(KEYBOARD_WORDS.keys())
    | set(LATIN_PHONETIC_WORDS.keys())
    | set(ALL_NUMBERS.keys())
    | set(MULTIPLIERS.keys())
    | set(ORDINALS_DENOM.keys())
    | _ALL_CASE_WORDS
    | {'скобка', 'скобку', 'скобки', 'скобу', 'открыть', 'закрыть', 'пробел'}
)


# ═══════════════════════════════════════
#  NUMBER PARSING
#  ПАРСИНГ ЧИСЕЛ
# ═══════════════════════════════════════

def _is_number_word(word):
    """Checks whether a word is a numeral or a multiplier.
    Проверяет, является ли слово числительным или множителем."""
    w = word.lower()
    return w in ALL_NUMBERS or w in MULTIPLIERS


def _parse_number_sequence(words):
    """
    Parses a sequence of Russian number words into an int.
    Парсит последовательность русских числительных в int.

    Examples:
    Примеры:
        ['двадцать', 'три']                    → 23
        ['тысяча', 'двести', 'тридцать', 'два'] → 1232
        ['два', 'миллиона', 'триста', 'тысяч'] → 2_300_000
    """
    if not words:
        return 0

    total = 0
    current = 0

    for word in words:
        w = word.lower()

        if w in ONES:
            current += ONES[w]
        elif w in TENS:
            current += TENS[w]
        elif w in HUNDREDS:
            current += HUNDREDS[w]
        elif w in MULTIPLIERS:
            mult = MULTIPLIERS[w]
            if current == 0:
                current = 1
            total += current * mult
            current = 0

    total += current
    return total


def _parse_number_sequence_from_list(groups):
    """
    Parses a list of numeral groups.
    Парсит список групп числительных.
    Each group represents a separate compound number (for example ['двадцать', 'три'] -> 23).
    Каждая группа — это отдельное составное число (например ['двадцать', 'три'] → 23).
    The function parses each group and sums the results for fractions or mixed numbers.
    Функция парсит каждую группу и суммирует результаты (для дробей/смешанных чисел).
    For regular numbers, string concatenation is used in the main code path.
    Для обычных чисел используется конкатенация строк в основном коде.
    """
    if not groups:
        return 0
    
    total = 0
    for group in groups:
        total += _parse_number_sequence(group)
    return total


def _parse_denominator_from_tokens(tokens_list):
    """
    Parses a denominator from a token list without using global tokens.
    Парс знаменателя из списка токенов (без доступа к глобальным tokens).
    Returns (denominator, count) or (None, 0).
    Возвращает (denominator, count) или (None, 0).
    """
    num_words = []
    j = 0
    while j < len(tokens_list):
        w = tokens_list[j].lower()
        if _is_number_word(w):
            num_words.append(w)
            j += 1
        elif w in ORDINALS_DENOM:
            base = ORDINALS_DENOM[w]
            prefix = _parse_number_sequence(num_words) if num_words else 0
            denominator = prefix + base
            return denominator, j + 1
        else:
            break

    return None, 0


def _split_number_group_into_numbers(num_words):
    """
    Splits a group of numeral words into separate numbers.
    Разбивает группу числительных на отдельные числа.

    'двадцать', 'три' → [['двадцать', 'три']]  (одно число 23)
    'двенадцать', 'семьдесят', 'четыре' → [['двенадцать'], ['семьдесят', 'четыре']]  (два числа: 12 и 74)
    'тысяча', 'двести', 'сорок', 'восемь', 'тысяча', 'триста' → [['тысяча','двести','сорок','восемь'], ['тысяча','триста']] (1248, 1349)
    'две', 'тысячи', 'двадцать', 'четыре' → [['две','тысячи','двадцать','четыре']] (одно число 2024)

    Boundary heuristics:
    Эвристика границ:
    1. unit (1-19) → ten/hundred = граница ("двенадцать | семьдесят")
    2. unit (1-19) → multiplier(единственное, не последний) = граница ("восемь | тысяча триста")
       НО: unit → multiplier(множественное) = НЕ граница ("две тысячи" = 2000)
    3. multiplier → multiplier = граница ("тысяча | миллион")
    4. hundred → multiplier = граница ("сто | тысяча" = 100, 1xxx)
    """
    if not num_words:
        return []

    def _word_type(w):
        if w in ONES and ONES[w] <= 19:
            return 'unit'
        elif w in TENS:
            return 'ten'
        elif w in HUNDREDS:
            return 'hundred'
        elif w in MULTIPLIERS:
            return 'multiplier'
        return 'unknown'

    # Plural multiplier forms require a preceding number: "две тысячи" = 2000.
    # Множественные формы множителей (требуют число перед собой: "две тысячи" = 2000)
    _plural_multipliers = frozenset({
        'тысячи', 'тысяч',
        'миллиона', 'миллионов',
        'миллиарда', 'миллиардов',
    })

    groups = []
    current = [num_words[0]]

    for i in range(1, len(num_words)):
        prev_word = num_words[i - 1].lower()
        curr_word = num_words[i].lower()

        prev_type = _word_type(prev_word)
        curr_type = _word_type(curr_word)

        # Do not split before a fraction denominator.
        # Не разбиваем перед знаменателем дроби
        if curr_word in ORDINALS_DENOM:
            current.append(curr_word)
            continue

        is_boundary = False

        # Boundary 1: unit -> ten/hundred ("двенадцать | семьдесят").
        # Граница 1: unit → ten/hundred ("двенадцать | семьдесят")
        if prev_type == 'unit' and curr_type in ('ten', 'hundred'):
            is_boundary = True
        if prev_type == 'ten' and curr_type == 'ten':
            is_boundary = True

        # Boundary 2: unit -> singular multiplier that is not last = split point.
        # Граница 2: unit → multiplier(единственное, не последний) = граница
        # "восемь | тысяча триста" means two numbers.
        # "восемь | тысяча триста" — два числа
        # BUT "две тысячи" is plural and must not split.
        # НО: "две тысячи" — множественная форма, НЕ граница
        if prev_type == 'unit' and curr_type == 'multiplier':
            if curr_word not in _plural_multipliers and i + 1 < len(num_words):
                is_boundary = True

        # Boundary 3: multiplier -> multiplier ("тысяча | миллион").
        # Граница 3: multiplier → multiplier ("тысяча | миллион")
        if prev_type == 'multiplier' and curr_type == 'multiplier':
            is_boundary = True

        # Boundary 4: hundred -> multiplier ("сто | тысяча").
        # Граница 4: hundred → multiplier ("сто | тысяча")
        # "тысяча сто | тысяча двести" becomes 1100 and 1200.
        # "тысяча сто | тысяча двести" = 1100, 1200
        if prev_type == 'hundred' and curr_type == 'multiplier':
            is_boundary = True
        if prev_type == 'hundred' and curr_type == 'hundred':
            is_boundary = True

        if is_boundary:
            groups.append(current)
            current = []

        current.append(curr_word)

    if current:
        groups.append(current)

    return groups


def _is_already_number(token):
    """Checks whether the token is already numeric digits.
    Проверяет, является ли токен уже числом (цифрами)."""
    if not token:
        return False
    try:
        float(token.replace(',', '.'))
        return True
    except ValueError:
        return False


def _is_single_digit_token(token):
    return token.isdigit() and len(token) == 1


def _try_parse_digit_word_sequence(words):
    """
    Works only for sequences of standalone digits from 0 to 9.
    Работает только для последовательности одиночных цифр 0..9.
    'один два три' -> '123'
    """
    if not words:
        return None

    digits = []
    for word in words:
        w = word.lower()
        if w not in ONES:
            return None
        val = ONES[w]
        if val < 0 or val > 9:
            return None
        digits.append(str(val))

    return ''.join(digits) if digits else None


def _wrap_keyboard_token(value):
    return f"{_KEYBOARD_TOKEN_PREFIX}{value}"


def _is_keyboard_token(token):
    return token.startswith(_KEYBOARD_TOKEN_PREFIX)


def _raw_token(token):
    if token == _SPACE_TOKEN:
        return ' '
    if token == _LIST_BREAK_TOKEN:
        return ''
    if _is_keyboard_token(token):
        return token[len(_KEYBOARD_TOKEN_PREFIX):]
    return token


def _is_identifier_like(token):
    raw = _raw_token(token)
    return bool(raw) and all(ch.isalnum() or ch == '_' for ch in raw)


def _should_glue_tokens(prev, token):
    prev_raw = _raw_token(prev)
    raw = _raw_token(token)

    if not prev_raw or not raw:
        return False

    if _is_keyboard_token(prev) and _is_keyboard_token(token):
        return True

    if _is_keyboard_token(prev) and _is_identifier_like(token):
        return True

    if _is_identifier_like(prev) and _is_keyboard_token(token):
        return True

    if _is_single_digit_token(prev_raw) and _is_single_digit_token(raw):
        return True

    if prev_raw in _MATH_BINARY_OPERATORS or raw in _MATH_BINARY_OPERATORS:
        return False

    return False


def _normalize_eval_expression(expr):
    expr = expr.replace('²', '**2')
    expr = expr.replace('³', '**3')
    expr = expr.replace('^', '**')
    expr = expr.replace(',', '.')
    expr = re.sub(r'√\s*\(', 'sqrt(', expr)
    expr = re.sub(r'√\s*([0-9]+(?:\.[0-9]+)?)', r'sqrt(\1)', expr)
    return expr


def _is_safe_math_ast(node):
    allowed_nodes = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Num,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
        ast.UAdd, ast.USub, ast.Load, ast.Call, ast.Name
    )
    if not isinstance(node, allowed_nodes):
        return False

    for child in ast.iter_child_nodes(node):
        if not _is_safe_math_ast(child):
            return False

    if isinstance(node, ast.Call):
        return isinstance(node.func, ast.Name) and node.func.id == 'sqrt' and len(node.args) == 1

    if isinstance(node, ast.Name):
        return node.id == 'sqrt'

    return True


def _format_math_result(value):
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        text = f"{value:.12f}".rstrip('0').rstrip('.')
        return text.replace('.', ',')
    return str(value)


def _pretty_format_math_expression(expr):
    """
    Makes an expression readable only for actual math.
    Делает выражение читабельным только для настоящей математики:
    It inserts spaces around binary operators while preserving parentheses and powers.
    расставляет пробелы вокруг бинарных операторов, сохраняя скобки и степени.
    """
    expr = expr.strip()
    if not expr:
        return expr

    expr = re.sub(r'\s+', '', expr)
    expr = re.sub(r'(?<!^)(>=|<=|!=|=|\+|-|\*|/|>|<)(?!$)', r' \1 ', expr)
    expr = re.sub(r'\s+', ' ', expr).strip()
    expr = re.sub(r'\(\s+', '(', expr)
    expr = re.sub(r'\s+\)', ')', expr)
    expr = re.sub(r'√\s+', '√', expr)
    return expr


def _try_append_evaluated_result(expr):
    expr = expr.rstrip()
    if not expr.endswith('='):
        return expr

    left = expr[:-1].strip()
    if not left:
        return expr

    # Only pure arithmetic is allowed, with no identifiers except sqrt after normalization.
    # Только чистая арифметика без буквенных идентификаторов, кроме sqrt после замены.
    normalized = _normalize_eval_expression(left)

    try:
        tree = ast.parse(normalized, mode='eval')
    except SyntaxError:
        return expr

    if not _is_safe_math_ast(tree):
        return expr

    try:
        value = eval(compile(tree, '<math_mode>', 'eval'), {'__builtins__': {}}, {'sqrt': lambda x: x ** 0.5})
    except Exception:
        return expr

    pretty_left = _pretty_format_math_expression(left)
    result_text = _format_math_result(value)
    result_text = re.sub(r'^\.(?=\d)', '', result_text)
    return f"{pretty_left} = {result_text}"


def reset_math_buffer():
    global _pending_math_compact
    _pending_math_compact = ""


def _cleanup_plain_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.rstrip('.!?').strip()
    return re.sub(r'(?<=[A-Za-zА-Яа-яЁё0-9])-(?=[A-Za-zА-Яа-яЁё0-9])', ' ', text)


def _is_uppercase_letter_sequence(token):
    return len(token) > 1 and token.isalpha() and token.upper() == token


def _has_explicit_math_context(operator_hits, keyboard_hits, number_hits, non_math_words):
    if operator_hits <= 0:
        return False

    # Pure math/symbolic phrase: "минус", "икс больше нуля", "10 минус 3".
    # Чистая математическая/символьная фраза: "минус", "икс больше нуля", "10 минус 3".
    if non_math_words == 0:
        return True

    # Allow short mixed phrases like "икс плюс один",
    # but not regular speech like "я сейчас скажу минус".
    # Слабый допуск для коротких смешанных фраз вроде "икс плюс один",
    # но не для обычной речи типа "я сейчас скажу минус".
    if (keyboard_hits > 0 or number_hits > 0) and non_math_words <= 1:
        return True

    return False


def _looks_like_math_input(text):
    cleaned_raw = _cleanup_plain_text(text)
    if not cleaned_raw:
        return False

    cleaned = cleaned_raw.lower()
    if (
        '-' in cleaned
        and not re.search(
            r'(?<![A-Za-zА-Яа-яЁё0-9])-(?![A-Za-zА-Яа-яЁё0-9])|(?<=\d)-|-(?=\d)',
            cleaned,
        )
        and not re.search(r'[+*/=<>^√π∞%()\[\]{}]', cleaned)
    ):
        return False

    if re.search(r'[+\-*/=<>^√π∞%()\[\]{}]', cleaned):
        return True

    tokens_raw = cleaned_raw.split()
    tokens = cleaned.split()
    if not tokens:
        return False

    for phrase, _ in MULTI_WORD_OPS:
        if phrase in cleaned:
            return True

    for phrase, _ in KEYBOARD_MULTI_WORDS:
        if phrase in cleaned:
            return True

    operator_hits = 0
    keyboard_hits = 0
    number_hits = 0
    non_math_words = 0

    for token_raw, token in zip(tokens_raw, tokens):
        normalized = token.strip('.,;:!?')
        normalized_raw = token_raw.strip('.,;:!?')
        if not normalized:
            continue

        if normalized in _MATH_HINT_WORDS:
            if normalized in _ALL_CASE_WORDS or normalized in KEYBOARD_WORDS or normalized in LATIN_PHONETIC_WORDS or normalized == 'пробел':
                keyboard_hits += 1
            else:
                operator_hits += 1
            continue

        if _is_already_number(normalized):
            number_hits += 1
            continue

        if normalized in _PASSTHROUGH_SYMBOLS:
            operator_hits += 1
            continue

        embedded_base, embedded_case = _extract_embedded_case_token(normalized)
        if embedded_base is not None and embedded_case is not None:
            keyboard_hits += 1
            continue

        if normalized in KEYBOARD_WORDS:
            keyboard_hits += 1
            continue

        if _is_uppercase_letter_sequence(normalized_raw):
            keyboard_hits += 1
            continue

        if normalized.isascii() and normalized.isalnum():
            if len(normalized) == 1 and normalized.isalpha():
                keyboard_hits += 1
            else:
                operator_hits += 1
            continue

        non_math_words += 1

    if _has_explicit_math_context(operator_hits, keyboard_hits, number_hits, non_math_words):
        return True

    if keyboard_hits > 0 and non_math_words == 0:
        return True

    if number_hits > 0 and non_math_words == 0:
        return True

    if _pending_math_compact and (keyboard_hits > 0 or number_hits > 0) and non_math_words == 0:
        return True

    return False


def _is_letter_token(token):
    raw = _raw_token(token)
    return len(raw) == 1 and raw.isalpha()


def _apply_case_marker(value, marker):
    if marker in _UPPERCASE_WORDS:
        return value.upper()
    return value.lower() if len(value) == 1 and value.isalpha() else value


def _extract_embedded_case_token(token):
    """
    Supports merged forms like 'aбольшая' or 'амбольшая' after STT.
    Поддержка слитных форм вроде 'aбольшая' или 'амбольшая' после STT.
    Returns (base_token, case_word) or (None, None).
    Возвращает (base_token, case_word) или (None, None).
    """
    for marker in tuple(_UPPERCASE_WORDS):
        if token.endswith(marker) and len(token) > len(marker):
            base = token[:-len(marker)]
            if len(base) == 1 and base.isalpha():
                return base, marker
    return None, None


# ═══════════════════════════════════════
#  FORMATTING
#  ФОРМАТИРОВАНИЕ
# ═══════════════════════════════════════

def _format_expression(tokens):
    """Joins tokens into an expression with correct spacing.
    Склеивает токены в выражение с правильными пробелами."""
    if not tokens:
        return ''

    _no_space_before = frozenset({')', ']', '}', ',', ';', ':', '.', '²', '³', '%'})
    _no_space_after = frozenset({'(', '[', '{', '√'})

    result = [_raw_token(tokens[0])]

    for i in range(1, len(tokens)):
        token = tokens[i]
        prev = tokens[i - 1]

        raw = _raw_token(token)
        prev_raw = _raw_token(prev)

        if raw in _no_space_before:
            result.append(raw)
        elif prev_raw in _no_space_after:
            result.append(raw)
        elif _should_glue_tokens(prev, token):
            result.append(raw)
        else:
            result.append(' ')
            result.append(raw)

    return ''.join(result)


def _format_compact(tokens):
    """Compact math-mode output: no spaces except explicit spoken "пробел".
    Плотный режим math mode: без пробелов, кроме явно продиктованного 'пробел'."""
    if not tokens:
        return ''

    parts = []
    for token in tokens:
        raw = _raw_token(token)
        if raw == ' ':
            parts.append(' ')
            continue
        parts.append(raw)
    return ''.join(parts)


# ═══════════════════════════════════════
#  MAIN FUNCTION
#  ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════

def convert_to_math(text):
    """
    Converts dictated text into a mathematical expression.
    Конвертирует надиктованный текст в математическое выражение.

    Returns: a string with the math expression.
    Возвращает: строку с мат. выражением.
    """
    if not text or not text.strip():
        return text
    result = text.lower().strip()

    # Drop STT punctuation; in math mode commas and dots are spoken as words.
    # Убираем пунктуацию от STT (в мат-режиме запятые/точки говорятся словами)
    result = result.rstrip('.!?')
    # Use auto-inserted STT commas only as number separators, without outputting a comma.
    # Автозапятые от STT используем только как разрыв между числами, без вывода запятой.
    result = result.replace(',', f' {_LIST_BREAK_TOKEN} ')

    result = re.sub(r'(?<=[a-zа-яёa-zA-ZА-ЯЁ0-9])-(?=[a-zа-яёa-zA-ZА-ЯЁ0-9])', ' ', result)
    result = re.sub(r'\b([a-zа-яё])\.\s*', r'\1 ', result)

    for phrase, symbol in KEYBOARD_MULTI_WORDS:
        result = result.replace(phrase, f' {_wrap_keyboard_token(symbol)} ')

    for phrase, symbol in MULTI_WORD_OPS:
        result = result.replace(phrase, f' {symbol} ')

    tokens = result.split()
    if not tokens:
        return text

    output = []
    i = 0

    latin_phonetic_count = sum(1 for token in tokens if token in LATIN_PHONETIC_WORDS)

    while i < len(tokens):
        token = tokens[i]
        embedded_base, embedded_case = _extract_embedded_case_token(token)
        if embedded_base is not None:
            tokens[i] = embedded_base
            tokens.insert(i + 1, embedded_case)
            token = tokens[i]

        if _is_keyboard_token(token):
            output.append(token)
            i += 1
            continue

        if token == 'пробел':
            output.append(_SPACE_TOKEN)
            i += 1
            continue

        if token == _LIST_BREAK_TOKEN:
            output.append(_LIST_BREAK_TOKEN)
            i += 1
            continue

        if token in _PASSTHROUGH_SYMBOLS:
            output.append(token)
            i += 1
            continue

        if _is_already_number(token):
            output.append(token)
            i += 1
            continue

        # Latin phonetics are accepted ONLY with an explicit case modifier.
        # Фонетика латиницы — ТОЛЬКО с модификатором регистра
        if token in LATIN_PHONETIC_WORDS:
            if i + 1 < len(tokens):
                marker = tokens[i + 1].lower()
                if marker in _ALL_CASE_WORDS:
                    value = LATIN_PHONETIC_WORDS[token]
                    value = _apply_case_marker(value, marker)
                    i += 2
                    output.append(_wrap_keyboard_token(value))
                    continue
            if latin_phonetic_count >= 2:
                output.append(_wrap_keyboard_token(LATIN_PHONETIC_WORDS[token]))
                i += 1
                continue
            # Without a modifier, this is not Latin phonetics; pass the token through.
            # Без модификатора — не латиница, передаём дальше как есть
            output.append(token)
            i += 1
            continue

        if token in _ALL_CASE_WORDS and i + 1 < len(tokens):
            next_token = tokens[i + 1].lower()
            if next_token in KEYBOARD_WORDS:
                value = KEYBOARD_WORDS[next_token]
                if _is_letter_token(value):
                    output.append(_wrap_keyboard_token(_apply_case_marker(value, token)))
                    i += 2
                    continue
            if next_token in LATIN_PHONETIC_WORDS:
                value = _apply_case_marker(LATIN_PHONETIC_WORDS[next_token], token)
                output.append(_wrap_keyboard_token(value))
                i += 2
                continue
            if next_token.isascii() and len(next_token) == 1 and next_token.isalpha():
                output.append(_wrap_keyboard_token(_apply_case_marker(next_token, token)))
                i += 2
                continue

        if token in KEYBOARD_WORDS:
            value = KEYBOARD_WORDS[token]
            if _is_letter_token(value) and i + 1 < len(tokens):
                marker = tokens[i + 1].lower()
                if marker in _ALL_CASE_WORDS:
                    value = _apply_case_marker(value, marker)
                    i += 1
            output.append(_wrap_keyboard_token(value))
            i += 1
            continue

        if _is_uppercase_letter_sequence(token):
            output.append(_wrap_keyboard_token(token.lower()))
            i += 1
            continue

        if token.isascii() and token.isalnum():
            value = token
            if len(token) == 1 and token.isalpha() and i + 1 < len(tokens):
                marker = tokens[i + 1].lower()
                if marker in _ALL_CASE_WORDS:
                    value = _apply_case_marker(value, marker)
                    i += 1
            output.append(_wrap_keyboard_token(value))
            i += 1
            continue

        if token in SINGLE_OPS:
            output.append(SINGLE_OPS[token])
            i += 1
            continue

        # Numeral sequence: collect words and split by comma boundaries.
        # Числительное — собираем последовательность, разбивая по запятым
        if _is_number_word(token):
            num_words = []
            j = i
            while j < len(tokens) and (_is_number_word(tokens[j]) or tokens[j] == _LIST_BREAK_TOKEN):
                num_words.append(tokens[j])
                j += 1

            # First split by commas (_LIST_BREAK_TOKEN).
            # Сначала разбиваем по запятым (_LIST_BREAK_TOKEN)
            comma_groups = []
            current_group = []
            for w in num_words:
                if w == _LIST_BREAK_TOKEN:
                    if current_group:
                        comma_groups.append(current_group)
                        current_group = []
                else:
                    current_group.append(w)
            if current_group:
                comma_groups.append(current_group)

            # Then split each comma-group into separate numbers
            # using the unit→ten/hundred boundary heuristic.
            # Затем каждую запятую-группу разбиваем на отдельные числа
            # по эвристике (unit→ten/hundred = граница)
            all_number_groups = []
            for cg in comma_groups:
                sub_groups = _split_number_group_into_numbers(cg)
                if sub_groups:
                    all_number_groups.extend(sub_groups)
                elif cg:
                    all_number_groups.append(cg)

            if not all_number_groups:
                i = j
                continue

            digit_sequence = _try_parse_digit_word_sequence(num_words)
            if digit_sequence is not None:
                output.append(digit_sequence)
                i = j
                continue

            has_celyx = False
            if j < len(tokens) and tokens[j].lower() in ('целых', 'целая', 'целые'):
                has_celyx = True
                j += 1

            if has_celyx:
                # MIXED FRACTION or DECIMAL: "три целых ..."
                # СМЕШАННАЯ ДРОБЬ или ДЕСЯТИЧНАЯ: «три целых ...»
                last_group = all_number_groups[-1]
                denom, denom_count = _parse_denominator_from_tokens(last_group)
                if denom is not None:
                    whole_parts = all_number_groups[:-1]
                    whole = _parse_number_sequence_from_list(whole_parts) if whole_parts else 0
                    frac_words = last_group[:len(last_group) - denom_count]
                    frac_num = _parse_number_sequence_from_list(frac_words) if frac_words else 0
                    ordinal_val = ORDINALS_DENOM[last_group[-1].lower()]

                    if ordinal_val in (10, 100, 1000, 10000, 100000, 1000000):
                        dec_str = str(frac_num).zfill(len(str(ordinal_val)) - 1)
                        output.append(f'{whole},{dec_str}')
                    else:
                        output.append(f'{whole} {frac_num}/{ordinal_val}')
                    i = j + denom_count
                else:
                    number = _parse_number_sequence_from_list(all_number_groups)
                    output.append(str(number))
                    i = j
                continue

            # Without "целых", look for a fraction in the last group.
            # БЕЗ «целых» — ищем дробь в последней группе
            found_fraction = False
            last_group = all_number_groups[-1]
            if len(last_group) >= 1:
                for split in range(1, len(last_group) + 1):
                    denom_val, denom_count = _parse_denominator_from_tokens(last_group[split:])
                    if denom_val is not None:
                        numerator = _parse_number_sequence_from_list([last_group[:split]])
                        prefix = _parse_number_sequence_from_list(all_number_groups[:-1]) if len(all_number_groups) > 1 else 0
                        full_numerator = prefix * denom_val + numerator if prefix else numerator
                        output.append(f'{full_numerator}/{denom_val}')
                        i = j
                        found_fraction = True
                        break

            if found_fraction:
                continue

            # Plain numbers: parse each number separately and concatenate without spaces.
            # Обычные числа — каждое число отдельно, склеиваем без пробелов
            number_strs = []
            for group in all_number_groups:
                group_digit_sequence = _try_parse_digit_word_sequence(group)
                if group_digit_sequence is not None:
                    number_strs.append(group_digit_sequence)
                    continue
                number = _parse_number_sequence_from_list([group])
                number_strs.append(str(number))
            output.append(''.join(number_strs))
            i = j
            continue

        # Unknown word: keep it as-is.
        # Неизвестное слово — оставляем как есть
        output.append(token)
        i += 1

    formatted = _format_compact(output)
    if formatted and not formatted.strip():
        return formatted
    return _try_append_evaluated_result(formatted)


def process_math_input(text):
    """
    Accumulative math-mode processing.
    Накопительный режим math mode.
    Returns:
    Возвращает:
    - text: what to insert
    - text: что вставлять
    - replace_left_chars: how many characters to delete to the left
    - replace_left_chars: сколько символов слева удалить
    - smart_spacing: whether regular smart spacing should be applied
    - smart_spacing: применять ли обычный умный пробел
    """
    global _pending_math_compact

    normalized_text = re.sub(r'\s+', ' ', text).strip()
    plain_text = _cleanup_plain_text(text)
    if plain_text.lower() == "пробел":
        _pending_math_compact = ""
        return {"text": " ", "replace_left_chars": 0, "smart_spacing": False}

    if not _looks_like_math_input(plain_text):
        # Plain text does NOT reset the buffer, so the user can
        # come back to the expression later and say "равно".
        # Обычный текст — НЕ сбрасываем буфер, чтобы потом можно было
        # вернуться к выражению и сказать "равно"
        return {"text": normalized_text, "replace_left_chars": 0, "smart_spacing": True}

    lower_text = text.lower()
    has_equal_marker = ('=' in lower_text) or ('равно' in lower_text) or ('равняется' in lower_text)

    compact = convert_to_math(text)

    # If compact output contains math operators (not just "="),
    # this is the START of a new example, so drop the old buffer.
    # IMPORTANT: a hyphen inside words ("какой-то") must not count as an operator.
    # A real "-" operator stands alone or touches digits at the boundary.
    # Если в компактном выводе есть математические операторы (но не просто "=") —
    # это НАЧАЛО нового примера. Сбрасываем старый буфер.
    # ВАЖНО: дефис в словах ("какой-то") не должен считаться оператором.
    # Настоящий оператор "-" стоит отдельно (с пробелами или на границе с цифрой).
    _has_math_ops = bool(re.search(r'[+*/^><]|!=|(?<!\w)-(?!\w)|-\d|\d-', compact))
    if _has_math_ops and _pending_math_compact:
        _pending_math_compact = ""

    if has_equal_marker:
        text_before_equal = re.sub(r'=', ' ', text, flags=re.IGNORECASE)
        text_before_equal = re.sub(r'\bравно\b|\bравняется\b', ' ', text_before_equal, flags=re.IGNORECASE)
        text_before_equal = _cleanup_plain_text(text_before_equal)

        had_pending = bool(_pending_math_compact)

        if text_before_equal.strip():
            compact_before_equal = convert_to_math(text_before_equal).strip()
            _before_has_ops = bool(re.search(r'[+*/^><]|!=|(?<!\w)-(?!\w)|-\d|\d-', compact_before_equal))
            _word_count = len(text_before_equal.split())

            if not _before_has_ops and _word_count > 3:
                _pending_math_compact = ""
                return {"text": normalized_text, "replace_left_chars": 0, "smart_spacing": True}

            expr = _pending_math_compact + compact_before_equal + "="
        else:
            compact_before_equal = ""
            expr = _pending_math_compact + "="

        evaluated = _try_append_evaluated_result(expr)
        if evaluated != expr:
            if had_pending:
                # The buffer came from previous utterances,
                # so replace_left covers the whole buffer plus the current expression if present.
                # Буфер был накоплен из предыдущих высказываний —
                # replace_left покрывает весь буфер + текущее выражение если есть
                replace = len(_pending_math_compact) + len(compact_before_equal)
            else:
                # The buffer was empty: either "равно" came as a standalone utterance
                # (then compact_before_equal='', replace=0), or expression+equals arrived
                # in one utterance, so nothing has been inserted yet and replace=0.
                # Буфер был пуст: либо «равно» отдельным высказыванием (тогда
                # compact_before_equal='', replace=0), либо выражение+равно пришли
                # вместе одним высказыванием — текст ещё не вставлен, replace=0
                replace = 0
            _pending_math_compact = ""
            return {"text": evaluated, "replace_left_chars": replace, "smart_spacing": False}

        _pending_math_compact = ""
        return {"text": "=", "replace_left_chars": 0, "smart_spacing": False}

    if compact == "=":
        _pending_math_compact = ""
        return {"text": "=", "replace_left_chars": 0, "smart_spacing": False}

    if compact.endswith("="):
        _pending_math_compact = ""
        return {"text": compact, "replace_left_chars": 0, "smart_spacing": False}

    # Add to the buffer ONLY when there are real math operators.
    # Plain text must not pollute the buffer, even if _looks_like_math_input
    # returned True because of a hyphen.
    # Добавляем в буфер ТОЛЬКО если есть настоящие математические операторы.
    # Обычный текст (даже если _looks_like_math_input вернул True из-за дефиса)
    # не должен загрязнять буфер.
    if _has_math_ops:
        _pending_math_compact += compact
        return {"text": compact, "replace_left_chars": 0, "smart_spacing": False}

    # No operators means this is not a math expression.
    # Leave the buffer intact so the user can still say "равно" for the previous expression.
    # Нет операторов — это не математическое выражение.
    # Буфер НЕ трогаем (чтобы потом можно было сказать "равно" к предыдущему выражению).
    return {"text": compact, "replace_left_chars": 0, "smart_spacing": False}
