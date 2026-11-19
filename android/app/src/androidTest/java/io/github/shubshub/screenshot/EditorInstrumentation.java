package io.github.shubshub.screenshot;

import android.app.Instrumentation;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.MotionEvent;
import java.io.File;
import java.io.FileOutputStream;

/** Device-side image assertions; exercises real Canvas, touch coordinates and undo history. */
public class EditorInstrumentation extends Instrumentation {
    @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }
    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            Bitmap base = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888); base.eraseColor(Color.WHITE);
            try (FileOutputStream out = new FileOutputStream(new File(getTargetContext().getCacheDir(), "capture.png"))) { base.compress(Bitmap.CompressFormat.PNG, 100, out); }
            EditorActivity activity = (EditorActivity) startActivitySync(new Intent(getTargetContext(), EditorActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            java.util.concurrent.atomic.AtomicReference<Throwable> failure = new java.util.concurrent.atomic.AtomicReference<>();
            runOnMainSync(() -> { try {
                EditorView view = new EditorView(activity, base); view.layout(0, 0, 100, 100);
                view.draw(new android.graphics.Canvas(Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)));
                view.selectTool("Redact"); drag(view, 10, 10, 40, 40);
                Bitmap image = view.export(); require(image.getPixel(20, 20) == Color.BLACK, "redaction must be opaque"); image.recycle();
                view.selectTool("Region"); drag(view, 5, 5, 50, 50);
                image = view.export(); require(image.getWidth() == 45 && image.getHeight() == 45, "crop dimensions");
                require(image.getPixel(15, 15) == Color.BLACK, "crop offset"); image.recycle();
                view.undo(); image = view.export(); require(image.getWidth() == 100, "undo crop"); image.recycle();
                view.undo(); image = view.export(); require(image.getPixel(20, 20) == Color.WHITE, "undo redaction"); image.recycle();
                view.redo(); image = view.export(); require(image.getPixel(20, 20) == Color.BLACK, "redo redaction"); image.recycle();
                view.selectTool("Pixelate"); drag(view, 0, 0, 80, 80);
                image = view.export(); require(image.getWidth() == 100, "pixelation renders"); image.recycle();
                view.selectTool("Region"); drag(view, 20, 20, 20, 20);
                image = view.export(); require(image.getWidth() == 100, "tap clears region"); image.recycle();
                EditorControls controls = new EditorControls(activity, view, () -> {}, () -> {}, () -> {});
                float density = activity.getResources().getDisplayMetrics().density;
                int cw = Math.round(360 * density), ch = Math.round(640 * density);
                controls.measure(android.view.View.MeasureSpec.makeMeasureSpec(cw, android.view.View.MeasureSpec.EXACTLY), android.view.View.MeasureSpec.makeMeasureSpec(ch, android.view.View.MeasureSpec.EXACTLY));
                controls.layout(0, 0, cw, ch);
                require(controls.left.getVisibility() == android.view.View.GONE && controls.right.getVisibility() == android.view.View.GONE, "panels start hidden");
                controls.showPanel(true, true);
                controls.measure(android.view.View.MeasureSpec.makeMeasureSpec(cw, android.view.View.MeasureSpec.EXACTLY), android.view.View.MeasureSpec.makeMeasureSpec(ch, android.view.View.MeasureSpec.EXACTLY));
                controls.layout(0, 0, cw, ch);
                require(controls.left.canScrollVertically(1), "tools must scroll");
                swipe(controls, 100 * density, 300 * density, 2 * density, 300 * density);
                require(controls.left.getVisibility() == android.view.View.GONE, "swipe left closes tools");
                swipe(controls, density, 300 * density, 100 * density, 300 * density);
                require(controls.left.getVisibility() == android.view.View.VISIBLE, "swipe from left opens tools");
                swipe(controls, 359 * density, 300 * density, 250 * density, 300 * density);
                require(controls.right.getVisibility() == android.view.View.VISIBLE, "swipe from right opens actions");
                controls.measure(android.view.View.MeasureSpec.makeMeasureSpec(cw, android.view.View.MeasureSpec.EXACTLY), android.view.View.MeasureSpec.makeMeasureSpec(ch, android.view.View.MeasureSpec.EXACTLY));
                controls.layout(0, 0, cw, ch);
                require(controls.right.canScrollVertically(1), "actions must scroll");
                checkButtons(controls, Math.round(112 * density), Math.round(48 * density));
                Bitmap preview = Bitmap.createBitmap(cw, ch, Bitmap.Config.ARGB_8888);
                controls.draw(new android.graphics.Canvas(preview));
                try (FileOutputStream out = new FileOutputStream(new File(getTargetContext().getCacheDir(), "editor-ui-test.png"))) { preview.compress(Bitmap.CompressFormat.PNG, 100, out); }
                preview.recycle();
                view.release(); activity.finish();
            } catch (Throwable error) { failure.set(error); }
            });
            if (failure.get() != null) throw failure.get();
            result.putString("stream", "PASS: opaque redaction, crop dimensions/offset, undo, redo, pixelation, region clearing, edge swipes, scrollable panels, uniform labelled buttons\n");
            finish(-1, result);
        } catch (Throwable error) { result.putString("stream", "FAIL: " + error + "\n"); finish(1, result); }
    }
    private static void require(boolean ok, String message) { if (!ok) throw new AssertionError(message); }
    private static void checkButtons(android.view.View view, int width, int height) {
        if (view instanceof android.widget.Button) {
            require(view.getLayoutParams().width == width && view.getLayoutParams().height == height, "uniform button dimensions");
            require(!((android.widget.Button)view).getText().toString().isEmpty(), "button name");
        }
        if (view instanceof android.view.ViewGroup) {
            android.view.ViewGroup group = (android.view.ViewGroup)view;
            for (int i = 0; i < group.getChildCount(); i++) checkButtons(group.getChildAt(i), width, height);
        }
    }
    private static void swipe(EditorControls controls, float x, float y, float ex, float ey) {
        long t = SystemClock.uptimeMillis();
        for (int action : new int[]{MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE, MotionEvent.ACTION_UP}) {
            MotionEvent event = MotionEvent.obtain(t, t + action * 20, action, action == MotionEvent.ACTION_DOWN ? x : ex, action == MotionEvent.ACTION_DOWN ? y : ey, 0);
            controls.dispatchTouchEvent(event); event.recycle();
        }
    }
    private static void drag(EditorView view, float x, float y, float ex, float ey) {
        long t = SystemClock.uptimeMillis();
        MotionEvent down = MotionEvent.obtain(t, t, MotionEvent.ACTION_DOWN, x, y, 0);
        MotionEvent up = MotionEvent.obtain(t, t + 50, MotionEvent.ACTION_UP, ex, ey, 0);
        view.onTouchEvent(down); view.onTouchEvent(up); down.recycle(); up.recycle();
    }
}
