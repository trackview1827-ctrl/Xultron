package ai.xultron.app.feature.voice

/**
 * Local detector boundary. A concrete detector must declare an installed model before the
 * foreground service may open the microphone. This release ships no detector model.
 */
interface WakeWordDetector {
    val modelId: String?
    fun isModelAvailable(): Boolean
    fun process(samples: ShortArray, size: Int): WakeWordDetection
    fun close() = Unit
}

enum class WakeWordDetection { NO_MATCH, MATCH }

object UnavailableWakeWordDetector : WakeWordDetector {
    override val modelId: String? = null
    override fun isModelAvailable() = false
    override fun process(samples: ShortArray, size: Int) = WakeWordDetection.NO_MATCH
}

/** Injection point for a future independently benchmarked local model. Never populate remotely. */
object VoiceWakeDetectorRegistry {
    @Volatile var detector: WakeWordDetector = UnavailableWakeWordDetector
}
