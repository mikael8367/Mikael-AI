package com.mikael.ai

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var web: WebView
    private val siteUrl = "https://mikael-ai.onrender.com"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermission()
        web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.allowFileAccess = false
        web.settings.allowContentAccess = false
        web.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                if (url.startsWith(siteUrl)) injectNativeWorkHooks(view)
            }
        }
        web.webChromeClient = WebChromeClient()
        web.addJavascriptInterface(NativeBridge(), "MikaelNative")
        setContentView(web)
        if (savedInstanceState == null) web.loadUrl(siteUrl) else web.restoreState(savedInstanceState)
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 401)
        }
    }

    private fun injectNativeWorkHooks(view: WebView) {
        val script = """
            (() => {
              if (window.__mikaelNativeHooks) return;
              window.__mikaelNativeHooks = true;
              const originalFetch = window.fetch.bind(window);
              window.fetch = async (...args) => {
                const requestUrl = String(args[0]?.url || args[0] || '');
                const response = await originalFetch(...args);
                if (/\/api\/work\/\d+\/(pause|resume|cancel)/.test(requestUrl)) {
                  try {
                    const clone = response.clone();
                    const task = await clone.json();
                    if (task.status === 'running') window.MikaelNative?.workStarted(task.progress || 'Trabalho em andamento');
                    else if (['completed','cancelled','failed'].includes(task.status)) window.MikaelNative?.workFinished(task.status);
                    else if (task.status === 'paused') window.MikaelNative?.workPaused();
                  } catch (_) {}
                }
                if (/\/api\/work\/\d+$/.test(requestUrl) && response.ok) {
                  try {
                    const task = await response.clone().json();
                    if (task.status === 'running') window.MikaelNative?.workStarted(task.progress || 'Trabalho em andamento');
                    else if (['completed','cancelled','failed'].includes(task.status)) window.MikaelNative?.workFinished(task.status);
                    else if (task.status === 'paused') window.MikaelNative?.workPaused();
                  } catch (_) {}
                }
                return response;
              };
              const start = document.getElementById('startLongWork');
              if (start) start.addEventListener('click', () => window.MikaelNative?.workStarted('Preparando trabalho'), true);
            })();
        """.trimIndent()
        view.evaluateJavascript(script, null)
    }

    inner class NativeBridge {
        @JavascriptInterface fun workStarted(detail: String) {
            runOnUiThread {
                val intent = Intent(this@MainActivity, WorkNotificationService::class.java)
                    .setAction(WorkNotificationService.ACTION_START)
                    .putExtra(WorkNotificationService.EXTRA_DETAIL, detail.take(180))
                if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
            }
        }
        @JavascriptInterface fun workFinished(status: String) {
            runOnUiThread {
                stopService(Intent(this@MainActivity, WorkNotificationService::class.java))
                val title = if (status == "completed") "Mikael AI concluiu o trabalho" else "Trabalho da Mikael AI encerrado"
                WorkNotificationService.showFinished(this@MainActivity, title)
            }
        }
        @JavascriptInterface fun workPaused() {
            runOnUiThread {
                val intent = Intent(this@MainActivity, WorkNotificationService::class.java).setAction(WorkNotificationService.ACTION_PAUSE)
                startService(intent)
            }
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        web.saveState(outState)
        super.onSaveInstanceState(outState)
    }
    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
