package ai.xultron.app.core.auth

import ai.xultron.app.core.network.ApiFactory
import ai.xultron.app.core.network.DeviceAuthResponse
import ai.xultron.app.core.network.DeviceEnrollRequest
import ai.xultron.app.core.network.DeviceGuestRequest
import ai.xultron.app.core.network.DeviceLoginRequest
import ai.xultron.app.core.network.LogoutRequest
import ai.xultron.app.core.network.RefreshRequest
import ai.xultron.app.core.network.UserDto
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import retrofit2.HttpException

class AuthRepository(
    private val apiFactory: ApiFactory,
    private val sessionStore: SessionStore,
    private val deviceIdentity: DeviceIdentity,
) {
    private val refreshMutex = Mutex()

    suspend fun restore(backendUrl: String): UserDto {
        val stored = sessionStore.current() ?: error("Yerel session bulunamadı.")
        runCatching { apiFactory.create(backendUrl).deviceSessions() }
            .recoverCatching { error ->
                if (error is HttpException && error.code() == 401) {
                    refresh(backendUrl)
                    apiFactory.create(backendUrl).deviceSessions()
                } else throw error
            }.getOrThrow()
        return sessionStore.current()?.user ?: stored.user ?: error("Session kullanıcı bilgisi içermiyor.")
    }

    suspend fun login(backendUrl: String, identifier: String, password: String): UserDto {
        val device = deviceIdentity.descriptor()
        val response = apiFactory.create(backendUrl).deviceLogin(DeviceLoginRequest(identifier.trim(), password, device))
        persist(response, backendUrl)
        registerDeviceFailClosed(backendUrl, device)
        return response.user
    }

    suspend fun enroll(backendUrl: String, username: String, email: String, password: String): UserDto {
        val device = deviceIdentity.descriptor()
        val response = apiFactory.create(backendUrl).deviceEnroll(DeviceEnrollRequest(username.trim(), email.trim(), password, device))
        persist(response, backendUrl)
        registerDeviceFailClosed(backendUrl, device)
        return response.user
    }

    suspend fun guest(backendUrl: String): UserDto {
        val device = deviceIdentity.descriptor()
        val response = apiFactory.create(backendUrl).deviceGuest(DeviceGuestRequest(device))
        persist(response, backendUrl)
        registerDeviceFailClosed(backendUrl, device)
        return response.user
    }

    suspend fun refresh(backendUrl: String): DeviceAuthResponse {
        val refreshToken = sessionStore.current()?.refreshToken ?: error("Refresh token bulunamadı.")
        val response = apiFactory.create(backendUrl).deviceRefresh(RefreshRequest(refreshToken))
        persist(response, backendUrl)
        return response
    }

    suspend fun logout(backendUrl: String) {
        val refreshToken = sessionStore.current()?.refreshToken
        runCatching { apiFactory.create(backendUrl).deviceLogout(LogoutRequest(refreshToken)) }
        sessionStore.clear()
    }

    suspend fun <T> withRefresh(backendUrl: String, call: suspend () -> T): T {
        return try {
            call()
        } catch (error: HttpException) {
            if (error.code() != 401) throw error
            val failedAccessToken = sessionStore.current()?.accessToken
            try {
                refreshMutex.withLock {
                    if (sessionStore.current()?.accessToken == failedAccessToken) {
                        refresh(backendUrl)
                    }
                }
                call()
            } catch (retryError: Throwable) {
                if (retryError is HttpException && retryError.code() == 401) {
                    sessionStore.clear()
                }
                throw retryError
            }
        }
    }

    private fun persist(response: DeviceAuthResponse, backendUrl: String) {
        require(response.tokenType.equals("Bearer", ignoreCase = true))
        val normalizedBackendUrl = ai.xultron.app.core.network.BackendEndpoint.normalize(backendUrl)
            ?: error("Backend URL doğrulanamadı.")
        sessionStore.update {
            it.copy(
                backendBaseUrl = normalizedBackendUrl,
                user = response.user,
                accessToken = response.accessToken,
                refreshToken = response.refreshToken,
                accessExpiresAt = response.accessExpiresAt,
                refreshExpiresAt = response.refreshExpiresAt,
                sessionId = response.session.sessionId ?: response.session.id,
                deviceId = response.session.deviceId ?: response.session.device?.id,
            )
        }
    }

    private suspend fun registerDeviceFailClosed(backendUrl: String, device: ai.xultron.app.core.network.DeviceDescriptorDto) {
        runCatching { apiFactory.create(backendUrl).registerDevice(device) }
            .onFailure {
                sessionStore.clear()
                throw IllegalStateException("Cihaz kaydı doğrulanamadı; session güvenli biçimde kapatıldı.", it)
            }
    }
}
