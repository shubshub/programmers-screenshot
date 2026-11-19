package io.github.shubshub.screenshot;

import android.content.Context;
import android.graphics.*;
import android.view.MotionEvent;
import android.view.View;
import java.util.ArrayList;
import java.util.Locale;

/** All coordinates and stroke widths are in source-image pixels, independent of view size. */
@android.annotation.SuppressLint("ViewConstructor") // Constructed programmatically with a captured bitmap, never inflated.
public class EditorView extends View {
    public static final String[] TOOLS = {"Region", "Pen", "Highlight", "Line", "Arrow", "Box", "Ellipse", "Measure", "Picker", "Redact", "Pixelate", "Step", "Text"};
    String tool = "Region";
    int ink = Color.rgb(255, 80, 100);
    float width = 8;
    private final Bitmap source;
    private Bitmap scene;
    private final ArrayList<Mark> history = new ArrayList<>();
    private final ArrayList<Mark> redo = new ArrayList<>();
    private Mark active;
    private Rect crop;
    private float scale = 1, offsetX, offsetY;
    private final Paint paint = new Paint(3);
    private final EditorActivity owner;

    static class Mark {
        String tool, text = "";
        int color, number;
        float width, x, y, endX, endY;
        Path path = new Path();
        Rect bounds(int w, int h) {
            return new Rect(Math.max(0, Math.min(w - 1, (int)Math.min(x, endX))), Math.max(0, Math.min(h - 1, (int)Math.min(y, endY))),
                Math.max(1, Math.min(w, (int)Math.ceil(Math.max(x, endX)))), Math.max(1, Math.min(h, (int)Math.ceil(Math.max(y, endY)))));
        }
    }
    public EditorView(EditorActivity owner, Bitmap source) {
        super(owner); this.owner = owner; this.source = source;
        setContentDescription("Screenshot canvas. Drag to use selected tool.");
        rebuild();
    }
    private void rebuild() {
        if (scene == null) scene = Bitmap.createBitmap(source.getWidth(), source.getHeight(), Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(scene);
        canvas.drawBitmap(source, 0, 0, null); crop = null;
        for (Mark mark : history) {
            if (mark.tool.equals("Region")) { crop = mark.bounds(source.getWidth(), source.getHeight()); if (crop.width() < 3 || crop.height() < 3) crop = null; }
            else drawMark(canvas, mark, scene);
        }
        invalidate();
    }
    void undo() { cancelStroke(); if (!history.isEmpty()) { redo.add(history.remove(history.size() - 1)); rebuild(); } }
    void redo() { cancelStroke(); if (!redo.isEmpty()) { history.add(redo.remove(redo.size() - 1)); rebuild(); } }
    void cancelStroke() { active = null; invalidate(); }
    private void commit(Mark mark) { history.add(mark); redo.clear(); rebuild(); }
    void selectTool(String value) { cancelStroke(); tool = value; }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas); canvas.drawColor(0xff101014);
        scale = Math.min((float)getWidth() / source.getWidth(), (float)getHeight() / source.getHeight());
        offsetX = (getWidth() - source.getWidth() * scale) / 2;
        offsetY = (getHeight() - source.getHeight() * scale) / 2;
        canvas.save(); canvas.translate(offsetX, offsetY); canvas.scale(scale, scale);
        canvas.drawBitmap(scene, 0, 0, null);
        if (active != null && !active.tool.equals("Region")) drawMark(canvas, active, null);
        Rect selection = active != null && active.tool.equals("Region") ? active.bounds(source.getWidth(), source.getHeight()) : crop;
        if (selection != null) {
            paint.reset(); paint.setAntiAlias(true);
            canvas.save(); canvas.clipOutRect(selection); canvas.drawColor(0x88000000); canvas.restore();
            paint.setColor(0xff55dfbb); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(2 / scale);
            canvas.drawRect(selection, paint); paint.setStyle(Paint.Style.FILL); paint.setTextSize(14 / scale);
            canvas.drawText(selection.width() + " × " + selection.height() + " px", selection.left + 6 / scale, Math.max(18 / scale, selection.top - 6 / scale), paint);
        }
        canvas.restore();
    }
    private void drawMark(Canvas c, Mark m, Bitmap target) {
        paint.reset(); paint.setAntiAlias(true); paint.setColor(m.color); paint.setStrokeWidth(m.width);
        paint.setStrokeCap(Paint.Cap.ROUND); paint.setStrokeJoin(Paint.Join.ROUND); paint.setStyle(Paint.Style.STROKE);
        Rect box = m.bounds(source.getWidth(), source.getHeight());
        switch (m.tool) {
            case "Pen": c.drawPath(m.path, paint); break;
            case "Highlight": paint.setAlpha(85); paint.setStrokeWidth(m.width * 4); c.drawPath(m.path, paint); break;
            case "Box": c.drawRect(box, paint); break;
            case "Ellipse": c.drawOval(new RectF(box), paint); break;
            case "Redact": paint.setColor(Color.BLACK); paint.setStyle(Paint.Style.FILL); c.drawRect(box, paint); break;
            case "Pixelate":
                if (target != null && box.width() > 0 && box.height() > 0) {
                    Bitmap part = Bitmap.createBitmap(target, box.left, box.top, box.width(), box.height());
                    Bitmap tiny = Bitmap.createScaledBitmap(part, Math.max(1, box.width() / 20), Math.max(1, box.height() / 20), true);
                    Paint blocks = new Paint(); blocks.setFilterBitmap(false);
                    c.drawBitmap(tiny, null, box, blocks);
                    if (tiny != part && tiny != target) tiny.recycle(); if (part != target) part.recycle();
                } else { paint.setColor(0x887f8796); paint.setStyle(Paint.Style.FILL); c.drawRect(box, paint); }
                break;
            case "Line": case "Arrow": case "Measure":
                c.drawLine(m.x, m.y, m.endX, m.endY, paint);
                if (m.tool.equals("Arrow")) {
                    double angle = Math.atan2(m.endY - m.y, m.endX - m.x);
                    float length = Math.max(24, m.width * 4);
                    for (double delta : new double[]{-0.5, 0.5}) c.drawLine(m.endX, m.endY,
                        m.endX - (float)Math.cos(angle + delta) * length, m.endY - (float)Math.sin(angle + delta) * length, paint);
                }
                if (m.tool.equals("Measure")) {
                    String label = String.format(Locale.US, "%.1f px", Math.hypot(m.endX - m.x, m.endY - m.y));
                    paint.setTextSize(36); paint.setStyle(Paint.Style.FILL);
                    float tx = (m.x + m.endX) / 2, ty = (m.y + m.endY) / 2;
                    paint.setColor(Color.BLACK); c.drawRect(tx - 4, ty - 40, tx + paint.measureText(label) + 4, ty + 6, paint);
                    paint.setColor(m.color); c.drawText(label, tx, ty, paint);
                }
                break;
            case "Step":
                paint.setStyle(Paint.Style.FILL); c.drawCircle(m.x, m.y, 30 + m.width, paint);
                paint.setColor(Color.WHITE); paint.setTextSize(38 + m.width); paint.setTypeface(Typeface.DEFAULT_BOLD);
                paint.setTextAlign(Paint.Align.CENTER); c.drawText(Integer.toString(m.number), m.x, m.y - (paint.ascent() + paint.descent()) / 2, paint); break;
            case "Text":
                paint.setTextSize(32 + m.width * 2); paint.setTypeface(Typeface.DEFAULT_BOLD); paint.setStyle(Paint.Style.FILL);
                float y = m.y;
                for (String line : m.text.split("\n", -1)) {
                    paint.setColor(0xe6000000); c.drawRect(m.x - 6, y + paint.ascent() - 4, m.x + paint.measureText(line) + 6, y + paint.descent() + 4, paint);
                    paint.setColor(m.color); c.drawText(line, m.x, y, paint); y += paint.getFontSpacing();
                } break;
        }
        paint.setStyle(Paint.Style.FILL); paint.setTextAlign(Paint.Align.LEFT); paint.setTypeface(Typeface.DEFAULT);
    }
    @Override public boolean onTouchEvent(MotionEvent event) {
        float x = Math.max(0, Math.min(source.getWidth() - 1, (event.getX() - offsetX) / scale));
        float y = Math.max(0, Math.min(source.getHeight() - 1, (event.getY() - offsetY) / scale));
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                if (event.getX() < offsetX || event.getY() < offsetY || event.getX() > offsetX + source.getWidth() * scale || event.getY() > offsetY + source.getHeight() * scale) return false;
                active = new Mark(); active.tool = tool; active.color = ink; active.width = width;
                active.x = active.endX = x; active.y = active.endY = y; active.path.moveTo(x, y); active.path.lineTo(x + .01f, y + .01f);
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(true); invalidate(); return true;
            case MotionEvent.ACTION_MOVE:
                if (active != null) { active.endX = x; active.endY = y; active.path.lineTo(x, y); invalidate(); } return true;
            case MotionEvent.ACTION_UP:
                if (active == null) return true;
                active.endX = x; active.endY = y; active.path.lineTo(x, y);
                Mark done = active; active = null;
                if (tool.equals("Picker")) {
                    ink = scene.getPixel((int)x, (int)y);
                    String hex = String.format(Locale.US, "#%06X", ink & 0xffffff);
                    ((android.content.ClipboardManager)getContext().getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(android.content.ClipData.newPlainText("Colour", hex));
                    owner.message("Copied " + hex); invalidate();
                } else if (tool.equals("Text")) {
                    android.widget.EditText input = new android.widget.EditText(getContext()); input.setHint("Label"); input.setInputType(131073);
                    new android.app.AlertDialog.Builder(getContext()).setTitle("Add text").setView(input).setPositiveButton("Add", (d, w) -> {
                        done.text = input.getText().toString(); if (!done.text.isEmpty()) commit(done);
                    }).setNegativeButton("Cancel", null).show(); invalidate();
                } else {
                    if (tool.equals("Step")) { done.number = 1; for (Mark m : history) if (m.tool.equals("Step")) done.number++; }
                    commit(done);
                }
                performClick(); return true;
            case MotionEvent.ACTION_CANCEL: cancelStroke(); return true;
            default: return true;
        }
    }
    @Override public boolean performClick() { super.performClick(); return true; }
    Bitmap export() {
        cancelStroke();
        if (crop == null) return scene.copy(Bitmap.Config.ARGB_8888, false);
        Bitmap cropped = Bitmap.createBitmap(scene, crop.left, crop.top, crop.width(), crop.height());
        Bitmap result = cropped.copy(Bitmap.Config.ARGB_8888, false);
        if (cropped != scene) cropped.recycle();
        return result;
    }
    void release() { source.recycle(); scene.recycle(); }
}
