package ai.xultron.app.data

import ai.xultron.app.core.network.ApiFactory
import ai.xultron.app.core.auth.AuthRepository
import ai.xultron.app.core.network.ChatRequest
import ai.xultron.app.core.network.ChatResponse
import ai.xultron.app.core.network.ConversationDto
import ai.xultron.app.core.network.HealthDto
import ai.xultron.app.core.network.MemoryDto
import ai.xultron.app.core.network.MessageDto
import ai.xultron.app.core.network.ProviderDto
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.UUID

class XultronRepository(private val apiFactory: ApiFactory, private val authRepository: AuthRepository) {
    suspend fun health(backendUrl: String): HealthDto = apiFactory.create(backendUrl).health()
    suspend fun conversations(backendUrl: String): List<ConversationDto> = authenticated(backendUrl) { conversations().conversations }
    suspend fun messages(backendUrl: String, conversationId: String): List<MessageDto> =
        authenticated(backendUrl) { messages(conversationId).messages }
    suspend fun sendMessage(backendUrl: String, message: String, conversationId: String?): ChatResponse =
        authenticated(backendUrl) { sendMessage(
            ChatRequest(message.trim(), "android_${UUID.randomUUID()}", conversationId),
        ) }
    suspend fun memories(backendUrl: String): List<MemoryDto> = authenticated(backendUrl) { memories().memories }
    suspend fun providers(backendUrl: String): List<ProviderDto> = authenticated(backendUrl) { providers().providers }
    suspend fun testProvider(backendUrl: String, providerId: String): JsonObject =
        authenticated(backendUrl) { testProvider(providerId) }
    suspend fun createProvider(
        backendUrl: String,
        name: String,
        kind: String,
        adapter: String,
        baseUrl: String?,
        model: String?,
        apiKey: String?,
    ): ProviderDto = authenticated(backendUrl) {
        createProvider(providerPayload(name, kind, adapter, baseUrl, model, apiKey)).provider
    }
    suspend fun updateProvider(
        backendUrl: String,
        providerId: String,
        name: String,
        kind: String,
        adapter: String,
        baseUrl: String?,
        model: String?,
        apiKey: String?,
    ): ProviderDto = authenticated(backendUrl) {
        patchProvider(providerId, providerPayload(name, kind, adapter, baseUrl, model, apiKey)).provider
    }
    suspend fun deleteProvider(backendUrl: String, providerId: String) =
        authenticated(backendUrl) { deleteProvider(providerId) }
    suspend fun providerModels(backendUrl: String, providerId: String): List<String> =
        authenticated(backendUrl) { providerModels(providerId).models }
    suspend fun settings(backendUrl: String): JsonObject = authenticated(backendUrl) { settings().settings }
    suspend fun patchBooleanSetting(backendUrl: String, key: String, value: Boolean): JsonObject =
        authenticated(backendUrl) { patchSettings(buildJsonObject { put(key, JsonPrimitive(value)) }).settings }

    private suspend fun <T> authenticated(backendUrl: String, call: suspend ai.xultron.app.core.network.XultronApi.() -> T): T =
        authRepository.withRefresh(backendUrl) { apiFactory.create(backendUrl).call() }

    private fun providerPayload(
        name: String,
        kind: String,
        adapter: String,
        baseUrl: String?,
        model: String?,
        apiKey: String?,
    ) = buildJsonObject {
        put("name", name.trim())
        put("kind", kind.trim())
        put("adapter", adapter.trim())
        baseUrl?.trim()?.takeIf(String::isNotEmpty)?.let { put("baseUrl", it) }
        model?.trim()?.takeIf(String::isNotEmpty)?.let { put("model", it) }
        apiKey?.takeIf(String::isNotBlank)?.let { put("apiKey", it) }
    }
}
