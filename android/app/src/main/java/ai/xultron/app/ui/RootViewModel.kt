package ai.xultron.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import ai.xultron.app.AppContainer
import ai.xultron.app.core.network.UserDto
import ai.xultron.app.core.network.BackendEndpoint
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException

sealed interface ConnectionState {
    data object NotConfigured : ConnectionState
    data object Offline : ConnectionState
    data object Checking : ConnectionState
    data class Connected(val version: String?) : ConnectionState
    data class Unreachable(val message: String) : ConnectionState
}

data class RootUiState(
    val backendUrl: String = "",
    val connection: ConnectionState = ConnectionState.NotConfigured,
    val user: UserDto? = null,
    val authBusy: Boolean = false,
    val error: String? = null,
    val lowDataMode: Boolean = false,
)

class RootViewModel(private val container: AppContainer) : ViewModel() {
    private val mutableState = MutableStateFlow(RootUiState())
    val state: StateFlow<RootUiState> = mutableState.asStateFlow()

    init {
        viewModelScope.launch {
            combine(container.settingsStore.backendUrl, container.connectivityObserver.online) { url, online -> url to online }
                .collectLatest { (url, online) ->
                    mutableState.value = mutableState.value.copy(backendUrl = url, error = null)
                    when {
                        url.isBlank() -> mutableState.value = mutableState.value.copy(connection = ConnectionState.NotConfigured, user = null)
                        url == BackendEndpoint.LOCAL -> validateConnectionAndSession(url)
                        !online -> mutableState.value = mutableState.value.copy(
                            connection = ConnectionState.Offline,
                            user = container.sessionStore.current()?.user,
                        )
                        else -> validateConnectionAndSession(url)
                    }
                }
        }
        viewModelScope.launch {
            container.settingsStore.lowDataMode.collect { enabled ->
                mutableState.value = mutableState.value.copy(lowDataMode = enabled)
            }
        }
    }

    fun saveBackendUrl(value: String) = viewModelScope.launch {
        val result = container.settingsStore.setBackendUrl(value)
        result.getOrNull()?.let { normalized ->
            val sessionBackend = container.sessionStore.current()?.backendBaseUrl
            if (sessionBackend != null && sessionBackend != normalized) {
                container.sessionStore.clear()
                mutableState.value = mutableState.value.copy(user = null)
            }
        }
        result.exceptionOrNull()?.let { error ->
            mutableState.value = mutableState.value.copy(error = error.message)
        }
    }

    fun login(identifier: String, password: String) = authenticate {
        container.authRepository.login(requireBackendUrl(), identifier, password)
    }

    fun enroll(username: String, email: String, password: String) = authenticate {
        container.authRepository.enroll(requireBackendUrl(), username, email, password)
    }

    fun continueAsGuest() = authenticate {
        container.authRepository.guest(requireBackendUrl())
    }

    fun logout() = viewModelScope.launch {
        val backendUrl = mutableState.value.backendUrl
        mutableState.value = mutableState.value.copy(authBusy = true, error = null)
        container.authRepository.logout(backendUrl)
        mutableState.value = mutableState.value.copy(user = null, authBusy = false)
    }

    fun retryConnection() = viewModelScope.launch {
        val url = mutableState.value.backendUrl
        if (url.isNotBlank()) validateConnectionAndSession(url)
    }

    fun setLowDataMode(enabled: Boolean) = viewModelScope.launch {
        container.settingsStore.setLowDataMode(enabled)
    }

    private fun authenticate(block: suspend () -> UserDto) = viewModelScope.launch {
        if (mutableState.value.connection !is ConnectionState.Connected) {
            mutableState.value = mutableState.value.copy(error = "Backend bağlantısı kurulmadan oturum açılamaz.")
            return@launch
        }
        mutableState.value = mutableState.value.copy(authBusy = true, error = null)
        runCatching { block() }
            .onSuccess { mutableState.value = mutableState.value.copy(user = it, authBusy = false) }
            .onFailure { mutableState.value = mutableState.value.copy(authBusy = false, error = it.userMessage()) }
    }

    private suspend fun validateConnectionAndSession(url: String) {
        mutableState.value = mutableState.value.copy(connection = ConnectionState.Checking)
        runCatching { container.repository.health(url) }
            .onSuccess { health ->
                mutableState.value = mutableState.value.copy(connection = ConnectionState.Connected(health.version))
                if (container.sessionStore.current() != null) {
                    runCatching { container.authRepository.restore(url) }
                        .onSuccess { user -> mutableState.value = mutableState.value.copy(user = user) }
                        .onFailure {
                            container.sessionStore.clear()
                            mutableState.value = mutableState.value.copy(user = null)
                        }
                }
            }
            .onFailure { error ->
                mutableState.value = mutableState.value.copy(
                    connection = ConnectionState.Unreachable(error.userMessage()),
                    user = container.sessionStore.current()?.user,
                )
            }
    }

    private fun requireBackendUrl(): String = mutableState.value.backendUrl.ifBlank {
        throw IllegalStateException("Backend URL ayarlanmamış.")
    }
}

private fun Throwable.userMessage(): String = when (this) {
    is HttpException -> "Backend isteği başarısız oldu (HTTP ${code()})."
    is IOException -> "Backend erişilemiyor. Bağlantınızı ve URL'yi kontrol edin."
    else -> message ?: "Beklenmeyen bir hata oluştu."
}

class RootViewModelFactory(private val container: AppContainer) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass.isAssignableFrom(RootViewModel::class.java))
        return RootViewModel(container) as T
    }
}
