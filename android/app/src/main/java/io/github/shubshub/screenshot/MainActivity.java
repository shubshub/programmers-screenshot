package io.github.shubshub.screenshot;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.content.Intent;
import android.provider.Settings;
import android.graphics.Typeface;
import android.view.Gravity;
import android.widget.*;

public class MainActivity extends Activity {
    private TextView status;
    private Appearance look;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state); look = new Appearance(this);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true); scroll.setBackgroundColor(look.background);
        scroll.setVerticalScrollBarEnabled(false);
        layout.setOnApplyWindowInsetsListener((v, insets) -> {
            android.graphics.Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
            v.setPadding(look.dp(24) + bars.left, bars.top, look.dp(24) + bars.right, look.dp(28) + bars.bottom); return insets;
        });
        LinearLayout hero = new LinearLayout(this); hero.setOrientation(LinearLayout.VERTICAL); hero.setGravity(Gravity.BOTTOM);
        hero.setPadding(look.dp(8), look.dp(64), 0, look.dp(32));
        text(hero, "PROGRAMMERS SCREENSHOT", 11, look.secondary, false).setLetterSpacing(.12f);
        TextView title = text(hero, "Your screen.\nYour markup.", 38, look.text, true); title.setLineSpacing(0, 1.02f);
        text(hero, "Capture a moment. Make it clear.", 15, look.secondary, false);
        layout.addView(hero);
        LinearLayout capture = card(layout);
        status = text(capture, "Ready to capture", 18, look.text, true);
        text(capture, "Press Side + Volume Up from any app,\nor start a capture below.", 14, look.secondary, false);
        Button start = action(capture, "Capture now", true);
        start.setOnClickListener(v -> {
            if (CaptureService.instance == null) { startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)); return; }
            v.performHapticFeedback(android.view.HapticFeedbackConstants.KEYBOARD_TAP); moveTaskToBack(true);
            new Handler(getMainLooper()).postDelayed(() -> { if (CaptureService.instance != null) CaptureService.instance.capture(); }, 1000);
        });
        LinearLayout shortcuts = card(layout);
        text(shortcuts, "Make it a shortcut", 19, look.text, true);
        instruction(shortcuts, "1", "Enable screenshot access", "Accessibility → Installed apps →\nProgrammers Screenshot");
        instruction(shortcuts, "2", "Choose your buttons", "Accessibility → Advanced settings →\nSide and Volume up buttons");
        instruction(shortcuts, "3", "Swipe. Edit. Save.", "Swipe from the left for tools, or the right\nfor colours, sizes and sharing.");
        action(shortcuts, "Accessibility settings", false).setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        TextView privacy = text(layout, "On your phone. Just for you.\nScreenshots stay local. Protected screens cannot be captured.", 12, look.secondary, false);
        privacy.setGravity(Gravity.CENTER); privacy.setPadding(look.dp(12), look.dp(12), look.dp(12), 0);
        scroll.addView(layout); setContentView(scroll);
    }
    private TextView text(LinearLayout parent, String value, int size, int color, boolean medium) {
        TextView view = new TextView(this); view.setText(value); view.setTextSize(size); view.setTextColor(color);
        view.setTypeface(Typeface.create(medium ? "sans-serif-medium" : "sans-serif", Typeface.NORMAL));
        view.setPadding(0, look.dp(4), 0, look.dp(8)); view.setLineSpacing(look.dp(3), 1);
        parent.addView(view, new LinearLayout.LayoutParams(-1, -2)); return view;
    }
    private LinearLayout card(LinearLayout parent) {
        LinearLayout card = new LinearLayout(this); card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(look.dp(20), look.dp(18), look.dp(20), look.dp(20)); card.setBackground(look.shape(look.surface, 28));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2); params.bottomMargin = look.dp(16);
        parent.addView(card, params); return card;
    }
    private Button action(LinearLayout parent, String name, boolean primary) {
        Button button = new Button(this); button.setText(name); button.setTextSize(14); button.setAllCaps(false); button.setStateListAnimator(null);
        button.setPadding(look.dp(18), 0, look.dp(18), 0); look.button(button, false, primary);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, look.dp(52)); params.topMargin = look.dp(12);
        parent.addView(button, params); return button;
    }
    private void instruction(LinearLayout parent, String number, String title, String detail) {
        LinearLayout row = new LinearLayout(this); row.setGravity(Gravity.TOP); row.setPadding(0, look.dp(12), 0, look.dp(4));
        TextView badge = new TextView(this); badge.setText(number); badge.setGravity(Gravity.CENTER); badge.setTextColor(look.accent);
        badge.setTextSize(14); badge.setTypeface(Typeface.DEFAULT_BOLD); badge.setBackground(look.shape(look.selected, 12));
        row.addView(badge, new LinearLayout.LayoutParams(look.dp(32), look.dp(32)));
        LinearLayout words = new LinearLayout(this); words.setOrientation(LinearLayout.VERTICAL); words.setPadding(look.dp(12), 0, 0, 0);
        text(words, title, 15, look.text, true); text(words, detail, 12, look.secondary, false);
        row.addView(words, new LinearLayout.LayoutParams(0, -2, 1)); parent.addView(row);
    }
    @Override public void onResume() {
        super.onResume();
        if (status != null) status.setText(CaptureService.instance == null ? "Set up your first capture" : "Ready when you are");
    }
}
