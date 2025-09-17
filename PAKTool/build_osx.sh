#!/bin/bash
set -e

APP_NAME="paktool"
APP_VERSION="0.0.3"
NET_VERSION="net9.0"

echo "Publishing for OSX Apple Silicon (osx-arm64)..."
dotnet publish -c Release -r osx-arm64 --self-contained true /p:PublishSingleFile=true
echo "OSX Apple Silicon binary is at: bin/Release/${NET_VERSION}/osx-arm64/publish/"

echo "Creating OSX Apple Silicon archive..."
pushd bin/Release/${NET_VERSION}/osx-arm64/publish/
    zip -r -j "../../../../../${APP_NAME}-${APP_VERSION}-osx-arm64.zip" .
popd

echo "Publishing for OSX Intel (osx-x64)..."
dotnet publish -c Release -r osx-x64 --self-contained true /p:PublishSingleFile=true
echo "OSX Intel binary is at: bin/Release/${NET_VERSION}/osx-x64/publish/"

echo "Creating OSX Intel archive..."
pushd bin/Release/${NET_VERSION}/osx-x64/publish/
    zip -r -j "../../../../../${APP_NAME}-${APP_VERSION}-osx-x64.zip" .
popd

echo "Done!"