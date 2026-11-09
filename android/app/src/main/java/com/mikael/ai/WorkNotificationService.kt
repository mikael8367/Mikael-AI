package com.mikael.ai

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder

class WorkNotificationService : Service() {
    private val channelId = "mikael_ai_work"
    private val notificationId = 7301

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_PAUSE -> {
                val notification = buildNotification("Trabalho pausado", "O progresso foi salvo. Abra o app para continuar.", false)
                getSystemService(NotificationManager::class.java).notify(notificationId, notification)
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
            else -> {
                val detail = intent?.getStringExtra(EXTRA_DETAIL) ?: "A Mikael AI está trabalhando"
                startForeground(notificationId, buildNotification("Mikael AI está trabalhando…", detail, true))
            }
        }
        return START_NOT_STICKY
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel(channelId, "Trabalhos da Mikael AI", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Mostra quando a Mikael AI está executando um trabalho"
                setShowBadge(false)
            })
        }
    }

    private fun buildNotification(title: String, detail: String, ongoing: Boolean): Notification {
        val openApp = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, channelId) else Notification.Builder(this)
        return builder.setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(title).setContentText(detail).setContentIntent(openApp)
            .setOngoing(ongoing).setOnlyAlertOnce(true).build()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "com.mikael.ai.WORK_START"
        const val ACTION_PAUSE = "com.mikael.ai.WORK_PAUSE"
        const val EXTRA_DETAIL = "detail"
        fun showFinished(context: Context, title: String) {
            val manager = context.getSystemService(NotificationManager::class.java)
            val channel = if (Build.VERSION.SDK_INT >= 26) "mikael_ai_work" else ""
            if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(NotificationChannel(channel, "Trabalhos da Mikael AI", NotificationManager.IMPORTANCE_DEFAULT))
            val openApp = PendingIntent.getActivity(context, 1, Intent(context, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(context, channel) else Notification.Builder(context)
            manager.notify(7302, builder.setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle(title).setContentText("Toque para voltar ao aplicativo.")
                .setContentIntent(openApp).setAutoCancel(true).build())
        }
    }
}
