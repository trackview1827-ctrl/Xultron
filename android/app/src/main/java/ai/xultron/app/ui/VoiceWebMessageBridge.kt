package ai.xultron.app.ui

import android.net.Uri
import android.webkit.WebView
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
 * A deliberately tiny, origin-bound WebMessage bridge. It accepts no raw audio, shell input,
 * URLs, tokens, or arbitrary method names. A start request is held until native UI confirms it.
 */
internal sealed interface VoiceWebMessage {
    val id: String
    data class Status(override val id: String) : VoiceWebMessage
    data class Start(override val id: String) : VoiceWebMessage
    data class Stop(override val id: String) : VoiceWebMessage
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
            else -> null
        }
    }.getOrNull()
}

internal fun interface VoiceWebReply { fun post(payload: String) }

internal data class PendingVoiceStart(
    val id: String,
    val reply: VoiceWebReply,
)

internal class VoiceWebMessageBridge(
    private val controller: VoiceServiceController,
    private val trustedOrigin: String,
    private val onStartConfirmationRequired: (PendingVoiceStart) -> Unit,
) : WebViewCompat.WebMessageListener {
    override fun onPostMessage(
        view: WebView,
        message: WebMessageCompat,
        sourceOrigin: Uri,
        isMainFrame: Boolean,
        replyProxy: JavaScriptReplyProxy,
    ) {
        val reply = VoiceWebReply { payload -> replyProxy.postMessage(payload) }
        if (!isMainFrame || !isTrustedVoiceSource(sourceOrigin.toString(), trustedOrigin)) {
            reply.error("invalid_frame")
            return
        }
        when (val request = VoiceWebMessageParser.parse(message.data)) {
            is VoiceWebMessage.Status -> reply.status(request.id, controller.status())
            is VoiceWebMessage.Start -> onStartConfirmationRequired(PendingVoiceStart(request.id, reply))
            is VoiceWebMessage.Stop -> reply.status(request.id, controller.stop().status())
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

internal fun VoiceWebReply.error(code: String) = post(
    Json.encodeToString(buildJsonObject { put("error", JsonPrimitive(code)) }),
)
