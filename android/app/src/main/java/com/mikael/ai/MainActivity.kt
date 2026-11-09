package com.mikael.ai

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

class MainActivity : Activity() {
    private lateinit var web: WebView
    private val siteHost = "mikael-ai.onrender.com"
    private val siteUrl = "https://$siteHost"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermission()
        web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.allowFileAccess = false
        web.settings.allowContentAccess = false
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                if (uri.scheme == "https" && uri.host == siteHost) return false
                if (uri.scheme == "https" || uri.scheme == "http") {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(uri.toString())))
                }
                return true
            }
            override fun onPageFinished(view: WebView, url: String) {
                if (Uri.parse(url).host == siteHost) injectNativeWorkHooks(view)
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
              // No app Android, esconder a WebView não deve acionar a pausa automática do site.
              try {
                Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
                Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
              } catch (_) {}
              let lastFinishedTaskId = null;
              const finishTaskOnce = (task) => {
                const id = String(task?.id ?? 'unknown');
                if (lastFinishedTaskId === id) return;
                lastFinishedTaskId = id;
                window.MikaelNative?.workFinished(task.status, id);
              };
              const originalFetch = window.fetch.bind(window);
              window.fetch = async (...args) => {
                const requestUrl = String(args[0]?.url || args[0] || '');
                try {
                  const response = await originalFetch(...args);
                  if (/\/api\/work\/start$/.test(requestUrl)) {
                    if (!response.ok) window.MikaelNative?.workFinished('failed', 'start-error');
                    else {
                      try {
                        const task = await response.clone().json();
                        if (task.status === 'running') { lastFinishedTaskId = null; window.MikaelNative?.workStarted(task.progress || 'Trabalho em andamento'); }
                        else if (['completed','cancelled','failed'].includes(task.status)) finishTaskOnce(task);
                      } catch (_) {}
                    }
                  } else if (/\/api\/work\/current$/.test(requestUrl) && response.ok) {
                    try {
                      const task = await response.clone().json();
                      if (task && task.status === 'running') { lastFinishedTaskId = null; window.MikaelNative?.workStarted(task.progress || 'Trabalho em andamento'); }
                      else if (task && ['completed','cancelled','failed'].includes(task.status)) finishTaskOnce(task);
                      else if (task && task.status === 'paused') window.MikaelNative?.workPaused();
                    } catch (_) {}
                  } else if (/\/api\/work\/\d+\/(pause|resume|cancel)$/.test(requestUrl) && response.ok) {
                    try {
                      const task = await response.clone().json();
                      if (task.status === 'running') { lastFinishedTaskId = null; window.MikaelNative?.workStarted(task.progress || 'Trabalho em andamento'); }
                      else if (['completed','cancelled','failed'].includes(task.status)) window.MikaelNative?.workFinished(task.status);
                      else if (task.status === 'paused') window.MikaelNative?.workPaused();
                    } catch (_) {}
                  }
                  return response;
                } catch (error) {
                  if (/\/api\/work\/start$/.test(requestUrl)) window.MikaelNative?.workFinished('failed', 'start-error');
                  throw error;
                }
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
        @JavascriptInterface fun workFinished(status: String, taskId: String) {
            runOnUiThread {
                stopService(Intent(this@MainActivity, WorkNotificationService::class.java))
                if (status == "completed") WorkNotificationService.showFinished(this@MainActivity, "Mikael AI concluiu o trabalho")
                else if (status == "failed") WorkNotificationService.showFinished(this@MainActivity, "O trabalho da Mikael AI falhou")
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
    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
