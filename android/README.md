# Native Android port

This is a Java/Android Views implementation, not a WebView or a packaged GTK app.
Android 11+ (API 30) is required. No network or broad storage permission is requested.

## Build

Install JDK 17+ and the Android SDK with platform 35 and build-tools 35.0.0.
Set `ANDROID_HOME` to the SDK directory (or set `sdk.dir` in `local.properties`).

```sh
cd android
./gradlew assembleDebug lintDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The APK above is debug-signed for local development. Published releases use
a separate private signing key. To build the distributable APK:

```sh
export SCREENSHOT_KEYSTORE=/absolute/private/path/release.jks
export SCREENSHOT_KEYSTORE_PASSWORD_FILE=/absolute/private/path/keystore-password
./gradlew assembleRelease lintRelease
```

The keystore alias must be `programmers-screenshot`; the key password matches
the keystore password. Keep the keystore and password file outside the repo,
readable only by their owner, and back them up securely. Future APK updates
must use the same signing key. Signing material is never uploaded as a release
asset. `app/build/outputs/apk/release/app-release.apk` is the signed output.

The shared PC/Android release can be validated and published from an up-to-date,
clean `main` checkout using `xvfb-run -a ./release.sh --android --publish`, with
the signing variables and `ANDROID_HOME` set. It publishes the `.deb`, signed
APK, and `SHA256SUMS` under the shared version tag.

If you installed an earlier development APK, Android will reject an update
signed with the release key. Uninstall the development app before installing
the published APK, then enable its accessibility service and shortcut again.
This discards pending edits and private app data; PNGs already saved to Pictures
remain in the gallery. Updates between published APKs do not require uninstalling.

## Power / Side + Volume Up on Samsung

1. Open **Programmers Screenshot** and tap **Accessibility settings**.
2. Under **Installed apps**, enable **Programmers Screenshot**, acknowledging
   Android's accessibility permission dialog. If One UI blocks an APK installed
   outside a store, allow restricted settings for this app from its App info menu.
3. Open **Accessibility → Advanced settings → Side and Volume up buttons**.
4. Select **Programmers Screenshot**. If other shortcuts are selected, Samsung
   may show a chooser when you press the buttons.
5. From another app, briefly press Side/Power and Volume Up together. The frozen
   screen opens in the editor. Save exports the selected region (or the full
   image when no region is selected).

The app registers `flagRequestAccessibilityButton` and handles the system's
accessibility shortcut callback. It does not intercept raw power key events,
replace the power menu, need root, or depend on a computer once installed.
The physical button mapping is controlled by Samsung's Settings, not by an
ordinary APK. On other phones, use their accessibility button/gesture shortcut.
A **Screenshot editor** Quick Settings tile and an in-app delayed Capture button
are also available after enabling the service.

## Editor

The left side panel contains Region, Pen, Highlight, Line, Arrow, Box,
Ellipse, Measure, Picker, Redact, Pixelate, Step, and Text. The right side panel
contains Save, Share, Undo, Redo, Close, named ink colours and stroke sizes.
Both panels scroll vertically. Every control is a labelled 112 × 48 dp button.
The interface uses One UI–inspired rounded floating surfaces, labelled line
icons, section headings, blue selection accents, ripple and haptic feedback,
and animated panel openings. The setup screen and editor controls follow the
phone's light/dark display mode. Native Android fonts and controls are used.
Both panels start hidden. Swipe inward from either edge (or tap Tools/Actions) to reveal its panel;
swipe outward or tap Hide tools/Hide actions to hide it. The screenshot fills
the available canvas behind the panels; hiding panels never changes crop or
drawing coordinates. Drag on the fitted screenshot; tap for a label,
numbered step, or colour sample. Region tap clears the crop. Undo/redo applies
to both crop changes and annotations. Redact exports opaque black pixels;
pixelation is cosmetic and should not be used for secrets. Coordinates and
measurements refer to original screenshot pixels, not scaled display pixels.

Save writes a flattened PNG to `Pictures/ProgrammersScreenshot` via MediaStore
and copies its image URI to the Android clipboard. Share saves and opens the
system share sheet with temporary read access. Pasting images depends on the
receiving app. Cancel discards the pending capture. Captures are kept in
private cache during editing; only explicit Save/Share publishes an image.

The accessibility service requests screenshot access only, not window-content
retrieval, key filtering, touch exploration, microphone, or network access.
Protected windows and the lock screen may reject screenshots. Capture only
runs when invoked; it does not automatically take a shot when enabled.

## Current scope

The core screenshot/annotation workflow is ported. Desktop-specific features
(X11 windows, multi-monitor controls, GNOME hotkeys, shell recipes, desktop
updater/skill integration) are not part of the APK. Screen recording/GIF/audio,
image import, and persistent preferences are not yet ported. Editing state
survives rotation, but not Android killing the app process; the cached capture
can be reopened only while it is still present. The desktop application and
its build remain independent.

## Device tests

```sh
./gradlew assembleDebug assembleDebugAndroidTest
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell am instrument -w io.github.shubshub.screenshot.test/io.github.shubshub.screenshot.EditorInstrumentation
```

These exercise native Canvas rendering, crop coordinates, opaque redaction,
undo/redo, pixelation, panel edge swipes, scrolling and uniform labelled buttons
on a device. The tests use a synthetic image, replace
the app's pending capture, and close the editor. Physical Side + Volume Up
should also be tested after selecting the service in Samsung Settings.

References: [Samsung accessibility shortcuts](https://www.samsung.com/us/support/answer/ANS10001906/),
[Android AccessibilityService](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService).
