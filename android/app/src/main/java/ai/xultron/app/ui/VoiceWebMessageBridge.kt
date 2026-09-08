package ai.xultron.app.ui

import android.net.Uri
import android.webkit.WebView
import ai.xultron.app.feature.voice.VoiceEnrollmentController
import ai.xultron.app.feature.voice.VoiceEnrollmentSnapshot
import ai.xultron.app.service.VoiceServiceCommandResult
import ai.xultron.app.service.VoiceServiceController
import ai.xultron.app.service.VoiceServiceStatus
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/**
 * A deliberately small, origin-bound WebMessage bridge. It accepts no raw audio, shell input,
 * URLs, tokens, phrase text, or arbitrary method names. Sensitive microphone operations wait for
 * native confirmation. Enrollment audio never crosses this bridge.
 */
internal sealed interface VoiceWebMessage {
    val id: String
    data class Status(override val id: String) : VoiceWebMessage
    data class Start(override val id: String) : VoiceWebMessage
    data class Stop(override val id: String) : VoiceWebMessage
    data class EnrollmentStatus(override val id: String) : VoiceWebMessage
    data class EnrollmentCapture(override val id: String) : VoiceWebMessage
    data class EnrollmentClear(override val id: String) : VoiceWebMessage
}

internal object VoiceWebMessageParser {
    private val requestId = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$")

    fun parse(raw: String?): VoiceWebMessage? = runCatching {
        val value = Json.parseToJsonElement(raw ?: return null) as? JsonObject ?: return null
        if (value.keys != setOf("v", "id", "action")) return null
        val version = value["v"]?.jsonPrimitive?.contentOrNull
        val id = value["id"]?.jsonPrimitive?.contentOrNull
        val action = value["action"]?.jsonPrimitive?.contentOrNull
        if (version != "1" || id == null || !requestId.matches(id)) return null
        when (action) {
            "voice.status" -> VoiceWebMessage.Status(id)
            "voice.start" -> VoiceWebMessage.Start(id)
            "voice.stop" -> VoiceWebMessage.Stop(id)
            "voice.enrollment.status" -> VoiceWebMessage.EnrollmentStatus(id)
            "voice.enrollment.capture" -> VoiceWebMessage.EnrollmentCapture(id)
            "voice.enrollment.clear" -> VoiceWebMessage.EnrollmentClear(id)
            else -> null
        }
    }.getOrNull()
}

internal fun interface VoiceWebReply { fun post(payload: String) }

internal data class PendingVoiceStart(val id: String, val reply: VoiceWebReply)
internal data class PendingVoiceEnrollment(
    val id: String,
    val operation: Operation,
    val reply: VoiceWebReply,
) {
    enum class Operation { CAPTURE, CLEAR }
}

internal class VoiceWebMessageBridge(
    private val controller: VoiceServiceController,
    private val enrollmentController: VoiceEnrollmentController,
    private val trustedOrigin: String,
    private val onStartConfirmationRequired: (PendingVoiceStart) -> Unit,
    private val onEnrollmentConfirmationRequired: (PendingVoiceEnrollment) -> Unit,
) : WebViewCompat.WebMessageListener {
    override fun onPostMessage(
        view: WebView,
        message: WebMessageCompat,
        sourceOrigin: Uri,
        isMainFrame: Boolean,
        replyProxy: JavaScriptReplyProxy,
    ) {
        val reply = VoiceWebReply { payload -> view.post { replyProxy.postMessage(payload) } }
        if (!isMainFrame || !isTrustedVoiceSource(sourceOrigin.toString(), trustedOrigin)) {
            reply.error("invalid_frame")
            return
        }
        when (val request = VoiceWebMessageParser.parse(message.data)) {
            is VoiceWebMessage.Status -> reply.status(request.id, controller.status())
            is VoiceWebMessage.Start -> onStartConfirmationRequired(PendingVoiceStart(request.id, reply))
            is VoiceWebMessage.Stop -> reply.status(request.id, controller.stop().status())
            is VoiceWebMessage.EnrollmentStatus -> reply.enrollment(request.id, enrollmentController.snapshot())
            is VoiceWebMessage.EnrollmentCapture -> onEnrollmentConfirmationRequired(
                PendingVoiceEnrollment(request.id, PendingVoiceEnrollment.Operation.CAPTURE, reply),
            )
            is VoiceWebMessage.EnrollmentClear -> onEnrollmentConfirmationRequired(
                PendingVoiceEnrollment(request.id, PendingVoiceEnrollment.Operation.CLEAR, reply),
            )
            null -> reply.error("invalid_request")
        }
    }
}

internal fun isTrustedVoiceSource(sourceOrigin: String, trustedOrigin: String): Boolean =
    sourceOrigin.trimEnd('/') == trustedOrigin.trimEnd('/')

internal fun VoiceServiceCommandResult.status(): VoiceServiceStatus = when (this) {
    is VoiceServiceCommandResult.Accepted -> status
    is VoiceServiceCommandResult.Blocked -> status
    is VoiceServiceCommandResult.Failed -> status
}

internal fun VoiceWebReply.status(id: String, status: VoiceServiceStatus) = post(
    Json.encodeToString(
        buildJsonObject {
            put("id", id)
            put("status", buildJsonObject {
                put("state", status.state.name)
                put("detail", status.detail)
                status.blockReason?.let { put("blockReason", it.name) }
                put("diagnostic", buildJsonObject {
                    put("cloudSttEnabled", status.diagnostic.cloudSttEnabled)
                    put("rawAudioUploadEnabled", status.diagnostic.rawAudioUploadEnabled)
                    put("pollingEnabled", status.diagnostic.pollingEnabled)
                    put("persistentWebSocketEnabled", status.diagnostic.persistentWebSocketEnabled)
                    put("rawAudioPersisted", status.diagnostic.rawAudioPersisted)
                    status.diagnostic.lastError?.let { put("lastError", it) }
                })
            })
        },
    ),
)

internal fun VoiceWebReply.enrollment(id: String, snapshot: VoiceEnrollmentSnapshot) = post(
    Json.encodeToString(
        buildJsonObject {
            put("id", id)
            put("enrollment", buildJsonObject {
                put("state", snapshot.state.name)
                put("attempts", snapshot.attempts)
                put("acceptedAttempts", snapshot.acceptedAttempts)
                put("requiredAttempts", snapshot.requiredAttempts)
                put("detail", snapshot.detail)
                snapshot.lastRejection?.let { put("lastRejection", it.name) }
            })
        },
    ),
)

internal fun VoiceWebReply.error(code: String) = post(
    Json.encodeToString(buildJsonObject { put("error", JsonPrimitive(code)) }),
)
