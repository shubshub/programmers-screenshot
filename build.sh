#!/bin/bash
# Build programmers-screenshot as an installable .deb.
#
#   ./build.sh              -> dist/programmers-screenshot_<version>_all.deb
#   ./build.sh --install    -> build, then install it with apt
set -euo pipefail

VERSION="0.26.0"
PACKAGE="programmers-screenshot"
ARCH="all"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$HERE/build/$PACKAGE"
DIST="$HERE/dist"
DEB="$DIST/${PACKAGE}_${VERSION}_${ARCH}.deb"

rm -rf "$HERE/build"
MODULE_DIR="$BUILD/usr/share/$PACKAGE/programmers_screenshot"
TOOLS_DIR="$MODULE_DIR/tools"
SOUND_DIR="$BUILD/usr/share/$PACKAGE/sounds"
mkdir -p "$BUILD/DEBIAN" \
         "$BUILD/usr/bin" \
         "$MODULE_DIR" \
         "$TOOLS_DIR" \
         "$SOUND_DIR" \
         "$BUILD/usr/share/applications" \
         "$BUILD/usr/share/icons/hicolor/scalable/apps" \
         "$BUILD/usr/share/man/man1" \
         "$BUILD/usr/share/doc/$PACKAGE" \
         "$DIST"

# --- payload ---------------------------------------------------------------
install -m 0755 "$HERE/bin/$PACKAGE"                       "$BUILD/usr/bin/$PACKAGE"
install -m 0644 "$HERE"/src/programmers_screenshot/*.py    "$MODULE_DIR/"
install -m 0644 "$HERE"/src/programmers_screenshot/tools/*.py "$TOOLS_DIR/"
install -m 0644 "$HERE/packaging/shutter.wav"              "$SOUND_DIR/shutter.wav"
install -m 0644 "$HERE/packaging/$PACKAGE.desktop"         "$BUILD/usr/share/applications/$PACKAGE.desktop"
install -m 0644 "$HERE/packaging/$PACKAGE.svg"             "$BUILD/usr/share/icons/hicolor/scalable/apps/$PACKAGE.svg"
gzip -9nc "$HERE/packaging/$PACKAGE.1" > "$BUILD/usr/share/man/man1/$PACKAGE.1.gz"
chmod 0644 "$BUILD/usr/share/man/man1/$PACKAGE.1.gz"

# --- control ---------------------------------------------------------------
sed "s/@VERSION@/$VERSION/" "$HERE/packaging/control" > "$BUILD/DEBIAN/control"
install -m 0755 "$HERE/packaging/postinst" "$BUILD/DEBIAN/postinst"
install -m 0755 "$HERE/packaging/postrm"   "$BUILD/DEBIAN/postrm"

cat > "$BUILD/usr/share/doc/$PACKAGE/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: programmers-screenshot
Source: https://github.com/shubshub/programmers-screenshot

Files: *
Copyright: 2026 Shubshub
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a
 copy of this software and associated documentation files (the "Software"),
 to deal in the Software without restriction, including without limitation
 the rights to use, copy, modify, merge, publish, distribute, sublicense,
 and/or sell copies of the Software, and to permit persons to whom the
 Software is furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 DEALINGS IN THE SOFTWARE.
EOF
chmod 0644 "$BUILD/usr/share/doc/$PACKAGE/copyright"

# The changelog is written by hand in packaging/changelog. It used to be
# generated here, which meant every build shipped the same "initial release"
# line no matter what was actually in it.
head -1 "$HERE/packaging/changelog" | grep -q "($VERSION)" || {
    echo "packaging/changelog does not start with an entry for $VERSION:" >&2
    head -1 "$HERE/packaging/changelog" >&2
    exit 1
}
cp "$HERE/packaging/changelog" "$BUILD/usr/share/doc/$PACKAGE/changelog.Debian"
gzip -9n "$BUILD/usr/share/doc/$PACKAGE/changelog.Debian"
chmod 0644 "$BUILD/usr/share/doc/$PACKAGE/changelog.Debian.gz"

# --- checksums + build -----------------------------------------------------
(cd "$BUILD" && find usr -type f -print0 | sort -z | xargs -0 md5sum > DEBIAN/md5sums)
chmod 0644 "$BUILD/DEBIAN/md5sums"

dpkg-deb --build --root-owner-group "$BUILD" "$DEB" >/dev/null
echo "Built $DEB"

if [ "${1:-}" = "--install" ]; then
    # --reinstall, or apt sees the same version number already installed and
    # does nothing at all, leaving you testing the previous build. The version
    # does not change between rebuilds during development, so this is the
    # normal case rather than the exception.
    sudo apt-get install -y --reinstall "$DEB"
    echo
    echo "Installed. Bind a hotkey with:  programmers-screenshot --install-hotkey"
fi
