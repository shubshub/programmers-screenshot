#!/bin/bash
# Gate a release: check, build, verify, and optionally tag and publish.
#
#   ./release.sh              check, build and verify — changes nothing
#   ./release.sh --tag        ...and create the annotated tag
#   ./release.sh --tag --push ...and push it
#   ./release.sh --publish    ...and make a GitHub release with the .deb
#   ./release.sh --android --publish  ...with a signed Android APK too
#
# Safe by default: without a flag it only reads, builds into dist/, and tells
# you whether the thing is fit to ship. Anything that leaves this machine is
# opt-in.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PACKAGE="programmers-screenshot"
WANT_TAG=0
WANT_PUSH=0
WANT_PUBLISH=0
ALLOW_DIRTY=0
WANT_ANDROID=0

for argument in "$@"; do
    case "$argument" in
        --tag) WANT_TAG=1 ;;
        --push) WANT_TAG=1; WANT_PUSH=1 ;;
        --publish) WANT_TAG=1; WANT_PUSH=1; WANT_PUBLISH=1 ;;
        --allow-dirty) ALLOW_DIRTY=1 ;;
        --android) WANT_ANDROID=1 ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "unknown option: $argument" >&2; exit 2 ;;
    esac
done

problems=0
step()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()    { printf '  ok    %s\n' "$*"; }
bad()   { printf '  FAIL  %s\n' "$*"; problems=$((problems + 1)); }
note()  { printf '  --    %s\n' "$*"; }

# --- 1. what are we releasing ----------------------------------------------
VERSION="$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' src/programmers_screenshot/cli.py)"
step "Releasing $PACKAGE $VERSION"

# --- 2. the tree is in a fit state ------------------------------------------
step "Working tree"
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] && ok "on main" || bad "on '$branch', not main"

if [ -z "$(git status --porcelain)" ]; then
    ok "nothing uncommitted"
elif [ "$ALLOW_DIRTY" = 1 ]; then
    note "uncommitted changes, allowed by --allow-dirty"
else
    bad "uncommitted changes — commit them, or pass --allow-dirty"
    git status --short | sed 's/^/        /'
fi

git fetch -q origin 2>/dev/null || note "could not reach origin"
if git rev-parse origin/main >/dev/null 2>&1; then
    behind="$(git rev-list --count HEAD..origin/main)"
    ahead="$(git rev-list --count origin/main..HEAD)"
    [ "$behind" = 0 ] && ok "not behind origin/main" || bad "$behind commit(s) behind origin/main"
    [ "$ahead" = 0 ] && ok "not ahead of origin/main" || bad "$ahead commit(s) not pushed"
fi

if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    bad "tag v$VERSION already exists"
else
    ok "tag v$VERSION is free"
fi

# --- 3. the version agrees with itself --------------------------------------
step "Version consistency"
# The man page and the README no longer carry the number -- build.sh puts it
# into the one and the other points at the Releases page -- so the changelog
# is the only place left that has to be kept in step by hand.
if grep -q "($VERSION)" packaging/changelog; then
    ok "packaging/changelog"
else
    bad "packaging/changelog has no entry for $VERSION"
fi

# --- 4. it does what it says ------------------------------------------------
step "Tests"
if suite_output=$(python3 tests/run.py 2>&1); then
    ok "$(echo "$suite_output" | tail -1)"
else
    bad "$(echo "$suite_output" | tail -1)"
    echo "$suite_output" | sed 's/^/        /'
fi

# --- 5. build ---------------------------------------------------------------
step "Build"
./build.sh >/dev/null
DEB="dist/${PACKAGE}_${VERSION}_all.deb"
[ -f "$DEB" ] && ok "$DEB ($(du -h "$DEB" | cut -f1))" || bad "no $DEB"

# --- 6. the artifact is sound ------------------------------------------------
step "The package itself"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
dpkg-deb -x "$DEB" "$STAGE"
dpkg-deb -e "$DEB" "$STAGE/DEBIAN"

reported="$("$STAGE/usr/bin/$PACKAGE" --version 2>/dev/null | awk '{print $2}')"
[ "$reported" = "$VERSION" ] && ok "reports $VERSION" || bad "reports '$reported'"

# -B, or importing would byte-compile the modules into the tree we are about
# to check for stray build artefacts.
if PYTHONPATH="$STAGE/usr/share/$PACKAGE" python3 -B -c "
from programmers_screenshot import tools, paths
assert tools.build_tools(), 'no tools'
assert paths.sound_file(), 'no shutter sound'
" 2>/dev/null; then
    ok "imports, and finds its tools and sound"
else
    bad "the installed layout does not import cleanly"
fi

shipped="$(gzip -dc "$STAGE/usr/share/doc/$PACKAGE/changelog.Debian.gz" | head -1)"
case "$shipped" in
    *"($VERSION)"*) ok "changelog is for $VERSION" ;;
    *) bad "changelog says: $shipped" ;;
esac

# Debian policy requires a copyright file in every package. This also checks
# the terms match the repo's, so the artefact cannot quietly grant more than
# the LICENSE does -- which is exactly what happened while it said MIT.
if [ ! -s "$STAGE/usr/share/doc/$PACKAGE/copyright" ]; then
    bad "no copyright file, which Debian policy requires"
elif ! grep -q "^License: MIT" "$STAGE/usr/share/doc/$PACKAGE/copyright"; then
    bad "the package copyright does not name the same licence as LICENSE"
elif ! head -1 LICENSE | grep -q "MIT"; then
    bad "LICENSE is no longer MIT; the package copyright still says it is"
else
    ok "copyright matches LICENSE"
