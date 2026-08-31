package ai.xultron.app.core.auth

import ai.xultron.app.core.network.UserDto
import ai.xultron.app.core.security.SecretStorage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class EncryptedSessionStoreTest {
    @Test
    fun `session survives recreation through the secret storage contract`() {
        val storage = FakeSecretStorage()
        val store = EncryptedSessionStore(storage)
        store.replace(
            StoredSession(
                user = UserDto("usr_1", "nuri"),
                accessToken = "mat_secret",
                refreshToken = "mrt_secret",
                deviceId = "dev_1",
            ),
        )

        val restored = EncryptedSessionStore(storage).current()
        assertEquals("nuri", restored?.user?.username)
        assertEquals("dev_1", restored?.deviceId)
    }

    @Test
    fun `corrupt encrypted payload is cleared fail closed`() {
        val storage = FakeSecretStorage("not-json")
        val store = EncryptedSessionStore(storage)
        assertNull(store.current())
        assertNull(storage.value)
    }

    private class FakeSecretStorage(initial: String? = null) : SecretStorage {
        var value: String? = initial
        override fun read(): String? = value
        override fun write(value: String) { this.value = value }
        override fun clear() { value = null }
    }
}
