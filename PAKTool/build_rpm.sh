#!/bin/bash

APP_NAME="paktool"
APP_VERSION="0.0.2"

echo "Publishing .NET application..."
dotnet publish -c Release --runtime linux-x64 --self-contained false

echo "Entering publish directory..."
pushd bin/Release/net9.0/linux-x64/publish/
    echo "Creating source tarball..."
    tar -czvf "${APP_NAME}-${APP_VERSION}.tar.gz" .
        
    echo "Moving tarball to rpmbuild/SOURCES..."
    mv "${APP_NAME}-${APP_VERSION}.tar.gz" ~/rpmbuild/SOURCES/
popd
cp ./paktool.spec ~/rpmbuild/SPECS/paktool.spec
rpmbuild -ba ~/rpmbuild/SPECS/paktool.spec
echo "Done! RPM should be at: ~/rpmbuild/RPMS/x86_64/paktool-*.*.x86_64.rpm"