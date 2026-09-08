package ai.xultron.app.feature.voice

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.core.content.ContextCompat
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Captures one explicit, short enrollment sample at a time. Raw PCM remains only in memory,
 * is zeroed before release, and is never included in a callback, log, database, or network call.
 */
data class VoiceEnrollmentSnapshot(
    val state: State,
    val attempts: Int,
    val acceptedAttempts: Int,
    val requiredAttempts: Int = VoiceEnrollmentPolicy.REQUIRED_ATTEMPTS,
    val detail: String,
    val lastRejection: EnrollmentRejection? = null,
) {
    enum class State { COLLECTING, CAPTURING, COMPLETE, BLOCKED, ERROR }
}

class VoiceEnrollmentController(context: Context) {
    private val appContext = context.applicationContext
    private val coordinator = VoiceEnrollmentCoordinator()
    private val profileStore = EncryptedVoiceProfileStore(appContext)
    private val recording = AtomicBoolean(false)
    private val executor = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "xultron-voice-enrollment").apply { isDaemon = true }
    }

    fun snapshot(): VoiceEnrollmentSnapshot {
        if (recording.get()) return VoiceEnrollmentSnapshot(
            state = VoiceEnrollmentSnapshot.State.CAPTURING,
            attempts = currentAttempts(),
            acceptedAttempts = acceptedAttempts(),
            detail = "An enrollment sample is already being captured.",
        )
        profileStore.read()?.let { return completeSnapshot() }
        val collecting = coordinator.status() as EnrollmentStatus.Collecting
        return VoiceEnrollmentSnapshot(
            state = VoiceEnrollmentSnapshot.State.COLLECTING,
            attempts = collecting.attempts.size,
            acceptedAttempts = collecting.attempts.count { it.accepted },
            detail = "Record one explicit local sample. Raw audio is discarded immediately.",
            lastRejection = collecting.attempts.lastOrNull()?.rejection,
        )
    }

    /** Starts only after native UI confirmation. Completion is delivered exactly once. */
    fun capture(onComplete: (VoiceEnrollmentSnapshot) -> Unit): VoiceEnrollmentSnapshot {
        if (profileStore.read() != null) return completeSnapshot()
        if (!appContext.packageManager.hasSystemFeature(PackageManager.FEATURE_MICROPHONE)) {
            return blocked("This device has no microphone.")
        }
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            return blocked("Microphone permission is required for enrollment.")
        }
        if (!recording.compareAndSet(false, true)) {
            return VoiceEnrollmentSnapshot(
                state = VoiceEnrollmentSnapshot.State.CAPTURING,
                attempts = currentAttempts(),
                acceptedAttempts = acceptedAttempts(),
                detail = "An enrollment sample is already being captured.",
            )
        }
        val capturing = VoiceEnrollmentSnapshot(
            state = VoiceEnrollmentSnapshot.State.CAPTURING,
            attempts = currentAttempts(),
            acceptedAttempts = acceptedAttempts(),
            detail = "Recording one short local sample. It is discarded after quality analysis.",
        )
        executor.execute {
            val failure = runCatching { captureOnce() }.exceptionOrNull()
            recording.set(false)
            onComplete(
                failure?.let { error ->
                    VoiceEnrollmentSnapshot(
                        state = VoiceEnrollmentSnapshot.State.ERROR,
                        attempts = currentAttempts(),
                        acceptedAttempts = acceptedAttempts(),
                        detail = "Could not capture the local enrollment sample: ${error.javaClass.simpleName}.",
                    )
                } ?: snapshot(),
            )
        }
        return capturing
    }

    fun clear(): VoiceEnrollmentSnapshot {
        if (recording.get()) return VoiceEnrollmentSnapshot(
            state = VoiceEnrollmentSnapshot.State.CAPTURING,
            attempts = currentAttempts(),
            acceptedAttempts = acceptedAttempts(),
            detail = "Wait for the current local recording to finish before clearing it.",
        )
        coordinator.clear()
        profileStore.clear()
        return snapshot()
    }

    private fun captureOnce() {
        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE_HZ, CHANNEL_CONFIG, ENCODING)
        check(bufferSize > 0) { "AudioRecord is unavailable" }
        val recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            SAMPLE_RATE_HZ,
            CHANNEL_CONFIG,
            ENCODING,
            bufferSize.coerceAtLeast(SAMPLES * Short.SIZE_BYTES),
        )
        val samples = ShortArray(SAMPLES)
        try {
            check(recorder.state == AudioRecord.STATE_INITIALIZED) { "AudioRecord initialization failed" }
            recorder.startRecording()
            var offset = 0
            while (offset < samples.size) {
                val read = recorder.read(samples, offset, samples.size - offset, AudioRecord.READ_BLOCKING)
                check(read > 0) { "AudioRecord read failed: $read" }
                offset += read
            }
            val status = coordinator.submit(VoiceSampleQuality.metrics(samples, SAMPLE_RATE_HZ))
            if (status is EnrollmentStatus.Complete) profileStore.write(status.profile)
        } finally {
            samples.fill(0)
            runCatching { recorder.stop() }
            recorder.release()
        }
    }

    private fun completeSnapshot() = VoiceEnrollmentSnapshot(
        state = VoiceEnrollmentSnapshot.State.COMPLETE,
        attempts = VoiceEnrollmentPolicy.REQUIRED_ATTEMPTS,
        acceptedAttempts = VoiceEnrollmentPolicy.REQUIRED_ATTEMPTS,
        detail = "Five accepted local samples created an encrypted experimental profile. No wake-word model is installed.",
    )

    private fun blocked(detail: String) = VoiceEnrollmentSnapshot(
        state = VoiceEnrollmentSnapshot.State.BLOCKED,
        attempts = currentAttempts(),
        acceptedAttempts = acceptedAttempts(),
        detail = detail,
    )

    private fun currentAttempts(): Int = (coordinator.status() as? EnrollmentStatus.Collecting)?.attempts?.size ?: VoiceEnrollmentPolicy.REQUIRED_ATTEMPTS
    private fun acceptedAttempts(): Int = (coordinator.status() as? EnrollmentStatus.Collecting)?.attempts?.count { it.accepted } ?: VoiceEnrollmentPolicy.REQUIRED_ATTEMPTS

    private companion object {
        const val SAMPLE_RATE_HZ = 16_000
        const val SAMPLE_SECONDS = 2
        const val SAMPLES = SAMPLE_RATE_HZ * SAMPLE_SECONDS
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
    }
}
