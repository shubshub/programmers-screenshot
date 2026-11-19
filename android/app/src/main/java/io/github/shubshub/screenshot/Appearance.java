package io.github.shubshub.screenshot;

import android.content.Context;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.*;
import android.graphics.drawable.*;
import android.widget.Button;

/** Shared native light/dark surfaces, touch feedback and a small consistent line-icon set. */
final class Appearance {
    final int background, surface, text, secondary, accent, selected, soft, divider;
    final Context context;
    Appearance(Context context) {
        this.context = context;
        boolean dark = (context.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        background = dark ? 0xff101014 : 0xfff2f2f6;
        surface = dark ? 0xff202024 : Color.WHITE;
        text = dark ? 0xfff5f5f7 : 0xff19191d;
        secondary = dark ? 0xffa4a4ae : 0xff707079;
        accent = dark ? 0xff9ab7ff : 0xff285bd4;
        selected = dark ? 0xff293957 : 0xffeaf0ff;
        soft = dark ? 0xff2c2c32 : 0xfff5f5f9;
        divider = dark ? 0xff3c3c44 : 0xffe8e8ee;
    }
    int dp(int n) { return Math.round(n * context.getResources().getDisplayMetrics().density); }
    GradientDrawable shape(int color, int radius) {
        GradientDrawable shape = new GradientDrawable(); shape.setColor(color); shape.setCornerRadius(dp(radius)); return shape;
    }
    void button(Button button, boolean chosen, boolean primary) {
        int foreground = primary ? Color.WHITE : chosen ? accent : text;
        int fill = primary ? 0xff3367e8 : chosen ? selected : soft;
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x223367e8), shape(fill, 16), shape(Color.WHITE, 16)));
        button.setTextColor(foreground); button.setSelected(chosen);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        button.setCompoundDrawablePadding(dp(7));
        String name = button.getText().toString();
        Icon icon = new Icon(name, foreground); icon.setBounds(0, 0, dp(18), dp(18));
        button.setCompoundDrawables(icon, null, null, null);
    }
    private static class Icon extends Drawable {
        private final Paint p = new Paint(3);
        private final String name;
        private final int color;
        Icon(String name, int color) { this.name = name; this.color = color; }
        private void line(Canvas c, float x, float y, float ex, float ey) { c.drawLine(x, y, ex, ey, p); }
        @Override public void draw(Canvas canvas) {
            canvas.save(); canvas.translate(getBounds().left, getBounds().top); canvas.scale(getBounds().width()/24f, getBounds().height()/24f);
            p.setColor(color); p.setStrokeWidth(1.8f); p.setStyle(Paint.Style.STROKE); p.setStrokeCap(Paint.Cap.ROUND); p.setStrokeJoin(Paint.Join.ROUND);
            switch (name) {
                case "Region": case "Capture now": case "Tools ›":
                    line(canvas, 8, 3, 3, 3); line(canvas, 3, 3, 3, 8); line(canvas, 16, 3, 21, 3); line(canvas, 21, 3, 21, 8);
                    line(canvas, 3, 16, 3, 21); line(canvas, 3, 21, 8, 21); line(canvas, 16, 21, 21, 21); line(canvas, 21, 21, 21, 16); break;
                case "Pen": case "Highlight":
                    Path pen = new Path(); pen.moveTo(4, 20); pen.lineTo(6, 14); pen.lineTo(16, 4); pen.lineTo(20, 8); pen.lineTo(10, 18); pen.close(); canvas.drawPath(pen, p); line(canvas, 14, 6, 18, 10); break;
                case "Line": line(canvas, 4, 20, 20, 4); break;
                case "Arrow": line(canvas, 4, 20, 20, 4); line(canvas, 11, 4, 20, 4); line(canvas, 20, 4, 20, 13); break;
                case "Box": canvas.drawRoundRect(4, 5, 20, 19, 2, 2, p); break;
                case "Ellipse": canvas.drawOval(3, 5, 21, 19, p); break;
                case "Measure": canvas.drawRoundRect(3, 7, 21, 17, 2, 2, p); for (int x = 7; x < 20; x += 4) line(canvas, x, 7, x, 11); break;
                case "Picker": line(canvas, 5, 19, 17, 7); line(canvas, 13, 5, 19, 11); canvas.drawCircle(18, 6, 3, p); line(canvas, 4, 20, 8, 20); break;
                case "Redact": p.setStyle(Paint.Style.FILL); canvas.drawRoundRect(3, 7, 21, 17, 3, 3, p); break;
                case "Pixelate": for (int x = 4; x < 20; x += 6) for (int y = 4; y < 20; y += 6) canvas.drawRect(x, y, x+3, y+3, p); break;
                case "Step": canvas.drawCircle(12, 12, 9, p); p.setStyle(Paint.Style.FILL); p.setTextSize(14); p.setTypeface(Typeface.DEFAULT_BOLD); canvas.drawText("1", 8, 17, p); break;
                case "Text": line(canvas, 4, 5, 20, 5); line(canvas, 12, 5, 12, 20); line(canvas, 8, 20, 16, 20); break;
                case "Save PNG": canvas.drawRoundRect(4, 3, 20, 21, 2, 2, p); canvas.drawRect(8, 3, 16, 9, p); canvas.drawRect(8, 14, 16, 21, p); break;
                case "Share PNG": canvas.drawCircle(18, 4, 3, p); canvas.drawCircle(5, 12, 3, p); canvas.drawCircle(18, 20, 3, p); line(canvas, 8, 10, 15, 6); line(canvas, 8, 14, 15, 18); break;
                case "Undo": case "Redo":
                    if (name.equals("Redo")) { canvas.scale(-1, 1, 12, 12); }
                    canvas.drawArc(5, 7, 21, 23, 200, 225, false, p); line(canvas, 4, 6, 4, 13); line(canvas, 4, 13, 11, 13); break;
                case "Close editor": line(canvas, 6, 6, 18, 18); line(canvas, 18, 6, 6, 18); break;
                case "Hide tools": line(canvas, 15, 5, 8, 12); line(canvas, 8, 12, 15, 19); break;
                case "Hide actions": line(canvas, 9, 5, 16, 12); line(canvas, 16, 12, 9, 19); break;
                default:
                    if (name.endsWith(" ink")) {
                        int ink = name.startsWith("Red") ? 0xffff5064 : name.startsWith("Mint") ? 0xff55dfbb : name.startsWith("Yellow") ? 0xffffdd55 : name.startsWith("White") ? Color.WHITE : name.startsWith("Black") ? Color.BLACK : 0xff60aaff;
                        p.setStyle(Paint.Style.FILL); p.setColor(ink); canvas.drawCircle(12, 12, 8, p); p.setColor(0xff9696a0); p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(1); canvas.drawCircle(12, 12, 8, p);
                    } else if (name.startsWith("Size")) {
                        p.setStrokeWidth(name.contains("28") ? 6 : name.contains("16") ? 4 : name.contains("8") ? 2.5f : 1.5f); line(canvas, 4, 17, 20, 7);
                    } else {
                        line(canvas, 5, 6, 19, 6); line(canvas, 5, 12, 19, 12); line(canvas, 5, 18, 19, 18);
                        canvas.drawCircle(9, 6, 2, p); canvas.drawCircle(15, 12, 2, p); canvas.drawCircle(9, 18, 2, p);
                    }
            }
            canvas.restore();
        }
        @Override public void setAlpha(int alpha) { p.setAlpha(alpha); }
        @Override public void setColorFilter(ColorFilter filter) { p.setColorFilter(filter); }
        @Override public int getIntrinsicWidth() { return getBounds().width(); }
        @Override public int getIntrinsicHeight() { return getBounds().height(); }
        @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
    }
}
