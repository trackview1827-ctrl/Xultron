package ai.xultron.app.ui

import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/** Pure URL policy shared by the WebView container and its unit tests. */
object WebFrontendUrl {
    fun rootForBackend(backendUrl: String): HttpUrl? {
        val parsed = backendUrl.toHttpUrlOrNull() ?: return null
        val apiPath = parsed.encodedPath.trimEnd('/')
        val rootPath = apiPath.removeSuffix("/api/v1").ifBlank { "/" }
        return parsed.newBuilder()
            .encodedPath(if (rootPath.endsWith('/')) rootPath else "$rootPath/")
            .query(null)
            .fragment(null)
            .build()
    }

    fun isAllowedNavigation(url: HttpUrl, root: HttpUrl): Boolean =
        url.scheme == root.scheme &&
            url.host == root.host &&
            url.port == root.port &&
            url.encodedPath.startsWith(root.encodedPath)
}
