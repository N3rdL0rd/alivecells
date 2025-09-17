#!/bin/bash
set -e

APP_NAME="paktool"
APP_VERSION="0.0.3"

echo "Publishing for Windows (win-x64)..."
dotnet publish -c Release --runtime win-x64 --self-contained false
echo "Windows binaries are at: bin/Release/net9.0/win-x64/publish/"

echo "Creating Windows archive..."
pushd bin/Release/net9.0/win-x64/publish/
    zip -r "../../../../../${APP_NAME}-${APP_VERSION}-win-x64.zip" .
popd

echo "Done!"