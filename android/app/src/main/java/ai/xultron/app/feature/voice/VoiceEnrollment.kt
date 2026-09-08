package ai.xultron.app.feature.voice

import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Local-only wake-profile enrollment. This is deliberately not a wake-word model.
 * A profile is experimental until independently benchmarked for FAR/FRR, replay,
 * noise, thermal, and battery behavior.
 */
object VoiceEnrollmentPolicy {
    const val REQUIRED_ATTEMPTS = 5
    const val MIN_DURATION_MS = 1_500L
    const val MIN_SPEECH_RATIO = 0.35
    const val MIN_RMS_DBFS = -42.0
    const val MAX_RMS_DBFS = -6.0
    const val MAX_CLIPPING_RATIO = 0.02
}

data class VoiceSampleMetrics(
    val durationMs: Long,
    val speechFrameRatio: Double,
    val rmsDbfs: Double,
    val clippingRatio: Double,
)

enum class EnrollmentRejection {
    TOO_SHORT,
    NO_SPEECH,
    TOO_QUIET,
    CLIPPED,
}

data class EnrollmentAttempt(
    val number: Int,
    val accepted: Boolean,
    val rejection: EnrollmentRejection? = null,
    /** Retains metrics only. Raw waveform samples are never retained. */
    val metrics: VoiceSampleMetrics,
)

data class ExperimentalVoiceProfile(
    val version: Int = 1,
    val enrolledAttempts: Int,
    val meanRmsDbfs: Double,
    val meanSpeechFrameRatio: Double,
)

sealed interface EnrollmentStatus {
    data class Collecting(val attempts: List<EnrollmentAttempt>) : EnrollmentStatus
    data class Complete(val profile: ExperimentalVoiceProfile) : EnrollmentStatus
}

class VoiceEnrollmentCoordinator {
    private val attempts = mutableListOf<EnrollmentAttempt>()

    fun status(): EnrollmentStatus = profileOrNull()?.let(EnrollmentStatus::Complete)
        ?: EnrollmentStatus.Collecting(attempts.toList())

    /** Each invocation is one explicit user enrollment action. It consumes one of five slots. */
    fun submit(metrics: VoiceSampleMetrics): EnrollmentStatus {
        check(attempts.size < VoiceEnrollmentPolicy.REQUIRED_ATTEMPTS) {
            "Enrollment already has five explicit attempts. Clear or reuse the local profile first."
        }
        val rejection = metrics.rejection()
        attempts += EnrollmentAttempt(
            number = attempts.size + 1,
            accepted = rejection == null,
            rejection = rejection,
            metrics = metrics,
        )
        return status()
    }

    fun clear() = attempts.clear()

    private fun profileOrNull(): ExperimentalVoiceProfile? {
        if (attempts.size != VoiceEnrollmentPolicy.REQUIRED_ATTEMPTS || attempts.any { !it.accepted }) return null
        return ExperimentalVoiceProfile(
            enrolledAttempts = attempts.size,
            meanRmsDbfs = attempts.map { it.metrics.rmsDbfs }.average(),
            meanSpeechFrameRatio = attempts.map { it.metrics.speechFrameRatio }.average(),
        )
    }
}

fun VoiceSampleMetrics.rejection(): EnrollmentRejection? = when {
    durationMs < VoiceEnrollmentPolicy.MIN_DURATION_MS -> EnrollmentRejection.TOO_SHORT
    speechFrameRatio < VoiceEnrollmentPolicy.MIN_SPEECH_RATIO -> EnrollmentRejection.NO_SPEECH
    rmsDbfs < VoiceEnrollmentPolicy.MIN_RMS_DBFS -> EnrollmentRejection.TOO_QUIET
    rmsDbfs > VoiceEnrollmentPolicy.MAX_RMS_DBFS || clippingRatio > VoiceEnrollmentPolicy.MAX_CLIPPING_RATIO -> EnrollmentRejection.CLIPPED
    else -> null
}

/** Computes non-reversible quality metrics while callers keep sample bytes transient. */
object VoiceSampleQuality {
    fun metrics(samples: ShortArray, sampleRateHz: Int): VoiceSampleMetrics {
        require(sampleRateHz > 0)
        if (samples.isEmpty()) return VoiceSampleMetrics(0, 0.0, Double.NEGATIVE_INFINITY, 0.0)
        val durationMs = samples.size * 1_000L / sampleRateHz
        val peakThreshold = Short.MAX_VALUE * 0.98
        // Iterate the caller-owned array directly. Do not create boxed/chunked waveform copies,
        // so the caller's final samples.fill(0) clears the only retained PCM buffer.
        val frameSize = (sampleRateHz / 50).coerceAtLeast(1) // 20 ms
        var totalSquares = 0.0
        var clipped = 0
        var speechFrames = 0
        var frameCount = 0
        var frameStart = 0
        while (frameStart < samples.size) {
            val frameEnd = minOf(frameStart + frameSize, samples.size)
            var frameSquares = 0.0
            var index = frameStart
            while (index < frameEnd) {
                val sample = samples[index].toDouble()
                val square = sample.pow(2.0)
                totalSquares += square
                frameSquares += square
                if (kotlin.math.abs(samples[index].toInt()) >= peakThreshold) clipped += 1
                index += 1
            }
            val frameRms = sqrt(frameSquares / (frameEnd - frameStart))
            if (frameRms / Short.MAX_VALUE >= 0.01) speechFrames += 1
            frameCount += 1
            frameStart = frameEnd
        }
        val rms = sqrt(totalSquares / samples.size)
        val rmsDbfs = if (rms == 0.0) Double.NEGATIVE_INFINITY else 20.0 * kotlin.math.log10(rms / Short.MAX_VALUE)
        val clippingRatio = clipped.toDouble() / samples.size
        return VoiceSampleMetrics(durationMs, speechFrames.toDouble() / frameCount, rmsDbfs, clippingRatio)
    }
}
