package io.github.shubshub.screenshot;

import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;
import android.os.Handler;
import android.widget.Toast;

public class CaptureTile extends TileService {
    @Override public void onStartListening() {
        getQsTile().setState(CaptureService.instance == null ? Tile.STATE_UNAVAILABLE : Tile.STATE_ACTIVE);
        getQsTile().updateTile();
    }
    @Override public void onClick() {
        unlockAndRun(() -> {
            if (CaptureService.instance == null) { Toast.makeText(this, "Enable Programmers Screenshot in Accessibility", Toast.LENGTH_LONG).show(); return; }
            CaptureService.instance.performGlobalAction(android.os.Build.VERSION.SDK_INT >= 31
                ? android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_DISMISS_NOTIFICATION_SHADE
                : android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK);
            new Handler(getMainLooper()).postDelayed(() -> { if (CaptureService.instance != null) CaptureService.instance.capture(); }, 500);
        });
    }
}
