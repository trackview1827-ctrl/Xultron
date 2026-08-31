package ai.xultron.app.ui

import android.annotation.SuppressLint
import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import ai.xultron.app.BuildConfig
import ai.xultron.app.core.network.BackendEndpoint
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

internal fun locationPermissionGranted(result: Map<String, Boolean>): Boolean =
    result[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
        result[Manifest.permission.ACCESS_COARSE_LOCATION] == true

internal fun requestedPermissionsGranted(
    requested: Set<String>,
    result: Map<String, Boolean>,
): Boolean = requested.isNotEmpty() && requested.all { result[it] == true }

private data class PendingWebPermission(
    val request: PermissionRequest,
    val resources: Array<String>,
    val androidPermissions: Set<String>,
)

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun WebFrontendScreen(
    backendUrl: String,
    modifier: Modifier = Modifier,
    onChangeBackend: () -> Unit = {},
) {
    val rootUrl = remember(backendUrl) {
        if (backendUrl == BackendEndpoint.LOCAL) null else WebFrontendUrl.rootForBackend(backendUrl)
    }
    var loadError by remember(rootUrl) { mutableStateOf<String?>(null) }
    var pendingWebPermission by remember { mutableStateOf<PendingWebPermission?>(null) }
    var pendingGeoPermission by remember { mutableStateOf<Pair<String, GeolocationPermissions.Callback>?>(null) }
    val webPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val pending = pendingWebPermission
        pendingWebPermission = null
        if (pending != null) {
            if (requestedPermissionsGranted(pending.androidPermissions, result)) pending.request.grant(pending.resources)
            else pending.request.deny()
        }
    }
    val geoPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val pending = pendingGeoPermission
        pendingGeoPermission = null
        pending?.second?.invoke(pending.first, locationPermissionGranted(result), false)
    }

    if (rootUrl == null) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Web frontend için uzak HTTPS veya Termux loopback backend seçilmeli.", color = MaterialTheme.colorScheme.error)
            Text("Yerel gömülü backend yalnızca native UI tarafından kullanılır.", modifier = Modifier.padding(top = 8.dp))
        }
        return
    }

    if (loadError != null) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Web frontend yüklenemedi", style = MaterialTheme.typography.titleLarge)
            Text(loadError.orEmpty(), modifier = Modifier.padding(top = 8.dp))
            Button(onClick = { loadError = null }, modifier = Modifier.padding(top = 16.dp)) { Text("Yeniden dene") }
            Button(onClick = onChangeBackend, modifier = Modifier.padding(top = 8.dp)) { Text("Backend adresini değiştir") }
        }
        return
    }

    var webView by remember { mutableStateOf<WebView?>(null) }
    var canGoBack by remember { mutableStateOf(false) }
    BackHandler(enabled = canGoBack) {
        webView?.goBack()
        canGoBack = webView?.canGoBack() == true
    }

    AndroidView(
        modifier = modifier.fillMaxSize(),
        factory = { context ->
            WebView(context).apply {
                webView = this
                layoutParams = ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                )
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.cacheMode = WebSettings.LOAD_DEFAULT
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                settings.javaScriptCanOpenWindowsAutomatically = false
                settings.setSupportMultipleWindows(false)
                settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
                webChromeClient = object : WebChromeClient() {
                    override fun onPermissionRequest(request: PermissionRequest) {
                        val requestOrigin = request.origin.toString().toHttpUrlOrNull()
                        if (requestOrigin == null || !WebFrontendUrl.isAllowedOrigin(requestOrigin, rootUrl)) {
                            request.deny()
                            return
                        }
                        val grantableResources = request.resources.filter {
                            it == PermissionRequest.RESOURCE_AUDIO_CAPTURE || it == PermissionRequest.RESOURCE_VIDEO_CAPTURE
                        }
                        if (grantableResources.isEmpty() || grantableResources.size != request.resources.size) {
                            request.deny()
                            return
                        }
                        val required = buildList {
                            if (PermissionRequest.RESOURCE_AUDIO_CAPTURE in request.resources &&
                                ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED
                            ) add(Manifest.permission.RECORD_AUDIO)
                            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE in request.resources &&
                                ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED
                            ) add(Manifest.permission.CAMERA)
                        }
                        if (required.isEmpty()) request.grant(grantableResources.toTypedArray())
                        else {
                            pendingWebPermission?.request?.deny()
                            pendingWebPermission = PendingWebPermission(request, grantableResources.toTypedArray(), required.toSet())
                            webPermissionLauncher.launch(required.toTypedArray())
                        }
                    }

                    override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                        val requestOrigin = origin.toHttpUrlOrNull()
                        if (requestOrigin == null || !WebFrontendUrl.isAllowedOrigin(requestOrigin, rootUrl)) {
                            callback.invoke(origin, false, false)
                            return
                        }
                        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
                        ) callback.invoke(origin, true, false)
                        else {
                            pendingGeoPermission?.let { it.second.invoke(it.first, false, false) }
                            pendingGeoPermission = origin to callback
                            geoPermissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
                        }
                    }
                }
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                        val parsed = request.url.toString().toHttpUrlOrNull() ?: return true
                        return !WebFrontendUrl.isAllowedNavigation(parsed, rootUrl) &&
                            !WebFrontendUrl.isAllowedOAuthNavigation(parsed)
                    }

                    @Deprecated("Deprecated in API 24")
                    override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean {
                        val parsed = url.toHttpUrlOrNull() ?: return true
                        return !WebFrontendUrl.isAllowedNavigation(parsed, rootUrl) &&
                            !WebFrontendUrl.isAllowedOAuthNavigation(parsed)
                    }

                    override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                        loadError = null
                    }

                    override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                        if (request.isForMainFrame) {
                            loadError = "${error.errorCode}: ${error.description}"
                        }
                    }
                }
                if (BuildConfig.DEBUG) WebView.setWebContentsDebuggingEnabled(true)
                loadUrl(rootUrl.toString())
            }
        },
        update = { view ->
            webView = view
            canGoBack = view.canGoBack()
        },
    )
}
