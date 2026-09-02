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
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MobileActivity extends Activity {
    private static final String API = "https://api.masterxcloud.shop/mobile/v1";
    private static final String PREFS = "master_xcloud_mobile";
    private static final int BG = Color.rgb(2,7,11), CARD = Color.rgb(7,18,24), WHITE = Color.WHITE;
    private static final int MUTED = Color.rgb(142,160,169), GREEN = Color.rgb(34,255,102), CYAN = Color.rgb(0,223,245), RED = Color.rgb(255,90,90);
    private SharedPreferences prefs;
    private String token;
    private boolean busy;

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        token = prefs.getString("token", "");
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        splash();
    }

    private void splash() {
        LinearLayout r = root(); r.setGravity(Gravity.CENTER);
        r.addView(text("MASTER", 38, WHITE, true)); r.addView(text("XCLOUD", 38, GREEN, true));
        r.addView(space(10)); r.addView(text("MOBILE NATIVE", 12, CYAN, true)); setContentView(r);
        r.postDelayed(this::restore, 700);
    }

    private void restore() {
        if (token.isEmpty()) { login("Informe sua conta do XCloud."); return; }
        request("GET", "/auth/session", null, token, x -> {
            if (x.ok) dashboard("Sessão ativa"); else { clear(); login("Sessão expirada. Entre novamente."); }
        });
    }

    private void login(String initial) {
        LinearLayout r = page();
        r.addView(text("MASTER XCLOUD", 30, GREEN, true));
        r.addView(text("LOGIN NATIVO", 12, MUTED, true)); r.addView(space(8));
        TextView status = text(initial, 12, CYAN, false); r.addView(status); r.addView(space(22));
        EditText email = field("E-mail", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        email.setText(prefs.getString("email", ""));
        EditText pass = field("Senha", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        r.addView(email); r.addView(space(12)); r.addView(pass); r.addView(space(18));
        Button enter = button("ENTRAR", GREEN); r.addView(enter); r.addView(space(10));
        Button health = button("TESTAR SERVIDOR", CARD); health.setTextColor(WHITE); r.addView(health); r.addView(space(18));
        TextView ver = text("MASTER XCLOUD • v0.5.0", 11, MUTED, false); ver.setGravity(Gravity.CENTER); r.addView(ver);

        health.setOnClickListener(v -> {
            if (busy) return; status.setText("Verificando servidor...");
            request("GET", "/health", null, "", x -> status.setText(x.ok ? "Servidor mobile online." : x.message));
        });
        enter.setOnClickListener(v -> {
            if (busy) return;
            String e = email.getText().toString().trim(), p = pass.getText().toString();
            if (e.isEmpty() || p.isEmpty()) { status.setText("Preencha e-mail e senha."); return; }
            try {
                JSONObject body = new JSONObject(); body.put("email", e); body.put("password", p);
                enter.setEnabled(false); status.setText("Autenticando diretamente no XCloud...");
                request("POST", "/auth/login", body, "", x -> {
                    enter.setEnabled(true);
                    if (!x.ok) { status.setText(x.message); return; }
                    token = x.data.optString("token", "");
                    if (token.isEmpty()) { status.setText("Sessão inválida retornada pelo servidor."); return; }
                    prefs.edit().putString("token", token).putString("email", e).apply();
                    dashboard("Conectado");
                });
            } catch (Exception ex) { enter.setEnabled(true); status.setText("Falha ao preparar login."); }
        });
    }

    private void dashboard(String state) {
        LinearLayout r = page();
        r.addView(text("MASTER XCLOUD", 28, GREEN, true));
        r.addView(text(prefs.getString("email", "Conta conectada"), 13, WHITE, false)); r.addView(space(6));
        r.addView(text("● " + state, 12, CYAN, true)); r.addView(space(20));
        TextView activate = card("⚡  NOVA ATIVAÇÃO", "Device Key / MAC + M3U / DNS"); r.addView(activate);
        TextView history = card("🕘  HISTÓRICO LOCAL", "Última ativação realizada neste aparelho"); r.addView(history);
        r.addView(space(12));
        Button logout = button("SAIR", CARD); logout.setTextColor(WHITE); r.addView(logout);
        activate.setOnClickListener(v -> activation());
        history.setOnClickListener(v -> history());
        logout.setOnClickListener(v -> doLogout());
    }

    private void activation() {
        LinearLayout r = page();
        TextView back = text("‹ VOLTAR", 14, CYAN, true); back.setOnClickListener(v -> dashboard("Sessão ativa")); r.addView(back); r.addView(space(14));
        r.addView(text("ATIVAÇÃO NATIVA", 26, GREEN, true));
        r.addView(text("O aplicativo envia os dados direto para a API mobile, sem abrir ou carregar a interface web.", 13, MUTED, false)); r.addView(space(20));
        EditText device = field("Device Key / MAC", InputType.TYPE_CLASS_TEXT);
        EditText playlist = field("M3U / DNS", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        r.addView(device); r.addView(space(12)); r.addView(playlist); r.addView(space(16));
        TextView stage = text("1/3 • Pronto para iniciar", 13, MUTED, true); r.addView(stage); r.addView(space(8));
        ProgressBar pb = new ProgressBar(this); pb.setVisibility(View.GONE); r.addView(pb); r.addView(space(10));
        Button go = button("ATIVAR AGORA", GREEN); r.addView(go);
        go.setOnClickListener(v -> {
            if (busy) return;
            String d = device.getText().toString().trim().toUpperCase(), p = playlist.getText().toString().trim();
            if (d.isEmpty()) { stage.setTextColor(RED); stage.setText("Informe o Device Key / MAC."); return; }
            if (p.isEmpty()) { stage.setTextColor(RED); stage.setText("Informe a M3U / DNS."); return; }
            try {
                JSONObject body = new JSONObject(); body.put("device", d); body.put("playlist", p);
                go.setEnabled(false); pb.setVisibility(View.VISIBLE); stage.setTextColor(CYAN); stage.setText("2/3 • Enviando dispositivo e configurando DNS...");
                request("POST", "/operations/activate", body, token, x -> {
                    go.setEnabled(true); pb.setVisibility(View.GONE);
                    if (!x.ok) {
                        stage.setTextColor(RED); stage.setText("Falha • " + x.message);
                        if (x.status == 401) { clear(); r.postDelayed(() -> login("Sessão expirada."), 1200); }
                        return;
                    }
                    String msg = x.data.optString("message", "Ativação concluída.");
                    int total = 0; JSONObject t = x.data.optJSONObject("timing_ms"); if (t != null) total = t.optInt("total", 0);
                    prefs.edit().putString("last_device", d).putString("last_result", msg).putLong("last_at", System.currentTimeMillis()).apply();
                    stage.setTextColor(GREEN); stage.setText("3/3 • ✓ " + msg + (total > 0 ? "\nTempo: " + total + " ms" : ""));
                    device.setText(""); playlist.setText(""); go.setText("NOVA ATIVAÇÃO");
                });
            } catch (Exception ex) { go.setEnabled(true); pb.setVisibility(View.GONE); stage.setTextColor(RED); stage.setText("Falha ao preparar ativação."); }
        });
    }

    private void history() {
        LinearLayout r = page(); TextView back = text("‹ VOLTAR", 14, CYAN, true); back.setOnClickListener(v -> dashboard("Sessão ativa")); r.addView(back); r.addView(space(14));
        r.addView(text("HISTÓRICO LOCAL", 26, GREEN, true)); r.addView(space(18));
        String d = prefs.getString("last_device", "Nenhuma ativação registrada"); String res = prefs.getString("last_result", "");
        r.addView(card("ÚLTIMA ATIVAÇÃO", d + (res.isEmpty() ? "" : "\n" + res)));
    }

    private void doLogout() {
        if (busy) return;
        if (token.isEmpty()) { clear(); login("Sessão encerrada."); return; }
        request("POST", "/auth/logout", new JSONObject(), token, x -> { clear(); login("Sessão encerrada."); });
    }

    private void clear() { token = ""; prefs.edit().remove("token").apply(); }

    private interface Callback { void done(Result r); }
    private static class Result { boolean ok; int status; String message; JSONObject data = new JSONObject(); }

    private void request(String method, String path, JSONObject body, String bearer, Callback cb) {
        if (busy) return; busy = true;
        new Thread(() -> {
            Result out = new Result(); out.message = "Não foi possível conectar ao servidor."; HttpURLConnection c = null;
            try {
                c = (HttpURLConnection) new URL(API + path).openConnection(); c.setRequestMethod(method); c.setConnectTimeout(15000); c.setReadTimeout(120000);
                c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                if (bearer != null && !bearer.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + bearer);
                if (body != null && !"GET".equals(method)) { c.setDoOutput(true); try (OutputStream os = c.getOutputStream()) { os.write(body.toString().getBytes(StandardCharsets.UTF_8)); } }
                out.status = c.getResponseCode(); InputStream is = out.status >= 200 && out.status < 300 ? c.getInputStream() : c.getErrorStream(); String raw = read(is);
                if (!raw.isEmpty()) try { out.data = new JSONObject(raw); } catch (Exception ignored) {}
                out.ok = out.status >= 200 && out.status < 300; out.message = out.ok ? out.data.optString("message", "OK") : out.data.optString("detail", "Erro HTTP " + out.status);
            } catch (Exception e) { out.message = "Não foi possível conectar ao servidor. Tente novamente."; }
            finally { if (c != null) c.disconnect(); Result f = out; runOnUiThread(() -> { busy = false; cb.done(f); }); }
        }).start();
    }

    private String read(InputStream is) throws Exception { if (is == null) return ""; StringBuilder s = new StringBuilder(); try (BufferedReader b = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) { String l; while ((l = b.readLine()) != null) s.append(l); } return s.toString(); }
    private LinearLayout root() { LinearLayout l = new LinearLayout(this); l.setOrientation(LinearLayout.VERTICAL); l.setBackgroundColor(BG); return l; }
    private LinearLayout page() { ScrollView s = new ScrollView(this); s.setBackgroundColor(BG); LinearLayout l = root(); l.setPadding(dp(24), dp(28), dp(24), dp(28)); s.addView(l); setContentView(s); return l; }
    private TextView text(String t, int sp, int color, boolean bold) { TextView v = new TextView(this); v.setText(t); v.setTextSize(sp); v.setTextColor(color); if (bold) v.setTypeface(Typeface.DEFAULT_BOLD); return v; }
    private EditText field(String h, int type) { EditText e = new EditText(this); e.setHint(h); e.setHintTextColor(MUTED); e.setTextColor(WHITE); e.setInputType(type); e.setSingleLine(true); e.setPadding(dp(14),0,dp(14),0); e.setBackgroundColor(CARD); e.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(56))); return e; }
    private Button button(String t, int color) { Button b = new Button(this); b.setText(t); b.setTypeface(Typeface.DEFAULT_BOLD); b.setTextColor(BG); b.setBackgroundColor(color); b.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(54))); return b; }
    private TextView card(String a, String b) { TextView v = text(a + "\n" + b, 16, WHITE, true); v.setPadding(dp(18),dp(16),dp(18),dp(16)); v.setBackgroundColor(CARD); LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, dp(94)); p.setMargins(0,0,0,dp(14)); v.setLayoutParams(p); v.setGravity(Gravity.CENTER_VERTICAL); return v; }
    private View space(int h) { View v = new View(this); v.setLayoutParams(new LinearLayout.LayoutParams(1, dp(h))); return v; }
    private int dp(int x) { return Math.round(x * getResources().getDisplayMetrics().density); }
}
