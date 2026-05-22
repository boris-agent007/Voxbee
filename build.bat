@echo off
@REM Copyright (C) 2026 Boris Shkylnikov
@REM SPDX-License-Identifier: GPL-3.0-or-later
@REM
@REM This file is part of Vox Bee.
@REM
@REM Vox Bee is free software: you can redistribute it and/or modify
@REM it under the terms of the GNU General Public License as published by
@REM the Free Software Foundation, version 3.
@REM
@REM Vox Bee is distributed in the hope that it will be useful,
@REM but WITHOUT ANY WARRANTY; without even the implied warranty of
@REM MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
@REM GNU General Public License for more details.
@REM
@REM You should have received a copy of the GNU General Public License
@REM along with Vox Bee. If not, see <https://www.gnu.org/licenses/>.

chcp 65001 >nul
echo.
echo ============================================
echo   Vox Bee - Сборка
echo ============================================
echo.

echo [1/4] Очистка...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
rmdir /s /q installer_output 2>nul
echo   OK

echo.
echo [2/4] PyInstaller...
pyinstaller vox_bee.spec --noconfirm
if errorlevel 1 (
    echo   ОШИБКА: PyInstaller
    pause
    exit /b 1
)
echo   OK

echo.
echo [3/4] Подготовка dist...

REM Создаём пустые папки
mkdir "dist\VoxBee\bin\cpu" 2>nul
mkdir "dist\VoxBee\bin\gpu" 2>nul
mkdir "dist\VoxBee\models" 2>nul
mkdir "dist\VoxBee\scripts" 2>nul
mkdir "dist\VoxBee\logs" 2>nul

REM Удаляем тяжёлые файлы если они попали в dist
del /q "dist\VoxBee\bin\cpu\*.exe" 2>nul
del /q "dist\VoxBee\bin\cpu\*.dll" 2>nul
del /q "dist\VoxBee\bin\gpu\*.exe" 2>nul
del /q "dist\VoxBee\bin\gpu\*.dll" 2>nul
del /q "dist\VoxBee\models\*.bin" 2>nul

REM README для моделей
echo Скачайте модели с https://huggingface.co/ggerganov/whisper.cpp/tree/main > "dist\VoxBee\models\README.txt"
echo Рекомендация: ggml-small.bin для начала >> "dist\VoxBee\VoxBee\README.txt"
echo Положите .bin файлы в эту папку >> "dist\VoxBee\models\README.txt"

REM README для bin
echo Положите бинарники whisper.cpp (CPU) в эту папку > "dist\VoxBee\bin\cpu\README.txt"
echo Положите бинарники whisper.cpp (GPU) в эту папку > "dist\VoxBee\bin\gpu\README.txt"


echo   OK

echo.
echo [4/4] Установщик...
where iscc >nul 2>&1
if errorlevel 1 (
    echo   iscc не найден - пропуск
    goto :done
)
iscc installer.iss
if errorlevel 1 (
    echo   ОШИБКА: Inno Setup
    pause
    exit /b 1
)
echo   Установщик создан!

:done
echo.
echo ============================================
echo   ГОТОВО!
echo   exe:       dist\VoxBee\VoxBee.exe
echo   installer: installer_output\VoxBee_Setup_1.0.0.exe
echo ============================================
echo.
echo   После установки пользователь должен сам добавить:
echo   - bin\cpu\  - бинарники whisper.cpp CPU
echo   - bin\gpu\  - бинарники whisper.cpp GPU
echo   - models\   - модели .bin
echo ============================================
pause
