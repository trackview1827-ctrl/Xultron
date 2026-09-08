package ai.xultron.app.service

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.content.pm.ServiceInfo
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import ai.xultron.app.feature.voice.VoiceWakeDetectorRegistry
import ai.xultron.app.R
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** A transparent, local-only experimental monitor. It deliberately does not run speech-to-text. */
class VoiceMonitoringForegroundService : Service() {
    private val active = AtomicBoolean(false)
    private val startingOrActive = AtomicBoolean(false)
    private val executor = Executors.newSingleThreadExecutor()
    private var recorder: AudioRecord? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = when (intent?.action) {
        ACTION_START -> { startMonitoring(); START_NOT_STICKY }
        ACTION_STOP -> { stopMonitoring(); START_NOT_STICKY }
        else -> { stopMonitoring(); START_NOT_STICKY }
    }

    private fun startMonitoring() {
        // Android can deliver multiple START intents before AudioRecord initialization completes.
        // Keep exactly one recorder lifetime so a second command cannot orphan microphone capture.
        if (!startingOrActive.compareAndSet(false, true)) return
        if (!VoiceWakeDetectorRegistry.detector.isModelAvailable()) {
            VoiceServiceRuntime.transition(VoiceServiceEvent.StartRequested(VoiceBlockReason.MODEL_UNAVAILABLE))
            startingOrActive.set(false)
            stopSelf()
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            VoiceServiceRuntime.transition(VoiceServiceEvent.StartRequested(VoiceBlockReason.MICROPHONE_PERMISSION_MISSING))
            startingOrActive.set(false)
            stopSelf()
            return
        }
        createChannel()
        runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) startForeground(NOTIFICATION_ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            else startForeground(NOTIFICATION_ID, notification())
            val minBuffer = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, ENCODING)
            require(minBuffer > 0) { "Audio capture is unavailable." }
            recorder = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, SAMPLE_RATE, CHANNEL_CONFIG, ENCODING, minBuffer * 2)
            require(recorder?.state == AudioRecord.STATE_INITIALIZED) { "Audio recorder could not initialize." }
            recorder?.startRecording()
            active.set(true)
            VoiceServiceRuntime.transition(VoiceServiceEvent.ForegroundServiceStarted)
            executor.execute { discardAudioUntilStopped(minBuffer) }
        }.onFailure { error ->
            VoiceServiceRuntime.transition(VoiceServiceEvent.Failure("Local microphone monitor failed: ${error.javaClass.simpleName}"))
            stopMonitoring()
        }
    }

    /** Discards each PCM buffer immediately. No raw audio reaches disk, network, STT, polling, or sockets. */
    private fun discardAudioUntilStopped(bufferSize: Int) {
        val buffer = ShortArray(bufferSize / 2)
        while (active.get()) {
            val size = recorder?.read(buffer, 0, buffer.size, AudioRecord.READ_BLOCKING) ?: 0
            if (size > 0) VoiceWakeDetectorRegistry.detector.process(buffer, size)
            buffer.fill(0)
        }
    }

    private fun stopMonitoring() {
        startingOrActive.set(false)
        val wasActive = active.getAndSet(false)
        runCatching { recorder?.stop() }
        recorder?.release()
        recorder = null
        VoiceWakeDetectorRegistry.detector.close()
        stopForeground(STOP_FOREGROUND_REMOVE)
        if (wasActive || VoiceServiceRuntime.status.value.state != VoiceServiceState.STOPPED) VoiceServiceRuntime.transition(VoiceServiceEvent.ServiceStopped)
        stopSelf()
    }

    override fun onTaskRemoved(rootIntent: Intent?) { stopMonitoring() }
    override fun onDestroy() { stopMonitoring(); executor.shutdownNow(); super.onDestroy() }
    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            (getSystemService(NotificationManager::class.java)).createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Experimental local voice monitoring", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Visible while Xultron has the microphone open."
                    setShowBadge(false)
                },
            )
        }
    }

    private fun notification(): Notification = NotificationCompat.Builder(this, CHANNEL_ID)
        .setSmallIcon(R.drawable.ic_launcher)
        .setContentTitle("Experimental local voice monitoring")
        .setContentText("Microphone active. No audio is uploaded or transcribed.")
        .setCategory(NotificationCompat.CATEGORY_SERVICE)
        .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
        .setOngoing(true)
        .setOnlyAlertOnce(true)
        .addAction(0, "Stop", PendingIntent.getService(this, 0, Intent(this, VoiceMonitoringForegroundService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
        .build()

    companion object {
        const val ACTION_START = "ai.xultron.app.action.START_LOCAL_VOICE_MONITOR"
        const val ACTION_STOP = "ai.xultron.app.action.STOP_LOCAL_VOICE_MONITOR"
        private const val CHANNEL_ID = "experimental_local_voice_monitor"
        private const val NOTIFICATION_ID = 1_507
        private const val SAMPLE_RATE = 16_000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
    }
}
