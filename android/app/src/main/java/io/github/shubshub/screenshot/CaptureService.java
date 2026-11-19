package io.github.shubshub.screenshot;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityButtonController;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Handler;
import android.os.Looper;
import android.view.Display;
import android.view.accessibility.AccessibilityEvent;
import android.widget.Toast;
import java.io.File;
import java.io.FileOutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class CaptureService extends AccessibilityService {
    static volatile CaptureService instance;
    private boolean busy;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final AccessibilityButtonController.AccessibilityButtonCallback shortcut =
        new AccessibilityButtonController.AccessibilityButtonCallback() {
            @Override public void onClicked(AccessibilityButtonController controller) { capture(); }
        };
    @Override protected void onServiceConnected() {
        instance = this;
        getAccessibilityButtonController().registerAccessibilityButtonCallback(shortcut);
    }
    public void capture() {
        if (busy) return;
        if (EditorActivity.visible) { message("Close the current screenshot first"); return; }
        busy = true;
        takeScreenshot(Display.DEFAULT_DISPLAY, getMainExecutor(), new TakeScreenshotCallback() {
            @Override public void onSuccess(ScreenshotResult result) {
                worker.execute(() -> {
                    try (android.hardware.HardwareBuffer buffer = result.getHardwareBuffer()) {
                        Bitmap hardware = Bitmap.wrapHardwareBuffer(buffer, result.getColorSpace());
                        if (hardware == null) throw new IllegalStateException("No screenshot returned");
                        Bitmap image = hardware.copy(Bitmap.Config.ARGB_8888, false);
                        hardware.recycle();
                        File file = new File(getCacheDir(), "capture.png");
                        try (FileOutputStream out = new FileOutputStream(file)) {
                            if (!image.compress(Bitmap.CompressFormat.PNG, 100, out)) throw new java.io.IOException("PNG encoding failed");
                        } finally { image.recycle(); }
                        main.post(() -> {
                            busy = false;
                            startActivity(new Intent(CaptureService.this, EditorActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                        });
                    } catch (Exception error) {
                        main.post(() -> { busy = false; message("Capture failed: " + error.getMessage()); });
                    }
                });
            }
            @Override public void onFailure(int code) {
                busy = false;
                message("Cannot capture this screen (" + code + "). Unlock your phone; protected apps cannot be captured.");
            }
        });
    }
    private void message(String text) { Toast.makeText(this, text, Toast.LENGTH_LONG).show(); }
    @Override public void onAccessibilityEvent(AccessibilityEvent event) { }
    @Override public void onInterrupt() { }
    @Override public void onDestroy() {
        instance = null;
        getAccessibilityButtonController().unregisterAccessibilityButtonCallback(shortcut);
        worker.shutdown();
        super.onDestroy();
    }
}
