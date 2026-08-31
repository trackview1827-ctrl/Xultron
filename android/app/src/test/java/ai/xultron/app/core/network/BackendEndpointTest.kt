package ai.xultron.app.core.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import okhttp3.HttpUrl.Companion.toHttpUrl

class BackendEndpointTest {
    @Test
    fun `normalizes an https backend to the v1 base url`() {
        assertEquals("https://example.com/api/v1/", BackendEndpoint.normalize(" https://example.com/ "))
        assertEquals("https://example.com/x/api/v1/", BackendEndpoint.normalize("https://example.com/x"))
        assertEquals("https://example.com/api/v1/", BackendEndpoint.normalize("https://example.com/api/v1"))
    }

    @Test
    fun `recognizes the app-private local backend`() {
        assertEquals(BackendEndpoint.LOCAL, BackendEndpoint.normalize(" local://xultron/ "))
    }

    @Test
    fun `rejects cleartext credentials query and fragments`() {
        assertNull(BackendEndpoint.normalize("http://example.com"))
        assertNull(BackendEndpoint.normalize("https://user:pass@example.com"))
        assertNull(BackendEndpoint.normalize("https://example.com?token=secret"))
        assertNull(BackendEndpoint.normalize("https://example.com/#fragment"))
    }

    @Test
    fun `session headers are bound to the exact backend origin and api base`() {
        val backend = "https://api.example.com/x/api/v1/"
        assertTrue(shouldAttachSessionHeaders("https://api.example.com/x/api/v1/conversations".toHttpUrl(), backend))
        assertFalse(shouldAttachSessionHeaders("https://evil.example/x/api/v1/conversations".toHttpUrl(), backend))
        assertFalse(shouldAttachSessionHeaders("https://api.example.com/other/api/v1/conversations".toHttpUrl(), backend))
        assertFalse(shouldAttachSessionHeaders("https://api.example.com.evil.test/x/api/v1/conversations".toHttpUrl(), backend))
    }

    @Test
    fun `unauthenticated device auth routes never receive stale bearer headers`() {
        val backend = "https://api.example.com/api/v1/"
        assertFalse(shouldAttachSessionHeaders("https://api.example.com/api/v1/device-auth/login".toHttpUrl(), backend))
        assertFalse(shouldAttachSessionHeaders("https://api.example.com/api/v1/device-auth/refresh".toHttpUrl(), backend))
        assertTrue(shouldAttachSessionHeaders("https://api.example.com/api/v1/device-auth/logout".toHttpUrl(), backend))
    }
}
