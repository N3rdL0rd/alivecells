@echo off
setlocal

set "APP_NAME=paktool"
set "APP_VERSION=0.0.4"
set "SCRIPT_DIR=%~dp0"
set "PUBLISH_DIR=%SCRIPT_DIR%bin\Release\net9.0\win-x64\publish"
set "ARCHIVE_PATH=%SCRIPT_DIR%%APP_NAME%-%APP_VERSION%-win-x64.zip"

echo Publishing for Windows (win-x64)...
dotnet publish "%SCRIPT_DIR%PAKTool.csproj" -c Release --runtime win-x64 --self-contained false
if errorlevel 1 goto :error

echo Windows binaries are at: %PUBLISH_DIR%

if exist "%ARCHIVE_PATH%" del /f /q "%ARCHIVE_PATH%"

echo Creating Windows archive...
powershell -NoProfile -Command "Compress-Archive -Path '%PUBLISH_DIR%\*' -DestinationPath '%ARCHIVE_PATH%'"
if errorlevel 1 goto :error

echo Done!
exit /b 0

:error
echo Build failed.
exit /b 1
