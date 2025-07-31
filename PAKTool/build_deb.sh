#!/bin/bash
set -e

APP_NAME="paktool"
APP_VERSION="0.0.2"

echo "Publishing .NET application..."
dotnet publish -c Release --runtime linux-x64 --self-contained false

# --- DEB Build ---
echo "Creating DEB package structure..."
DEB_DIR="${APP_NAME}_${APP_VERSION}_amd64"
rm -rf "${DEB_DIR}" # Clean up any previous attempt
mkdir -p "${DEB_DIR}/usr/lib/${APP_NAME}"
mkdir -p "${DEB_DIR}/usr/bin"
mkdir -p "${DEB_DIR}/DEBIAN"

echo "Copying application files..."
cp -r bin/Release/net9.0/linux-x64/publish/* "${DEB_DIR}/usr/lib/${APP_NAME}/"

echo "Creating control file..."
cat << EOF > "${DEB_DIR}/DEBIAN/control"
Package: ${APP_NAME}
Version: ${APP_VERSION}
Architecture: amd64
Maintainer: N3rdL0rd <n3rdl0rd@proton.me>
Depends: dotnet-runtime-9.0
Description: A tool for expanding and creating Dead Cells PAK archives.
 A command-line tool for expanding and creating PAK resource archives for the
 game Dead Cells. This version has been recompiled from decompiled sources to
 run natively on modern .NET and Linux. Now with v1 PAK support <v35!
EOF

echo "Creating executable script..."
cat << EOF > "${DEB_DIR}/usr/bin/${APP_NAME}"
#!/bin/bash
exec /usr/lib/${APP_NAME}/PAKTool "\$@"
EOF

chmod 755 "${DEB_DIR}/usr/bin/${APP_NAME}"

echo "Building DEB package..."
dpkg-deb --build --root-owner-group "${DEB_DIR}"

echo "Done! DEB should be at: ${DEB_DIR}.deb"