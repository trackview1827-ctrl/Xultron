package ai.xultron.app.service

/** Pure reducer so start/stop behavior remains deterministic and testable. */
enum class VoiceServiceState { STOPPED, STARTING, MONITORING_EXPERIMENTAL, STOPPING, BLOCKED, ERROR }

enum class VoiceBlockReason { MICROPHONE_UNAVAILABLE, MICROPHONE_PERMISSION_MISSING, NOTIFICATION_PERMISSION_MISSING, MODEL_UNAVAILABLE, UNSUPPORTED }

data class VoiceServiceStatus(
    val state: VoiceServiceState = VoiceServiceState.STOPPED,
    val detail: String = "Stopped. No microphone is open.",
    val blockReason: VoiceBlockReason? = null,
    val diagnostic: VoiceDiagnostics = VoiceDiagnostics(),
)

data class VoiceDiagnostics(
    val cloudSttEnabled: Boolean = false,
    val rawAudioUploadEnabled: Boolean = false,
    val pollingEnabled: Boolean = false,
    val persistentWebSocketEnabled: Boolean = false,
    val rawAudioPersisted: Boolean = false,
    val lastError: String? = null,
)

sealed interface VoiceServiceEvent {
    data class StartRequested(val blockReason: VoiceBlockReason? = null) : VoiceServiceEvent
    data object ForegroundServiceStarted : VoiceServiceEvent
    data object StopRequested : VoiceServiceEvent
    data object ServiceStopped : VoiceServiceEvent
    data class Failure(val detail: String) : VoiceServiceEvent
}

object VoiceServiceStateMachine {
    fun reduce(current: VoiceServiceStatus, event: VoiceServiceEvent): VoiceServiceStatus = when (event) {
        is VoiceServiceEvent.StartRequested -> event.blockReason?.let { blocked(it) }
            ?: current.copy(state = VoiceServiceState.STARTING, detail = "Starting user-requested local microphone session.", blockReason = null)
        VoiceServiceEvent.ForegroundServiceStarted -> current.copy(
            state = VoiceServiceState.MONITORING_EXPERIMENTAL,
            detail = "Experimental local monitoring active. No cloud STT, upload, polling, or persistent socket.",
            blockReason = null,
        )
        VoiceServiceEvent.StopRequested -> if (current.state == VoiceServiceState.STOPPED) current
            else current.copy(state = VoiceServiceState.STOPPING, detail = "Stopping microphone session.")
        VoiceServiceEvent.ServiceStopped -> VoiceServiceStatus()
        is VoiceServiceEvent.Failure -> current.copy(
            state = VoiceServiceState.ERROR,
            detail = event.detail,
            diagnostic = current.diagnostic.copy(lastError = event.detail),
        )
    }

    private fun blocked(reason: VoiceBlockReason) = VoiceServiceStatus(
        state = VoiceServiceState.BLOCKED,
        blockReason = reason,
        detail = when (reason) {
            VoiceBlockReason.MICROPHONE_UNAVAILABLE -> "This device has no microphone."
            VoiceBlockReason.MICROPHONE_PERMISSION_MISSING -> "Microphone permission is required before starting."
            VoiceBlockReason.NOTIFICATION_PERMISSION_MISSING -> "Notification permission is required so the active microphone session remains visible."
            VoiceBlockReason.MODEL_UNAVAILABLE -> "No independently benchmarked local wake model is installed, so the microphone will not open."
            VoiceBlockReason.UNSUPPORTED -> "Experimental local voice monitoring is not supported on this device."
        },
    )
}