fi
[ -f LICENSE ] && ok "LICENSE in the repo" || bad "no LICENSE in the repo"

if man --warnings -l "$STAGE/usr/share/man/man1/$PACKAGE.1.gz" >/dev/null 2>&1; then
    ok "man page renders"
else
    bad "man page has warnings"
fi

# Generated now, so worth checking the substitution actually happened.
titled="$(gzip -dc "$STAGE/usr/share/man/man1/$PACKAGE.1.gz" | head -1)"
case "$titled" in
    *"$PACKAGE $VERSION"*) ok "man page says $VERSION" ;;
    *) bad "man page title line says: $titled" ;;
esac

if desktop-file-validate "$STAGE/usr/share/applications/$PACKAGE.desktop" 2>/dev/null; then
    ok "desktop entry valid"
else
    bad "desktop entry invalid"
fi

[ -s "$STAGE/DEBIAN/md5sums" ] && ok "md5sums present" || bad "no md5sums"

# Read the package listing, not the extracted tree: anything this script does
# to the tree afterwards would otherwise look like a leak.
if dpkg-deb -c "$DEB" | grep -qE '__pycache__|\.pyc$'; then
    bad "build artefacts leaked into the package"
    dpkg-deb -c "$DEB" | grep -E '__pycache__|\.pyc$' | sed 's/^/        /'
else
    ok "no stray build artefacts"
fi

# --- 7. lint ----------------------------------------------------------------
step "Lint"
if command -v ruff >/dev/null; then
    if ruff_output=$(ruff check src tests 2>&1); then
        ok "ruff is happy"
    else
        bad "ruff says:"
        echo "$ruff_output" | sed 's/^/        /'
    fi
else
    note "ruff not installed — pipx run ruff check src tests lints without installing it"
fi

if command -v lintian >/dev/null; then
    if lintian_output=$(lintian --no-tag-display-limit "$DEB" 2>&1); then
        ok "lintian is happy"
    else
        note "lintian says:"
        echo "$lintian_output" | sed 's/^/        /'
    fi
else
    note "lintian not installed — sudo apt install lintian to check the packaging"
fi

# --- Android, when requested ------------------------------------------------
ASSETS=("$DEB")
if [ "$WANT_ANDROID" = 1 ]; then
    step "Android release APK"
    android_version="$(sed -n "s/^[[:space:]]*versionName '\([^']*\)'/\1/p" android/app/build.gradle)"
    [ "$android_version" = "$VERSION" ] && ok "Android version agrees" || bad "Android is $android_version, PC is $VERSION"
    if [ ! -f "${SCREENSHOT_KEYSTORE:-}" ] || [ ! -f "${SCREENSHOT_KEYSTORE_PASSWORD_FILE:-}" ]; then
        bad "set SCREENSHOT_KEYSTORE and SCREENSHOT_KEYSTORE_PASSWORD_FILE to private release signing files"
    else
        (cd android && ./gradlew assembleRelease assembleDebugAndroidTest lintRelease)
        APK="dist/${PACKAGE}_${VERSION}_android.apk"
        cp android/app/build/outputs/apk/release/app-release.apk "$APK"
        sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
        signer="$sdk_root/build-tools/35.0.0/apksigner"
        if [ -x "$signer" ] && "$signer" verify "$APK"; then
            ok "release APK signature verifies"
        else
            bad "APK signature verification failed (requires Android build-tools 35.0.0)"
        fi
        ASSETS+=("$APK")
    fi
fi

# --- verdict ----------------------------------------------------------------
if [ "$problems" -gt 0 ]; then
    printf '\n\033[1m%d problem(s). Not releasing.\033[0m\n' "$problems"
    exit 1
fi
printf '\n\033[1mReady: %s\033[0m\n' "$DEB"
if [ "$WANT_ANDROID" = 1 ]; then
    (cd dist && sha256sum "${PACKAGE}_${VERSION}_all.deb" "${PACKAGE}_${VERSION}_android.apk" > SHA256SUMS)
    ASSETS+=(dist/SHA256SUMS)
fi

# --- 8. tag and publish, only when asked ------------------------------------
if [ "$WANT_TAG" = 1 ]; then
    step "Tagging"
    git tag -a "v$VERSION" -m "$PACKAGE $VERSION"
    ok "created v$VERSION"
    if [ "$WANT_PUSH" = 1 ]; then
        git push origin "v$VERSION"
        ok "pushed v$VERSION"
    else
        note "not pushed; ./release.sh --push would"
    fi
fi

if [ "$WANT_PUBLISH" = 1 ]; then
    step "Publishing"
    notes="$(mktemp)"
    awk 'NR>1 && /^programmers-screenshot \(/ {exit} {print}' packaging/changelog > "$notes"
    if [ "$WANT_ANDROID" = 1 ]; then
        printf '\nAssets: .deb for Linux PCs, signed APK for Android 11+, and SHA256SUMS.\nAndroid shortcut setup and platform scope: https://github.com/shubshub/programmers-screenshot/blob/v%s/android/README.md\n' "$VERSION" >> "$notes"
        printf '\nIf upgrading from a development APK, uninstall it first because the published APK uses a separate release signing key. This discards pending edits/private app data; saved PNGs remain in Pictures. Re-enable screenshot access and the shortcut after installing. Future published APKs will use this same release key.\n' >> "$notes"
    fi
    title="$PACKAGE $VERSION"
    [ "$WANT_ANDROID" = 0 ] || title="$title — PC and Android"
    gh release create "v$VERSION" "${ASSETS[@]}" --title "$title" --notes-file "$notes"
    rm -f "$notes"
    ok "published"
fi
