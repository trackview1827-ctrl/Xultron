package ai.xultron.app.core.auth

import ai.xultron.app.core.network.UserDto
import ai.xultron.app.core.security.SecretStorage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

@Serializable
data class StoredSession(
    val backendBaseUrl: String? = null,
    val user: UserDto? = null,
    val accessToken: String? = null,
    val refreshToken: String? = null,
    val accessExpiresAt: String? = null,
    val refreshExpiresAt: String? = null,
    val sessionId: String? = null,
    val deviceId: String? = null,
)

interface SessionStore {
    val state: StateFlow<StoredSession?>
    fun current(): StoredSession?
    fun replace(session: StoredSession)
    fun update(transform: (StoredSession) -> StoredSession)
    fun clear()
}

class EncryptedSessionStore(
    private val storage: SecretStorage,
    private val json: Json = Json { ignoreUnknownKeys = true },
) : SessionStore {
    private val lock = ReentrantLock()
    private val mutableState = MutableStateFlow(readFailClosed())
    override val state: StateFlow<StoredSession?> = mutableState

    override fun current(): StoredSession? = lock.withLock { mutableState.value }

    override fun replace(session: StoredSession) = lock.withLock {
        storage.write(json.encodeToString(StoredSession.serializer(), session))
        mutableState.value = session
    }

    override fun update(transform: (StoredSession) -> StoredSession) = lock.withLock {
        replace(transform(mutableState.value ?: StoredSession()))
    }

    override fun clear() = lock.withLock {
        storage.clear()
        mutableState.value = null
    }

    private fun readFailClosed(): StoredSession? {
        val encoded = storage.read() ?: return null
        return runCatching { json.decodeFromString(StoredSession.serializer(), encoded) }
            .getOrElse {
                storage.clear()
                null
            }
    }
}
