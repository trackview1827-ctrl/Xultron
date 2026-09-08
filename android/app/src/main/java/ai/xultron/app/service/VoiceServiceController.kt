package ai.xultron.app.service

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import ai.xultron.app.feature.voice.VoiceWakeDetectorRegistry
import ai.xultron.app.feature.voice.WakeWordDetector
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * User-driven control surface for the microphone FGS. It never schedules boot recovery,
 * background restarts, network audio operations, or a cloud speech connection.
 */
class VoiceServiceController(
    private val context: Context,
    private val detectorProvider: () -> WakeWordDetector = { VoiceWakeDetectorRegistry.detector },
) {
    private val mutableStatus = VoiceServiceRuntime.status
    fun observeStatus(): StateFlow<VoiceServiceStatus> = mutableStatus.asStateFlow()
    fun status(): VoiceServiceStatus = mutableStatus.value

    fun start(): VoiceServiceCommandResult {
        if (isVoiceServiceStartInFlight(VoiceServiceRuntime.status.value)) {
            return VoiceServiceCommandResult.Accepted(VoiceServiceRuntime.status.value)
        }
        val event = VoiceServiceEvent.StartRequested(preflightBlockReason())
        mutableStatus.value = VoiceServiceStateMachine.reduce(mutableStatus.value, event)
        if (mutableStatus.value.state == VoiceServiceState.BLOCKED) return VoiceServiceCommandResult.Blocked(mutableStatus.value)
        return runCatching {
            ContextCompat.startForegroundService(context, Intent(context, VoiceMonitoringForegroundService::class.java).setAction(VoiceMonitoringForegroundService.ACTION_START))
            VoiceServiceCommandResult.Accepted(mutableStatus.value)
        }.getOrElse { error ->
            mutableStatus.value = VoiceServiceStateMachine.reduce(mutableStatus.value, VoiceServiceEvent.Failure("Could not start local voice monitoring: ${error.javaClass.simpleName}"))
            VoiceServiceCommandResult.Failed(mutableStatus.value)
        }
    }

    fun stop(): VoiceServiceCommandResult {
        mutableStatus.value = VoiceServiceStateMachine.reduce(mutableStatus.value, VoiceServiceEvent.StopRequested)
        context.stopService(Intent(context, VoiceMonitoringForegroundService::class.java))
        return VoiceServiceCommandResult.Accepted(mutableStatus.value)
    }

    private fun preflightBlockReason(): VoiceBlockReason? = when {
        !detectorProvider().isModelAvailable() -> VoiceBlockReason.MODEL_UNAVAILABLE
        !context.packageManager.hasSystemFeature(PackageManager.FEATURE_MICROPHONE) -> VoiceBlockReason.MICROPHONE_UNAVAILABLE
        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED -> VoiceBlockReason.MICROPHONE_PERMISSION_MISSING
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED -> VoiceBlockReason.NOTIFICATION_PERMISSION_MISSING
        else -> null
    }
}

internal fun isVoiceServiceStartInFlight(status: VoiceServiceStatus): Boolean =
    status.state in setOf(VoiceServiceState.STARTING, VoiceServiceState.MONITORING_EXPERIMENTAL)

sealed interface VoiceServiceCommandResult {
    data class Accepted(val status: VoiceServiceStatus) : VoiceServiceCommandResult
    data class Blocked(val status: VoiceServiceStatus) : VoiceServiceCommandResult
    data class Failed(val status: VoiceServiceStatus) : VoiceServiceCommandResult
}

internal object VoiceServiceRuntime {
    val status = MutableStateFlow(VoiceServiceStatus())
    fun transition(event: VoiceServiceEvent) { status.value = VoiceServiceStateMachine.reduce(status.value, event) }
}
