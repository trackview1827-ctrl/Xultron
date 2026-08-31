package ai.xultron.app.core.network

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.Path
import retrofit2.http.POST
import retrofit2.http.Query

object ApiRoutes {
    const val HEALTH = "system/health"
    const val CONVERSATIONS = "chat/conversations"
    const val MESSAGES = "chat/messages"
    const val MEMORY = "memory"
    const val PROVIDERS = "providers"
    const val SETTINGS = "settings"
    const val DEVICES = "devices"
    const val DEVICE_AUTH_LOGIN = "device-auth/login"
    const val DEVICE_AUTH_ENROLL = "device-auth/enroll"
    const val DEVICE_AUTH_GUEST = "device-auth/guest"
    const val DEVICE_AUTH_REFRESH = "device-auth/refresh"
    const val DEVICE_AUTH_LOGOUT = "device-auth/logout"
    const val DEVICE_AUTH_REVOKE = "device-auth/revoke"
    const val DEVICE_AUTH_SESSIONS = "device-auth/sessions"
    const val DEVICE_REGISTER = "devices/register"
}

@Serializable data class HealthDto(val status: String, val version: String? = null, val time: String? = null)
@Serializable data class UserDto(
    val id: String,
    val username: String,
    val email: String? = null,
    val isGuest: Boolean = false,
    val createdAt: String? = null,
)
@Serializable data class DeviceDescriptorDto(
    val installationId: String,
    val name: String,
    val type: String = "android",
    val appVersion: String? = null,
    val metadata: JsonObject? = null,
)
@Serializable data class DeviceLoginRequest(val identifier: String, val password: String, val device: DeviceDescriptorDto)
@Serializable data class DeviceEnrollRequest(
    val username: String,
    val email: String,
    val password: String,
    val device: DeviceDescriptorDto,
)
@Serializable data class DeviceGuestRequest(val device: DeviceDescriptorDto)
@Serializable data class RefreshRequest(val refreshToken: String)
@Serializable data class LogoutRequest(val refreshToken: String? = null)
@Serializable data class RevokeRequest(val sessionId: String? = null, val deviceId: String? = null)
@Serializable data class RegisteredDeviceDto(
    val id: String,
    val installationId: String? = null,
    val name: String? = null,
    val type: String? = null,
)
@Serializable data class NativeSessionDto(
    val id: String? = null,
    val sessionId: String? = null,
    val deviceId: String? = null,
    val device: RegisteredDeviceDto? = null,
    val expiresAt: String? = null,
)
@Serializable data class DeviceAuthResponse(
    val tokenType: String,
    val accessToken: String,
    val accessExpiresAt: String,
    val expiresIn: Long,
    val refreshToken: String,
    val refreshExpiresAt: String,
    val user: UserDto,
    val session: NativeSessionDto,
)
@Serializable data class NativeSessionsDto(val sessions: List<JsonObject>)
@Serializable data class DeviceRegistrationDto(val device: JsonObject)
@Serializable data class OkDto(val ok: Boolean = true)
@Serializable data class ConversationDto(
    val id: String,
    val title: String,
    val createdAt: String,
    val updatedAt: String,
)
@Serializable data class ConversationsDto(val conversations: List<ConversationDto>)
@Serializable data class ConversationEnvelope(val conversation: ConversationDto)
@Serializable data class MessageDto(
    val id: String,
    val conversationId: String,
    val role: String,
    val content: String,
    val createdAt: String,
    val requestId: String? = null,
)
@Serializable data class MessagesDto(val messages: List<MessageDto>)
@Serializable data class ChatRequest(val message: String, val requestId: String, val conversationId: String? = null)
@Serializable data class ChatResponse(val conversation: ConversationDto, val messages: List<MessageDto>)
@Serializable data class MemoryDto(
    val id: String,
    val title: String,
    val content: String,
    val category: String,
    val createdAt: String,
    val updatedAt: String,
)
@Serializable data class MemoriesDto(val memories: List<MemoryDto>)
@Serializable data class ProviderCredentialDto(
    val configured: Boolean = false,
    val masked: String? = null,
    val authMethod: String? = null,
)
@Serializable data class ProviderDto(
    val id: String,
    val name: String,
    val kind: String,
    val adapter: String,
    val baseUrl: String? = null,
    val model: String? = null,
    val enabled: Boolean = true,
    val isDefault: Boolean = false,
    val credential: ProviderCredentialDto = ProviderCredentialDto(),
)
@Serializable data class ProvidersDto(val providers: List<ProviderDto>)
@Serializable data class ProviderEnvelope(val provider: ProviderDto)
@Serializable data class ModelsDto(val models: List<String>)
@Serializable data class SettingsDto(val settings: JsonObject)

interface XultronApi {
    @GET(ApiRoutes.HEALTH) suspend fun health(): HealthDto
    @GET(ApiRoutes.CONVERSATIONS) suspend fun conversations(@Query("limit") limit: Int = 50): ConversationsDto
    @GET("chat/conversations/{conversationId}/messages") suspend fun messages(
        @Path("conversationId") conversationId: String,
        @Query("limit") limit: Int = 100,
    ): MessagesDto
    @POST(ApiRoutes.MESSAGES) suspend fun sendMessage(@Body request: ChatRequest): ChatResponse
    @GET(ApiRoutes.MEMORY) suspend fun memories(): MemoriesDto
    @GET(ApiRoutes.PROVIDERS) suspend fun providers(): ProvidersDto
    @POST(ApiRoutes.PROVIDERS) suspend fun createProvider(@Body request: JsonObject): ProviderEnvelope
    @PATCH("providers/{providerId}") suspend fun patchProvider(
        @Path("providerId") providerId: String,
        @Body request: JsonObject,
    ): ProviderEnvelope
    @DELETE("providers/{providerId}") suspend fun deleteProvider(@Path("providerId") providerId: String): OkDto
    @POST("providers/{providerId}/test") suspend fun testProvider(@Path("providerId") providerId: String): JsonObject
    @POST("providers/{providerId}/models") suspend fun providerModels(@Path("providerId") providerId: String): ModelsDto
    @GET(ApiRoutes.SETTINGS) suspend fun settings(): SettingsDto
    @PATCH(ApiRoutes.SETTINGS) suspend fun patchSettings(@Body request: JsonObject): SettingsDto
    @POST(ApiRoutes.DEVICE_AUTH_LOGIN) suspend fun deviceLogin(@Body request: DeviceLoginRequest): DeviceAuthResponse
    @POST(ApiRoutes.DEVICE_AUTH_ENROLL) suspend fun deviceEnroll(@Body request: DeviceEnrollRequest): DeviceAuthResponse
    @POST(ApiRoutes.DEVICE_AUTH_GUEST) suspend fun deviceGuest(@Body request: DeviceGuestRequest): DeviceAuthResponse
    @POST(ApiRoutes.DEVICE_AUTH_REFRESH) suspend fun deviceRefresh(@Body request: RefreshRequest): DeviceAuthResponse
    @POST(ApiRoutes.DEVICE_AUTH_LOGOUT) suspend fun deviceLogout(@Body request: LogoutRequest): OkDto
    @POST(ApiRoutes.DEVICE_AUTH_REVOKE) suspend fun deviceRevoke(@Body request: RevokeRequest): OkDto
    @GET(ApiRoutes.DEVICE_AUTH_SESSIONS) suspend fun deviceSessions(): NativeSessionsDto
    @POST(ApiRoutes.DEVICE_REGISTER) suspend fun registerDevice(@Body request: DeviceDescriptorDto): DeviceRegistrationDto
}
