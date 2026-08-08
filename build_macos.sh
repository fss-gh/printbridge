#!/bin/bash
# Build PrintBridge for macOS (.app bundle)
# Run from print-agent/ directory

set -e

echo "=== PrintBridge — macOS Build ==="

# 0. Clean previous build
echo "→ Cleaning previous build..."
rm -rf dist/ build/ *.spec

# 1. Generate icon
echo "→ Generating icon..."
python3 generate_icon.py

# 2. Build with PyInstaller
echo "→ Building .app with PyInstaller..."
pyinstaller \
    --noconfirm \
    --name "PrintBridge" \
    --onefile \
    --windowed \
    --icon icon_macos.png \
    --add-data "icon.png:." \
    --hidden-import pystray._darwin \
    --osx-bundle-identifier com.printbridge.agent \
    agent.py

echo "→ Build complete!"
echo "   .app location: dist/PrintBridge.app"

# 3. Make it a background app (no Dock icon, menu bar only)
echo "→ Setting as background service (no Dock icon)..."
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "dist/PrintBridge.app/Contents/Info.plist" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :LSUIElement true" "dist/PrintBridge.app/Contents/Info.plist"

# 4. Create DMG (optional — requires create-dmg)
if command -v create-dmg &> /dev/null; then
    echo "→ Creating DMG..."
    create-dmg \
        --volname "PrintBridge" \
        --volicon icon_macos.png \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "PrintBridge.app" 175 190 \
        --app-drop-link 425 190 \
        "dist/PrintBridge-Installer.dmg" \
        "dist/PrintBridge.app"
    echo "   DMG location: dist/PrintBridge-Installer.dmg"
else
    echo "   (Skipping DMG — install create-dmg: brew install create-dmg)"
fi

echo ""
echo "=== Done! ==="
