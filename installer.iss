; Copyright (C) 2026 Boris Shkylnikov
; SPDX-License-Identifier: GPL-3.0-or-later
;
; This file is part of Vox Bee.
;
; Vox Bee is free software: you can redistribute it and/or modify
; it under the terms of the GNU General Public License as published by
; the Free Software Foundation, version 3.
;
; Vox Bee is distributed in the hope that it will be useful,
; but WITHOUT ANY WARRANTY; without even the implied warranty of
; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
; GNU General Public License for more details.
;
; You should have received a copy of the GNU General Public License
; along with Vox Bee. If not, see <https://www.gnu.org/licenses/>.
;; Inno Setup-скрипт для Vox Bee.
; Inno Setup script for Vox Bee.

; Компиляция: ISCC.exe installer.iss
; Build: ISCC.exe installer.iss

#define MyAppName "Vox Bee"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Vox Bee"
#define MyAppExeName "VoxBee.exe"
#define MyAppURL "https://github.com/your-repo/vox-bee"


; Redistributable VC++ добавляется только если `vc_redist.x64.exe` лежит в корне проекта.
; The VC++ redistributable is included only if `vc_redist.x64.exe` is present in the project root.
#ifexist "vc_redist.x64.exe"
  #define VCRedistIncluded
#endif

