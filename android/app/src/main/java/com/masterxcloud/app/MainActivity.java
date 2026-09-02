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
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private static final String PREFS = "master_xcloud";
    private static final String API_URL = "https://api.masterxcloud.shop";
    private static final int BG = Color.rgb(2,7,11);
    private static final int CARD = Color.rgb(6,16,21);
    private static final int WHITE = Color.WHITE;
    private static final int MUTED = Color.rgb(142,160,169);
    private static final int GREEN = Color.rgb(34,255,102);
    private static final int CYAN = Color.rgb(0,223,245);
    private static final int RED = Color.rgb(255,80,80);

    private SharedPreferences prefs;
    private String token = "";
    private int operations = 0;
    private boolean requestRunning = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        token = prefs.getString("auth_token", "");
        operations = prefs.getInt("operations", 0);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        showSplash();
    }

    private void showSplash() {
        LinearLayout root = base();
        root.setGravity(Gravity.CENTER);
        root.addView(label("MASTER", 38, WHITE, true));
        root.addView(label("XCLOUD", 38, GREEN, true));
        root.addView(space(14));
        root.addView(label("PAINEL MOBILE", 12, CYAN, true));
        setContentView(root);
        root.postDelayed(this::restoreSession, 800);
    }

    private void restoreSession() {
        if (token.isEmpty()) {
            showLogin("Conecte sua conta do Master XCloud.");
            return;
        }
        api("GET", "/auth/session", null, token, result -> {
            if (result.ok) showDashboard("Servidor online • sessão ativa");
            else {
                clearSession();
                showLogin("Sua sessão expirou. Entre novamente.");
            }
        });
    }

    private void showLogin(String statusText) {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout root = base();
        root.setPadding(dp(28), dp(36), dp(28), dp(28));
        scroll.addView(root);

        root.addView(label("MASTER XCLOUD", 30, GREEN, true));
        root.addView(label("ACESSO AO PAINEL", 12, MUTED, false));
        root.addView(space(10));
        TextView serverState = label(statusText, 12, CYAN, false);
        root.addView(serverState);
        root.addView(space(26));

        EditText email = field("E-mail", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        email.setText(prefs.getString("login_email", ""));
        EditText pass = field("Senha", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        root.addView(email);
        root.addView(space(12));
        root.addView(pass);
        root.addView(space(18));

        Button login = button("ENTRAR", GREEN);
        root.addView(login);
        root.addView(space(12));

        Button check = button("VERIFICAR SERVIDOR", CARD);
        check.setTextColor(WHITE);
        root.addView(check);
        root.addView(space(18));

        TextView version = label("MASTER XCLOUD • v0.4.0", 11, MUTED, false);
        version.setGravity(Gravity.CENTER);
        root.addView(version);

        check.setOnClickListener(v -> {
            if (requestRunning) return;
            serverState.setText("Verificando servidor...");
            api("GET", "/health", null, "", r -> serverState.setText(r.ok ? "Servidor online." : r.message));
        });

        login.setOnClickListener(v -> {
            if (requestRunning) return;
            String e = email.getText().toString().trim();
            String p = pass.getText().toString();
            if (e.isEmpty() || p.isEmpty()) {
                serverState.setText("Preencha e-mail e senha.");
                return;
            }
            login.setEnabled(false);
            serverState.setText("Conectando ao Master XCloud...");
            try {
                JSONObject body = new JSONObject();
                body.put("email", e);
                body.put("password", p);
                api("POST", "/auth/login", body, "", result -> {
                    login.setEnabled(true);
                    if (!result.ok) {
                        serverState.setText(result.message);
                        return;
                    }
                    String newToken = result.data.optString("token", "");
                    if (newToken.isEmpty()) {
                        serverState.setText("Servidor não retornou uma sessão válida.");
                        return;
                    }
                    token = newToken;
                    prefs.edit()
                            .putString("auth_token", token)
                            .putString("login_email", e)
                            .apply();
                    pass.setText("");
                    showDashboard("Conectado ao servidor");
                });
            } catch (Exception ex) {
                login.setEnabled(true);
                serverState.setText("Não foi possível preparar o login.");
            }
        });

        setContentView(scroll);
    }

    private void showDashboard(String state) {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        LinearLayout root = base();
        root.setPadding(dp(22), dp(24), dp(22), dp(24));
        scroll.addView(root);

        root.addView(label("MASTER XCLOUD", 28, GREEN, true));
        root.addView(label(prefs.getString("login_email", "Conta conectada"), 13, WHITE, false));
        root.addView(space(8));
        TextView apiState = label("● " + state, 12, CYAN, true);
        root.addView(apiState);
        root.addView(space(18));

        TextView ops = label("ATIVAÇÕES NESTE APP: " + operations, 13, MUTED, true);
        root.addView(ops);
        root.addView(space(14));

        TextView activationCard = card("⚡  ATIVAR DISPOSITIVO", "Adicionar Device Key / MAC + M3U / DNS");
        root.addView(activationCard);
        root.addView(cardDisabled("👥  CLIENTES", "Módulo será conectado na próxima etapa"));
        root.addView(cardDisabled("📺  DISPOSITIVOS", "Consulta será conectada na próxima etapa"));
        root.addView(cardDisabled("⚙  CONFIGURAÇÕES", "Conta e preferências"));
        root.addView(space(18));

        Button refresh = button("ATUALIZAR CONEXÃO", CARD);
        refresh.setTextColor(WHITE);
        refresh.setOnClickListener(v -> {
            if (requestRunning) return;
            apiState.setText("● Verificando sessão...");
            api("GET", "/auth/session", null, token, r -> {
                if (r.ok) apiState.setText("● Servidor online • sessão ativa");
                else {
                    clearSession();
                    showLogin("Sessão expirada. Entre novamente.");
                }
            });
        });
        root.addView(refresh);
        root.addView(space(10));

        Button logout = button("SAIR", CARD);
        logout.setTextColor(WHITE);
        logout.setOnClickListener(v -> logout());
        root.addView(logout);

        activationCard.setOnClickListener(v -> showActivation());
        setContentView(scroll);
    }

    private void showActivation() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        LinearLayout root = base();
        root.setPadding(dp(22), dp(24), dp(22), dp(24));
        scroll.addView(root);

        TextView back = label("‹ VOLTAR", 14, CYAN, true);
        back.setPadding(0, dp(8), 0, dp(8));
        back.setOnClickListener(v -> showDashboard("Servidor online • sessão ativa"));
        root.addView(back);
        root.addView(space(14));

        root.addView(label("ATIVAR DISPOSITIVO", 26, GREEN, true));
        root.addView(label("Adicione o dispositivo e configure a lista em uma única operação.", 13, MUTED, false));
        root.addView(space(20));

        EditText device = field("Device Key / MAC", InputType.TYPE_CLASS_TEXT);
        EditText playlist = field("M3U / DNS", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        root.addView(device);
        root.addView(space(12));
        root.addView(playlist);
        root.addView(space(18));

        TextView status = label("Pronto para ativar.", 13, MUTED, false);
        root.addView(status);
        root.addView(space(12));

        ProgressBar progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        root.addView(progress);
        root.addView(space(10));

        Button execute = button("ATIVAR AGORA", GREEN);
        root.addView(execute);

        execute.setOnClickListener(v -> {
            if (requestRunning) return;
            String dev = device.getText().toString().trim().toUpperCase();
            String list = playlist.getText().toString().trim();
            if (dev.isEmpty()) {
                status.setTextColor(RED);
                status.setText("Informe o Device Key / MAC.");
                return;
            }
            if (list.isEmpty()) {
                status.setTextColor(RED);
                status.setText("Informe a M3U / DNS.");
                return;
            }

            execute.setEnabled(false);
            progress.setVisibility(View.VISIBLE);
            status.setTextColor(CYAN);
            status.setText("Conectando ao painel e processando ativação...");
            try {
                JSONObject body = new JSONObject();
                body.put("device", dev);
                body.put("playlist", list);
                api("POST", "/operations/activate", body, token, result -> {
                    execute.setEnabled(true);
                    progress.setVisibility(View.GONE);
                    if (!result.ok) {
                        status.setTextColor(RED);
                        status.setText(result.message);
                        if (result.status == 401) {
                            clearSession();
                            root.postDelayed(() -> showLogin("Sessão expirada. Entre novamente."), 1500);
                        }
                        return;
                    }
                    operations++;
                    prefs.edit().putInt("operations", operations).apply();
                    status.setTextColor(GREEN);
                    String msg = result.data.optString("message", "Ativação concluída com sucesso.");
                    JSONObject timing = result.data.optJSONObject("timing_ms");
                    if (timing != null && timing.has("total")) {
                        msg += "\nTempo: " + timing.optInt("total") + " ms";
                    }
                    status.setText("✓ " + msg);
                    device.setText("");
                    playlist.setText("");
                    Toast.makeText(this, "Ativação concluída!", Toast.LENGTH_LONG).show();
                });
            } catch (Exception ex) {
                execute.setEnabled(true);
                progress.setVisibility(View.GONE);
                status.setTextColor(RED);
                status.setText("Não foi possível preparar a ativação.");
            }
        });

        setContentView(scroll);
    }

    private void logout() {
        if (requestRunning) return;
        if (token.isEmpty()) {
            clearSession();
            showLogin("Sessão encerrada.");
            return;
        }
        api("POST", "/auth/logout", new JSONObject(), token, r -> {
            clearSession();
            showLogin("Sessão encerrada.");
        });
    }

    private void clearSession() {
        token = "";
        prefs.edit().remove("auth_token").apply();
    }

    private interface ApiCallback { void done(ApiResult result); }

    private static class ApiResult {
        boolean ok;
        int status;
        String message;
        JSONObject data;
    }

    private void api(String method, String path, JSONObject body, String bearer, ApiCallback callback) {
        if (requestRunning) return;
        requestRunning = true;
        new Thread(() -> {
            ApiResult result = new ApiResult();
            result.ok = false;
            result.status = 0;
            result.message = "Não foi possível conectar ao servidor.";
            result.data = new JSONObject();
            HttpURLConnection conn = null;
            try {
                URL url = new URL(API_URL + path);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod(method);
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(120000);
                conn.setRequestProperty("Accept", "application/json");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                if (bearer != null && !bearer.isEmpty()) conn.setRequestProperty("Authorization", "Bearer " + bearer);

                if (body != null && !"GET".equals(method)) {
                    conn.setDoOutput(true);
                    byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
                    try (OutputStream os = conn.getOutputStream()) { os.write(bytes); }
                }

                result.status = conn.getResponseCode();
                InputStream stream = result.status >= 200 && result.status < 300 ? conn.getInputStream() : conn.getErrorStream();
                String text = readAll(stream);
                if (text != null && !text.trim().isEmpty()) {
                    try { result.data = new JSONObject(text); } catch (Exception ignored) {}
                }
                result.ok = result.status >= 200 && result.status < 300;
                if (result.ok) {
                    result.message = result.data.optString("message", "OK");
                } else {
                    result.message = result.data.optString("detail", "Erro HTTP " + result.status);
                }
            } catch (Exception e) {
                result.message = "Não foi possível conectar ao servidor. Tente novamente.";
            } finally {
                if (conn != null) conn.disconnect();
                ApiResult finalResult = result;
                runOnUiThread(() -> {
                    requestRunning = false;
                    callback.done(finalResult);
                });
            }
        }).start();
    }

    private String readAll(InputStream stream) throws Exception {
        if (stream == null) return "";
        StringBuilder sb = new StringBuilder();
        try (BufferedReader br = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = br.readLine()) != null) sb.append(line);
        }
        return sb.toString();
    }

    private TextView card(String title, String subtitle) {
        TextView v = label(title + "\n" + subtitle, 16, WHITE, true);
        v.setPadding(dp(18), dp(16), dp(18), dp(16));
        v.setBackgroundColor(CARD);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, dp(88));
        lp.setMargins(0, 0, 0, dp(14));
        v.setLayoutParams(lp);
        v.setGravity(Gravity.CENTER_VERTICAL);
        return v;
    }

    private TextView cardDisabled(String title, String subtitle) {
        TextView v = card(title, subtitle);
        v.setTextColor(MUTED);
        v.setOnClickListener(x -> Toast.makeText(this, "Módulo ainda não conectado.", Toast.LENGTH_SHORT).show());
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
