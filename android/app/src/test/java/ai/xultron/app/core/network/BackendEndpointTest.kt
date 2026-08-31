package ai.xultron.app.core.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import okhttp3.HttpUrl.Companion.toHttpUrl
import ai.xultron.app.ui.WebFrontendUrl

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
    fun `accepts the same-device Termux backend`() {
        assertEquals(
            "http://127.0.0.1:5000/api/v1/",
            BackendEndpoint.normalize("http://127.0.0.1:5000"),
        )
        assertEquals(
            "http://localhost:5000/api/v1/",
            BackendEndpoint.normalize("http://localhost:5000/"),
        )
    }

    @Test
    fun `rejects cleartext credentials query and fragments`() {
        assertNull(BackendEndpoint.normalize("http://example.com"))
        assertNull(BackendEndpoint.normalize("http://192.168.1.10:5000"))
        assertNull(BackendEndpoint.normalize("http://127.0.0.1:8080"))
        assertNull(BackendEndpoint.normalize("https://user:pass@example.com"))
        assertNull(BackendEndpoint.normalize("https://example.com?token=secret"))
        assertNull(BackendEndpoint.normalize("https://example.com/#fragment"))
    }

    @Test
    fun `web frontend root follows the backend path`() {
        val root = requireNotNull(WebFrontendUrl.rootForBackend("https://example.com/x/api/v1/"))
        assertEquals("https://example.com/x/", root.toString())
        assertTrue(WebFrontendUrl.isAllowedNavigation("https://example.com/x/settings".toHttpUrl(), root))
        assertFalse(WebFrontendUrl.isAllowedNavigation("https://evil.example/x/settings".toHttpUrl(), root))
        assertTrue(WebFrontendUrl.isAllowedOrigin("https://example.com/".toHttpUrl(), root))
        assertFalse(WebFrontendUrl.isAllowedOrigin("https://example.com.evil.test/".toHttpUrl(), root))
        assertFalse(WebFrontendUrl.isAllowedOrigin("http://example.com/".toHttpUrl(), root))
    }

    @Test
    fun `web frontend allows only the explicit OpenAI authorization origin`() {
        assertTrue(WebFrontendUrl.isAllowedOAuthNavigation("https://auth.openai.com/oauth/authorize".toHttpUrl()))
        assertFalse(WebFrontendUrl.isAllowedOAuthNavigation("https://openai.com/oauth/authorize".toHttpUrl()))
        assertFalse(WebFrontendUrl.isAllowedOAuthNavigation("http://auth.openai.com/oauth/authorize".toHttpUrl()))
        assertFalse(WebFrontendUrl.isAllowedOAuthNavigation("https://auth.openai.com.evil.test/".toHttpUrl()))
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