[Setup]
; Уникальный идентификатор приложения. После релиза менять нельзя, иначе сломаются обновления и деинсталляция.
; Unique application identifier. Do not change it after release or updates and uninstall may break.
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\voxbee.ico,0
UninstallDisplayName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=VoxBee_Setup_{#MyAppVersion}
SetupIconFile=src\voxbee.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Установка идёт в Program Files, поэтому нужны права администратора.
; Installation targets Program Files, so administrator privileges are required.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
AlwaysRestart=no
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.0.1.0
VersionInfoCompany=Vox Bee
VersionInfoDescription=Vox Bee
VersionInfoProductName=Vox Bee
VersionInfoProductVersion=1.0.1
VersionInfoCopyright=Copyright (C) 2026 Boris Shkylnikov

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: unchecked
Name: "autostart"; Description: "Запускать при старте Windows"; GroupDescription: "Дополнительно:"; Flags: unchecked
#ifdef VCRedistIncluded
Name: "vcredist_silent"; Description: "Тихая установка (рекомендуется)"; GroupDescription: "Microsoft Visual C++ Runtime:"; Flags: exclusive; Check: VCRedistNeedsInstall
Name: "vcredist_normal"; Description: "Обычная установка (с диалоговыми окнами)"; GroupDescription: "Microsoft Visual C++ Runtime:"; Flags: exclusive unchecked; Check: VCRedistNeedsInstall
#endif

[Files]
; Redistributable VC++ кладётся во временную папку установщика и запускается из неё.
; The VC++ redistributable is copied to the installer's temporary directory and launched from there.
#ifdef VCRedistIncluded
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif
Source: "dist\VoxBee\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "src\voxbee.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\voxbee_off.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\voxbee_recording.ico"; DestDir: "{app}"; Flags: ignoreversion


[Dirs]
; Эти каталоги нужны приложению и должны оставаться доступными на запись обычному пользователю.
; These directories are required by the app and must remain writable for a regular user.
Name: "{app}\models"; Permissions: users-modify
Name: "{app}\bin"; Permissions: users-modify
Name: "{app}\bin\cpu"; Permissions: users-modify
Name: "{app}\bin\gpu"; Permissions: users-modify
Name: "{app}\scripts"; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\voxbee.ico"; IconIndex: 0
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\voxbee.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\voxbee.ico"; IconIndex: 0; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VoxBee"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
#ifdef VCRedistIncluded
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Установка Microsoft Visual C++ Runtime..."; Flags: waituntilterminated; Tasks: vcredist_silent
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /norestart"; StatusMsg: "Установка Microsoft Visual C++ Runtime..."; Flags: waituntilterminated; Tasks: vcredist_normal
#endif
; Обновляем системный кэш иконок, чтобы новые иконки появились сразу после установки.
; Refresh the system icon cache so the new icons appear immediately after installation.
Filename: "ie4uinit.exe"; Parameters: "-show"; Flags: runhidden waituntilterminated; StatusMsg: "Обновление иконок..."
Filename: "{cmd}"; Parameters: "/c del /f /a ""%LocalAppData%\IconCache.db"" 2>nul & del /f /s /a ""%LocalAppData%\Microsoft\Windows\Explorer\iconcache_*.db"" 2>nul"; Flags: runhidden waituntilterminated; StatusMsg: "Очистка кэша..."
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
; Перед удалением принудительно останавливаем приложение, чтобы освободить файлы.
; Force-stop the application before uninstall so its files can be removed.
Filename: "{cmd}"; Parameters: "/c taskkill /f /im {#MyAppExeName} 2>nul"; Flags: runhidden waituntilterminated; RunOnceId: "KillApp"
Filename: "{cmd}"; Parameters: "/c timeout /t 2 /nobreak >nul"; Flags: runhidden waituntilterminated; RunOnceId: "WaitKill"
Filename: "ie4uinit.exe"; Parameters: "-show"; Flags: runhidden; RunOnceId: "RefreshIcons"

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\VoxBee"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\commands.json"
Type: files; Name: "{app}\aliases.json"
Type: files; Name: "{app}\scripts.json"
Type: files; Name: "{app}\user_dictionary.json"
Type: filesandordirs; Name: "{app}\scripts"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\*.tmp"

[Code]
var
  FilesPage: TWizardPage;
  edtModels, edtCpu, edtGpu: TEdit;
  DeleteUserDataCheckbox: TNewCheckBox;

function VCRedistNeedsInstall: Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
    Result := (Installed = 0);
end;  

procedure BrowseForDir(Edit: TEdit; const Prompt: String);
var
  Dir: String;
begin
  Dir := Edit.Text;
  if Dir = '' then
    Dir := ExpandConstant('{src}');
  if BrowseForFolder(Prompt, Dir, False) then
    Edit.Text := Dir;
end;

procedure BrowseModelsClick(Sender: TObject);
begin
  BrowseForDir(edtModels, 'Выберите папку с моделями:');
end;

procedure BrowseCpuClick(Sender: TObject);
begin
  BrowseForDir(edtCpu, 'Выберите папку CPU:');
end;

procedure BrowseGpuClick(Sender: TObject);
begin
  BrowseForDir(edtGpu, 'Выберите папку GPU:');
end;

procedure InitializeWizard;
var
  lblModels, lblCpu, lblGpu, lblHint: TNewStaticText;
  SetupDir, AutoModels, AutoCpu, AutoGpu: String;
  btnModels, btnCpu, btnGpu: TNewButton;
  RowHeight, BtnWidth, EditWidth: Integer;
begin
  FilesPage := CreateCustomPage(wpSelectDir,
    'Расположение файлов',
    'Укажите папки с моделями и исполняемыми файлами whisper.cpp (необязательно).');

  // Автоматически подставляем каталоги, если они лежат рядом с инсталлятором.
  // Auto-fill directories when they are located next to the installer.
  SetupDir := ExtractFilePath(ExpandConstant('{srcexe}'));
  AutoModels := SetupDir + 'models';
  AutoCpu := SetupDir + 'cpu';
  AutoGpu := SetupDir + 'gpu'; 

  RowHeight := 90;
  BtnWidth := 110;
  EditWidth := FilesPage.SurfaceWidth - BtnWidth - 15;

  lblModels := TNewStaticText.Create(FilesPage);
  lblModels.Parent := FilesPage.Surface;
  lblModels.Top := 0;
  lblModels.Left := 0;
  lblModels.Width := FilesPage.SurfaceWidth;
  lblModels.AutoSize := False;
  lblModels.WordWrap := True;
  lblModels.Height := 35;
  lblModels.Caption := 'Папка с моделями распознавания (файлы .bin):';
  lblModels.Font.Style := [fsBold];

  edtModels := TEdit.Create(FilesPage);
  edtModels.Parent := FilesPage.Surface;
  edtModels.Top := 40;
  edtModels.Left := 0;
  edtModels.Width := EditWidth;
  if DirExists(AutoModels) then
    edtModels.Text := AutoModels
  else
    edtModels.Text := '';

  btnModels := TNewButton.Create(FilesPage);
  btnModels.Parent := FilesPage.Surface;
  btnModels.Top := edtModels.Top - 2;
  btnModels.Left := EditWidth + 10;
  btnModels.Width := BtnWidth;
  btnModels.Height := edtModels.Height;
  btnModels.Caption := 'Обзор...';
  btnModels.OnClick := @BrowseModelsClick;

  lblCpu := TNewStaticText.Create(FilesPage);
  lblCpu.Parent := FilesPage.Surface;
  lblCpu.Top := RowHeight;
  lblCpu.Left := 0;
  lblCpu.Width := FilesPage.SurfaceWidth;
  lblCpu.AutoSize := False;
  lblCpu.WordWrap := True;
  lblCpu.Height := 35;
  lblCpu.Caption := 'Папка с исполняемыми файлами Whisper CPU (whisper-cli.exe и DLL):';
  lblCpu.Font.Style := [fsBold];

  edtCpu := TEdit.Create(FilesPage);
  edtCpu.Parent := FilesPage.Surface;
  edtCpu.Top := RowHeight + 40;
  edtCpu.Left := 0;
  edtCpu.Width := EditWidth;
  if DirExists(AutoCpu) then
    edtCpu.Text := AutoCpu
  else
    edtCpu.Text := '';

  btnCpu := TNewButton.Create(FilesPage);
  btnCpu.Parent := FilesPage.Surface;
  btnCpu.Top := edtCpu.Top - 2;
  btnCpu.Left := EditWidth + 10;
  btnCpu.Width := BtnWidth;
  btnCpu.Height := edtCpu.Height;
  btnCpu.Caption := 'Обзор...';
  btnCpu.OnClick := @BrowseCpuClick;

  lblGpu := TNewStaticText.Create(FilesPage);
  lblGpu.Parent := FilesPage.Surface;
  lblGpu.Top := RowHeight * 2;
  lblGpu.Left := 0;
  lblGpu.Width := FilesPage.SurfaceWidth;
  lblGpu.AutoSize := False;
  lblGpu.WordWrap := True;
  lblGpu.Height := 35;
  lblGpu.Caption := 'Папка с исполняемыми файлами Whisper GPU/CUDA (whisper-cli.exe и DLL):';
  lblGpu.Font.Style := [fsBold];

  edtGpu := TEdit.Create(FilesPage);
  edtGpu.Parent := FilesPage.Surface;
  edtGpu.Top := RowHeight * 2 + 40;
  edtGpu.Left := 0;
  edtGpu.Width := EditWidth;
  if DirExists(AutoGpu) then
    edtGpu.Text := AutoGpu
  else
    edtGpu.Text := '';

  btnGpu := TNewButton.Create(FilesPage);
  btnGpu.Parent := FilesPage.Surface;
  btnGpu.Top := edtGpu.Top - 2;
  btnGpu.Left := EditWidth + 10;
  btnGpu.Width := BtnWidth;
  btnGpu.Height := edtGpu.Height;
  btnGpu.Caption := 'Обзор...';
  btnGpu.OnClick := @BrowseGpuClick;

  lblHint := TNewStaticText.Create(FilesPage);
  lblHint.Parent := FilesPage.Surface;
  lblHint.Top := RowHeight * 3 + 10;
  lblHint.Left := 0;
  lblHint.Width := FilesPage.SurfaceWidth;
  lblHint.AutoSize := True;
  lblHint.WordWrap := True;
  lblHint.Top := edtGpu.Top + 50;
  lblHint.Caption := 'Все поля необязательные. Папки рядом с установщиком обнаруживаются автоматически. Можно изменить или оставить пустыми.';
  lblHint.Font.Color := clGray;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = FilesPage.ID then
  begin
    if (edtModels.Text <> '') and not DirExists(edtModels.Text) then
    begin
      MsgBox('Папка с моделями не найдена:' + #13#10 + edtModels.Text, mbError, MB_OK);
      Result := False;
      Exit;
    end;

    if (edtCpu.Text <> '') and not DirExists(edtCpu.Text) then
    begin
      MsgBox('Папка CPU не найдена:' + #13#10 + edtCpu.Text, mbError, MB_OK);
      Result := False;
      Exit;
    end;

    if (edtGpu.Text <> '') and not DirExists(edtGpu.Text) then
    begin
      MsgBox('Папка GPU не найдена:' + #13#10 + edtGpu.Text, mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

procedure DirectoryCopy(SourcePath, DestPath: String);
var
  FindRec: TFindRec;
  SrcFile, DstFile: String;
begin
  if not ForceDirectories(DestPath) then Exit;

  if FindFirst(SourcePath + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          SrcFile := SourcePath + '\' + FindRec.Name;
          DstFile := DestPath + '\' + FindRec.Name;
          if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
            DirectoryCopy(SrcFile, DstFile)
          else
            FileCopy(SrcFile, DstFile, False);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, OldExe, OldDat, OldMsg: String;
  NewExe, NewDat, NewMsg: String;
  RegKey, UninstStr: String;
begin
  if CurStep = ssPostInstall then
  begin
    if (edtModels.Text <> '') and DirExists(edtModels.Text) then
      DirectoryCopy(edtModels.Text, ExpandConstant('{app}\models'));
    if (edtCpu.Text <> '') and DirExists(edtCpu.Text) then
      DirectoryCopy(edtCpu.Text, ExpandConstant('{app}\bin\cpu'));
    if (edtGpu.Text <> '') and DirExists(edtGpu.Text) then
      DirectoryCopy(edtGpu.Text, ExpandConstant('{app}\bin\gpu'));

    // Переименовываем стандартные файлы деинсталлятора, чтобы пользователь видел понятные имена.
    // Rename the default uninstaller files so the user sees readable names.
    AppDir := ExpandConstant('{app}');
    OldExe := AppDir + '\unins000.exe';
    OldDat := AppDir + '\unins000.dat';
    OldMsg := AppDir + '\unins000.msg';
    NewExe := AppDir + '\VoxBeeUninstall.exe';
    NewDat := AppDir + '\VoxBeeUninstall.dat';
    NewMsg := AppDir + '\VoxBeeUninstall.msg';

    if FileExists(OldExe) then RenameFile(OldExe, NewExe);
    if FileExists(OldDat) then RenameFile(OldDat, NewDat);
    if FileExists(OldMsg) then RenameFile(OldMsg, NewMsg);

    // Обновляем записи в реестре, чтобы Windows запускал переименованный деинсталлятор.
    // Update registry entries so Windows invokes the renamed uninstaller.
    RegKey := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1');
    if RegQueryStringValue(HKLM, RegKey, 'UninstallString', UninstStr) then
    begin
      RegWriteStringValue(HKLM, RegKey, 'UninstallString', '"' + NewExe + '"');
      RegWriteStringValue(HKLM, RegKey, 'QuietUninstallString', '"' + NewExe + '" /SILENT');
    end
    else if RegQueryStringValue(HKCU, RegKey, 'UninstallString', UninstStr) then
    begin
      RegWriteStringValue(HKCU, RegKey, 'UninstallString', '"' + NewExe + '"');
      RegWriteStringValue(HKCU, RegKey, 'QuietUninstallString', '"' + NewExe + '" /SILENT');
    end;
  end;
end;
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataPath: String;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Удаляем автозапуск вручную на случай, если запись сохранилась вне стандартного сценария.
    // Remove autorun explicitly in case the entry survived outside the standard uninstall flow.
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'VoxBee');
    
    // Пользовательские данные удаляем только по явному подтверждению.
    // User data is removed only after explicit confirmation.
    if MsgBox('Удалить пользовательские настройки и данные?' + #13#10 + #13#10 +
              '(конфигурация, словари, скрипты, логи)', mbConfirmation, MB_YESNO) = IDYES then
    begin
      AppDataPath := ExpandConstant('{userappdata}\VoxBee');
      if DirExists(AppDataPath) then
      begin
        DelTree(AppDataPath, True, True, True);
      end;
    end;
  end;
  
  if CurUninstallStep = usPostUninstall then
  begin
    // После удаления чистим каталог установки от оставшегося мусора.
    // After uninstall, clean the installation directory from leftover files.
    DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;

function InitializeUninstall(): Boolean;
var
  iResultCode: Integer;
begin
  Result := True;
  // При запуске деинсталлятора заранее закрываем приложение, если оно ещё работает.
  // Close the app before uninstall starts if it is still running.
  Exec('taskkill', '/f /im VoxBee.exe', '', SW_HIDE, ewWaitUntilTerminated, iResultCode);
end;

