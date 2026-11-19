package io.github.shubshub.screenshot;

import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.ArrayList;

/** Two independently scrollable edge panels over the full-size screenshot canvas. */
@android.annotation.SuppressLint({"ViewConstructor", "RtlHardcoded"}) // Physical left/right edges intentionally match the swipe directions in every locale.
public class EditorControls extends FrameLayout {
    private final EditorActivity activity;
    private final EditorView editor;
    private final Appearance look;
    final ScrollView left, right;
    private final Button toolsHandle, actionsHandle;
    private final ArrayList<Button> toolButtons = new ArrayList<>(), colorButtons = new ArrayList<>(), sizeButtons = new ArrayList<>();
    private final int[] colors = {0xffff5064, 0xff55dfbb, 0xffffdd55, Color.WHITE, Color.BLACK, 0xff60aaff};
    private final int[] sizes = {4, 8, 16, 28};
    private float downX, downY;
    private boolean edgeGesture, dragging;

    public EditorControls(EditorActivity activity, EditorView editor, Runnable close, Runnable save, Runnable share) {
        super(activity); this.activity = activity; this.editor = editor; look = new Appearance(activity);
        setBackgroundColor(look.background);
        addView(editor, new LayoutParams(-1, -1));
        left = panel(Gravity.LEFT); right = panel(Gravity.RIGHT);
        LinearLayout tools = (LinearLayout)left.getChildAt(0), actions = (LinearLayout)right.getChildAt(0);
        heading(tools, "Tools", false);
        addButton(tools, "Hide tools", () -> showPanel(true, false));
        heading(tools, "EDIT IMAGE", true);
        for (String tool : EditorView.TOOLS) {
            Button button = addButton(tools, tool, () -> { editor.selectTool(tool); updateSelection(); });
            toolButtons.add(button);
        }
        heading(actions, "Actions", false);
        addButton(actions, "Hide actions", () -> showPanel(false, false));
        heading(actions, "SCREENSHOT", true);
        addButton(actions, "Save PNG", save); addButton(actions, "Share PNG", share);
        addButton(actions, "Undo", editor::undo); addButton(actions, "Redo", editor::redo);
        addButton(actions, "Close editor", close);
        heading(actions, "INK COLOUR", true);
        String[] names = {"Red ink", "Mint ink", "Yellow ink", "White ink", "Black ink", "Blue ink"};
        for (int i = 0; i < colors.length; i++) {
            final int color = colors[i];
            colorButtons.add(addButton(actions, names[i], () -> { editor.ink = color; updateSelection(); }));
        }
        heading(actions, "STROKE SIZE", true);
        for (int size : sizes) sizeButtons.add(addButton(actions, "Size " + size + " px", () -> { editor.width = size; updateSelection(); }));
        toolsHandle = handle("Tools ›", Gravity.LEFT, () -> showPanel(true, true));
        actionsHandle = handle("‹ Actions", Gravity.RIGHT, () -> showPanel(false, true));
        showPanel(true, false); showPanel(false, false); updateSelection();
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private ScrollView panel(int side) {
        ScrollView scroll = new ScrollView(activity); scroll.setFillViewport(false);
        scroll.setContentDescription(side == Gravity.LEFT ? "Tools panel, scroll vertically" : "Actions, colours and sizes panel, scroll vertically");
        scroll.setBackground(look.shape(look.surface, 26)); scroll.setClipToOutline(true); scroll.setElevation(dp(6));
        scroll.setVerticalScrollBarEnabled(false); scroll.setOverScrollMode(OVER_SCROLL_NEVER);
        LinearLayout list = new LinearLayout(activity); list.setOrientation(LinearLayout.VERTICAL); list.setPadding(dp(8), dp(16), dp(8), dp(12));
        scroll.addView(list, new ScrollView.LayoutParams(-1, -2));
        LayoutParams params = new LayoutParams(dp(128), -1, side | Gravity.TOP);
        params.topMargin = dp(8); params.bottomMargin = dp(64);
        if (side == Gravity.LEFT) params.leftMargin = dp(8); else params.rightMargin = dp(8);
        addView(scroll, params); return scroll;
    }
    private void heading(LinearLayout list, String text, boolean section) {
        TextView title = new TextView(activity); title.setText(text); title.setTextColor(section ? look.secondary : look.text);
        title.setTextSize(section ? 10 : 20); title.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        title.setPadding(dp(8), section ? dp(16) : 0, 0, dp(12));
        if (section) title.setLetterSpacing(.07f); else title.setAccessibilityHeading(true);
        list.addView(title);
    }
    private Button control(String name, Runnable action) {
        Button button = new Button(activity); button.setText(name); button.setContentDescription(name);
        button.setTextSize(12); button.setAllCaps(false); button.setMinWidth(0); button.setMinimumWidth(0);
        button.setMinHeight(0); button.setMinimumHeight(0); button.setPadding(dp(10), 0, dp(5), 0);
        button.setGravity(Gravity.CENTER_VERTICAL | Gravity.START); button.setStateListAnimator(null);
        button.setMaxLines(2); style(button, false);
        button.setOnClickListener(v -> { if (!activity.isSaving()) { v.performHapticFeedback(android.view.HapticFeedbackConstants.KEYBOARD_TAP); action.run(); } });
        return button;
    }
    private Button addButton(LinearLayout list, String name, Runnable action) {
        Button button = control(name, action);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(dp(112), dp(48)); params.bottomMargin = dp(6);
        list.addView(button, params); return button;
    }
    private Button handle(String name, int side, Runnable action) {
        Button button = control(name, action);
        LayoutParams params = new LayoutParams(dp(112), dp(48), side | Gravity.BOTTOM); params.bottomMargin = dp(8);
        if (side == Gravity.LEFT) params.leftMargin = dp(8); else params.rightMargin = dp(8);
        addView(button, params); button.setElevation(dp(4)); return button;
    }
    private void style(Button button, boolean selected) {
        look.button(button, selected, button.getText().toString().equals("Save PNG"));
    }
    private void updateSelection() {
        for (int i = 0; i < toolButtons.size(); i++) style(toolButtons.get(i), editor.tool.equals(EditorView.TOOLS[i]));
        for (int i = 0; i < colorButtons.size(); i++) style(colorButtons.get(i), editor.ink == colors[i]);
        for (int i = 0; i < sizeButtons.size(); i++) style(sizeButtons.get(i), editor.width == sizes[i]);
    }
    void showPanel(boolean isLeft, boolean show) {
        ScrollView panel = isLeft ? left : right;
        panel.animate().cancel();
        boolean opening = show && panel.getVisibility() != VISIBLE;
        panel.setVisibility(show ? VISIBLE : GONE);
        if (opening && isAttachedToWindow()) {
            panel.setTranslationX(dp(isLeft ? -24 : 24)); panel.setAlpha(0);
            panel.animate().translationX(0).alpha(1).setDuration(180).setInterpolator(new android.view.animation.DecelerateInterpolator()).start();
        } else { panel.setTranslationX(0); panel.setAlpha(1); }
        (isLeft ? toolsHandle : actionsHandle).setVisibility(show ? GONE : VISIBLE);
    }
    @Override public boolean onInterceptTouchEvent(MotionEvent event) {
        float x = event.getX(), y = event.getY();
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
            downX = x; downY = y; dragging = false;
            edgeGesture = x < getPaddingLeft() + dp(28) || x > getWidth() - getPaddingRight() - dp(28)
                || (left.getVisibility() == VISIBLE && x < getPaddingLeft() + dp(136))
                || (right.getVisibility() == VISIBLE && x > getWidth() - getPaddingRight() - dp(136));
        } else if (event.getActionMasked() == MotionEvent.ACTION_MOVE && edgeGesture) {
            float dx = x - downX, dy = y - downY;
            if (Math.abs(dx) > dp(36) && Math.abs(dx) > Math.abs(dy) * 1.5f) {
                boolean fromLeft = downX < getWidth() / 2f;
                showPanel(fromLeft, fromLeft ? dx > 0 : dx < 0);
                dragging = true; return true; // Android sends ACTION_CANCEL to the canvas/scroll view.
            }
        }
        return super.onInterceptTouchEvent(event);
    }
    @Override public void requestDisallowInterceptTouchEvent(boolean disallow) {
        // Preserve edge swipes even when the drawing canvas starts a provisional stroke.
        if (!edgeGesture || !disallow) super.requestDisallowInterceptTouchEvent(disallow);
    }
    @android.annotation.SuppressLint("ClickableViewAccessibility") // This surface handles swipes only; all click actions use labelled native buttons.
    @Override public boolean onTouchEvent(MotionEvent event) {
        // Keep edge gestures alive over letterboxed space where the canvas rejects DOWN.
        if (edgeGesture && event.getActionMasked() == MotionEvent.ACTION_MOVE && !dragging) onInterceptTouchEvent(event);
        return edgeGesture || dragging || super.onTouchEvent(event);
    }
    @Override public boolean performClick() { return super.performClick(); }
}
