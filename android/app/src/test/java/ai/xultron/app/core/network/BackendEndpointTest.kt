package ai.xultron.app.core.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class BackendEndpointTest {
    @Test
    fun `normalizes an https backend to the v1 base url`() {
        assertEquals("https://example.com/api/v1/", BackendEndpoint.normalize(" https://example.com/ "))
        assertEquals("https://example.com/x/api/v1/", BackendEndpoint.normalize("https://example.com/x"))
        assertEquals("https://example.com/api/v1/", BackendEndpoint.normalize("https://example.com/api/v1"))
    }

    @Test
    fun `rejects cleartext credentials query and fragments`() {
        assertNull(BackendEndpoint.normalize("http://example.com"))
        assertNull(BackendEndpoint.normalize("https://user:pass@example.com"))
        assertNull(BackendEndpoint.normalize("https://example.com?token=secret"))
        assertNull(BackendEndpoint.normalize("https://example.com/#fragment"))
    }
}
