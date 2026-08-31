package ai.xultron.app.core.network

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import ai.xultron.app.core.auth.SessionStore
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import retrofit2.Retrofit
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

object BackendEndpoint {
    const val LOCAL = "local://xultron"

    fun normalize(raw: String): String? {
        val candidate = raw.trim().trimEnd('/')
        if (candidate == LOCAL) return LOCAL
        val url = candidate.toHttpUrlOrNull() ?: return null
        if (url.username.isNotEmpty() || url.password.isNotEmpty()) return null
        if (url.query != null || url.fragment != null) return null
        val loopback = url.host == "127.0.0.1" || url.host == "localhost"
        val allowed = url.scheme == "https" ||
            (url.scheme == "http" && loopback && url.port == 5000)
        if (!allowed) return null
        val path = url.encodedPath.trimEnd('/')
        val apiPath = if (path.endsWith("/api/v1")) path else "$path/api/v1"
        return url.newBuilder().encodedPath("$apiPath/").build().toString()
    }
}

internal fun shouldAttachSessionHeaders(requestUrl: okhttp3.HttpUrl, backendBaseUrl: String?): Boolean {
    val sessionUrl = backendBaseUrl?.toHttpUrlOrNull() ?: return false
    val sameBackend = requestUrl.scheme == sessionUrl.scheme &&
        requestUrl.host == sessionUrl.host &&
        requestUrl.port == sessionUrl.port &&
        requestUrl.encodedPath.startsWith(sessionUrl.encodedPath)
    return sameBackend && !isAuthlessDeviceAuthRoute(requestUrl.encodedPath)
}

internal fun isAuthlessDeviceAuthRoute(path: String): Boolean = AUTHLESS_DEVICE_AUTH_PATHS.any(path::endsWith)

private val AUTHLESS_DEVICE_AUTH_PATHS = setOf(
    "/device-auth/enroll",
    "/device-auth/login",
    "/device-auth/guest",
    "/device-auth/refresh",
)

class SessionHeaderInterceptor(private val sessionStore: SessionStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val builder = original.newBuilder().header("X-Request-ID", "android_${UUID.randomUUID()}")
        val session = sessionStore.current()
        if (session != null && shouldAttachSessionHeaders(original.url, session.backendBaseUrl)) {
            session.accessToken?.takeIf { it.isNotBlank() }?.let { builder.header("Authorization", "Bearer $it") }
            session.deviceId?.takeIf { it.isNotBlank() }?.let { builder.header("X-Device-ID", it) }
        }
        return chain.proceed(builder.build())
    }

}

class ApiFactory(private val sessionStore: SessionStore) {
    private val cache = ConcurrentHashMap<String, XultronApi>()
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    fun create(backendUrl: String): XultronApi {
        val normalized = BackendEndpoint.normalize(backendUrl)
            ?: throw IllegalArgumentException("Backend URL must be HTTPS, or Termux loopback http://127.0.0.1:5000.")
        return cache.getOrPut(normalized) {
            val clientBuilder = OkHttpClient.Builder()
                .addInterceptor(SessionHeaderInterceptor(sessionStore))
            Retrofit.Builder()
                .baseUrl(normalized)
                .client(clientBuilder.build())
                .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                .build()
                .create(XultronApi::class.java)
        }
    }
}

class ConnectivityObserver(context: Context) {
    private val manager = context.getSystemService(ConnectivityManager::class.java)

    val online: Flow<Boolean> = callbackFlow {
        fun emitCurrent() {
            val network = manager.activeNetwork
            val capabilities = network?.let(manager::getNetworkCapabilities)
            trySend(capabilities?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true)
        }
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = emitCurrent()
            override fun onLost(network: Network) = emitCurrent()
            override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) = emitCurrent()
        }
        emitCurrent()
        manager.registerDefaultNetworkCallback(callback)
        awaitClose { manager.unregisterNetworkCallback(callback) }
    }.distinctUntilChanged()
}
