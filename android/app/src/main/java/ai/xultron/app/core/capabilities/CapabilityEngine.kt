package ai.xultron.app.core.capabilities

enum class Capability {
    MICROPHONE,
    CAMERA,
    LOCATION_FOREGROUND,
    LOCATION_BACKGROUND,
    SENSORS,
    NOTIFICATIONS,
    TERMINAL,
    WAKE_WORD,
    DISPLAY_OVER_OTHER_APPS,
    SCREEN_CAPTURE,
}

enum class PermissionDisposition { GRANTED, DENIED, REQUIRES_SETTINGS, RESTRICTED, NOT_AVAILABLE, UNKNOWN }

data class CapabilityRequest(
    val capability: Capability,
    val userEnabled: Boolean,
    val permission: PermissionDisposition,
    val featureImplemented: Boolean,
    val requiresConfirmation: Boolean = false,
    val confirmationGranted: Boolean = false,
)

sealed interface CapabilityDecision {
    data object Allowed : CapabilityDecision
    data class Denied(val reason: String) : CapabilityDecision
    data class RequestPermission(val capability: Capability) : CapabilityDecision
    data class OpenSettings(val capability: Capability) : CapabilityDecision
    data class Confirm(val capability: Capability) : CapabilityDecision
}

/** One fail-closed boundary for every native or privileged action. */
class CapabilityEngine {
    fun evaluate(request: CapabilityRequest): CapabilityDecision {
        if (!request.featureImplemented) return CapabilityDecision.Denied("Bu özellik mevcut fazda uygulanmadı.")
        if (!request.userEnabled) return CapabilityDecision.Denied("Kullanıcı politikası bu capability'yi devre dışı bıraktı.")
        return when (request.permission) {
            PermissionDisposition.GRANTED -> when {
                request.requiresConfirmation && !request.confirmationGranted -> CapabilityDecision.Confirm(request.capability)
                else -> CapabilityDecision.Allowed
            }
            PermissionDisposition.DENIED -> CapabilityDecision.RequestPermission(request.capability)
            PermissionDisposition.REQUIRES_SETTINGS -> CapabilityDecision.OpenSettings(request.capability)
            PermissionDisposition.RESTRICTED -> CapabilityDecision.Denied("Android veya cihaz politikası erişimi kısıtlıyor.")
            PermissionDisposition.NOT_AVAILABLE -> CapabilityDecision.Denied("Capability bu cihazda kullanılamıyor.")
            PermissionDisposition.UNKNOWN -> CapabilityDecision.Denied("Permission durumu doğrulanamadı.")
        }
    }
}
