package com.masterxcloud.app;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final String PREFS = "master_xcloud";
    private static final int BG = Color.rgb(2,7,11);
    private static final int CARD = Color.rgb(6,16,21);
    private static final int WHITE = Color.WHITE;
    private static final int MUTED = Color.rgb(142,160,169);
    private static final int GREEN = Color.rgb(34,255,102);
    private static final int CYAN = Color.rgb(0,223,245);
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        showSplash();
    }

    private void showSplash() {
        LinearLayout root = base();
        root.setGravity(Gravity.CENTER);
        TextView master = label("MASTER", 38, WHITE, true);
        TextView xcloud = label("XCLOUD", 38, GREEN, true);
        TextView sub = label("PAINEL MOBILE", 12, CYAN, true);
        root.addView(master);
        root.addView(xcloud);
        root.addView(space(14));
        root.addView(sub);
        setContentView(root);
        root.postDelayed(() -> {
            if (prefs.getBoolean("logged_in", false)) showDashboard();
            else showLogin();
        }, 1000);
    }

    private void showLogin() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout root = base();
        root.setPadding(dp(28), dp(36), dp(28), dp(28));
        scroll.addView(root);

        root.addView(label("MASTER XCLOUD", 30, GREEN, true));
        root.addView(label("ACESSO AO PAINEL", 12, MUTED, false));
        root.addView(space(28));

        EditText server = field("https://seu-painel.com", InputType.TYPE_TEXT_VARIATION_URI);
        server.setText(prefs.getString("server_url", ""));
        EditText user = field("Usuário", InputType.TYPE_CLASS_TEXT);
        EditText pass = field("Senha", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        root.addView(server);
        root.addView(space(12));
        root.addView(user);
        root.addView(space(12));
        root.addView(pass);
        root.addView(space(18));

        Button login = button("ENTRAR", GREEN);
        login.setOnClickListener(v -> {
            String s = server.getText().toString().trim();
            String u = user.getText().toString().trim();
            String p = pass.getText().toString();
            if (s.isEmpty() || u.isEmpty() || p.isEmpty()) {
                Toast.makeText(this, "Preencha servidor, usuário e senha.", Toast.LENGTH_SHORT).show();
                return;
            }
            prefs.edit().putString("server_url", s).putString("user_name", u).putBoolean("logged_in", true).apply();
            showDashboard();
        });
        root.addView(login);
        root.addView(space(18));
        TextView version = label("Versão inicial 0.1.0", 11, MUTED, false);
        version.setGravity(Gravity.CENTER);
        root.addView(version);
        setContentView(scroll);
    }

    private void showDashboard() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        LinearLayout root = base();
        root.setPadding(dp(22), dp(24), dp(22), dp(24));
        scroll.addView(root);

        root.addView(label("MASTER XCLOUD", 28, GREEN, true));
        root.addView(label("Olá, " + prefs.getString("user_name", "Revendedor"), 15, WHITE, false));
        root.addView(space(18));

        root.addView(card("☁  PAINEL", "Visão geral da sua operação"));
        root.addView(card("👥  CLIENTES", "Gerencie acessos e usuários"));
        root.addView(card("📺  DISPOSITIVOS", "Ativações e equipamentos"));
        root.addView(card("⚡  AUTOMAÇÃO", "Rotinas do Master XCloud"));
        root.addView(card("⚙  CONFIGURAÇÕES", "Servidor, conta e preferências"));
        root.addView(space(18));

        Button logout = button("SAIR", CARD);
        logout.setTextColor(WHITE);
        logout.setOnClickListener(v -> {
            prefs.edit().putBoolean("logged_in", false).apply();
            showLogin();
        });
        root.addView(logout);
        setContentView(scroll);
    }

    private TextView card(String title, String subtitle) {
        TextView v = label(title + "\n" + subtitle, 16, WHITE, true);
        v.setPadding(dp(18), dp(16), dp(18), dp(16));
        v.setBackgroundColor(CARD);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, dp(88));
        lp.setMargins(0, 0, 0, dp(14));
        v.setLayoutParams(lp);
        v.setGravity(Gravity.CENTER_VERTICAL);
        v.setOnClickListener(x -> Toast.makeText(this, title.replaceAll("[^A-ZÁÉÍÓÚÇ ]", "").trim() + " — próxima etapa", Toast.LENGTH_SHORT).show());
        return v;
    }

    private LinearLayout base() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setBackgroundColor(BG);
        return l;
    }

    private EditText field(String hint, int type) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setHintTextColor(MUTED);
        e.setTextColor(WHITE);
        e.setSingleLine(true);
        e.setInputType(type);
        e.setPadding(dp(14), 0, dp(14), 0);
        e.setBackgroundColor(CARD);
        e.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(56)));
        return e;
    }

    private Button button(String text, int color) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextColor(BG);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setBackgroundColor(color);
        b.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(54)));
        return b;
    }

    private TextView label(String text, int sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private View space(int h) {
        View v = new View(this);
        v.setLayoutParams(new LinearLayout.LayoutParams(1, dp(h)));
        return v;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
