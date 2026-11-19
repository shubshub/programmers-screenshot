package io.github.shubshub.screenshot;

import android.app.Activity;
import android.os.Bundle;
import android.content.*;
import android.graphics.*;
import android.net.Uri;
import android.provider.MediaStore;
import android.widget.*;
import java.io.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;

public class EditorActivity extends Activity {
    static boolean visible;
    private EditorView editor;
    private boolean saving;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        Bitmap image = BitmapFactory.decodeFile(new File(getCacheDir(), "capture.png").getPath());
        if (image == null) { message("No screenshot available. Use the shortcut to capture first."); finish(); return; }
        editor = new EditorView(this, image);
        EditorControls root = new EditorControls(this, editor, this::finish, () -> save(false), () -> save(true));
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars() | android.view.WindowInsets.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom); return insets;
        });
        setContentView(root);
    }
    boolean isSaving() { return saving; }
    private void save(boolean share) {
        if (saving) return;
        Bitmap result = editor.export(); saving = true;
        worker.execute(() -> {
            Uri uri = null;
            try {
                ContentValues values = new ContentValues();
                values.put(MediaStore.Images.Media.DISPLAY_NAME, "Screenshot_" + new SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(new Date()) + ".png");
                values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
                values.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/ProgrammersScreenshot");
                values.put(MediaStore.Images.Media.IS_PENDING, 1);
                uri = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                if (uri == null) throw new IOException("Could not create image");
                try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                    if (out == null || !result.compress(Bitmap.CompressFormat.PNG, 100, out)) throw new IOException("Could not write PNG");
                }
                values.clear(); values.put(MediaStore.Images.Media.IS_PENDING, 0); getContentResolver().update(uri, values, null, null);
                Uri saved = uri;
                runOnUiThread(() -> {
                    saving = false;
                    android.content.ClipboardManager clipboard = (android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
                    clipboard.setPrimaryClip(ClipData.newUri(getContentResolver(), "Screenshot", saved));
                    if (share) {
                        Intent send = new Intent(Intent.ACTION_SEND).setType("image/png").putExtra(Intent.EXTRA_STREAM, saved).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        send.setClipData(ClipData.newUri(getContentResolver(), "Screenshot", saved));
                        startActivity(Intent.createChooser(send, "Share screenshot"));
                    } else { message("Saved to Pictures/ProgrammersScreenshot and copied"); finish(); }
                });
            } catch (Exception e) {
                if (uri != null) getContentResolver().delete(uri, null, null);
                runOnUiThread(() -> { saving = false; message("Save failed: " + e.getMessage()); });
            } finally { result.recycle(); }
        });
    }
    void message(String text) { Toast.makeText(this, text, Toast.LENGTH_LONG).show(); }
    @Override protected void onResume() { super.onResume(); visible = true; }
    @Override protected void onPause() { visible = false; super.onPause(); }
    @Override protected void onDestroy() {
        if (editor != null) editor.release(); worker.shutdown();
        if (isFinishing()) new File(getCacheDir(), "capture.png").delete();
        super.onDestroy();
    }
}
