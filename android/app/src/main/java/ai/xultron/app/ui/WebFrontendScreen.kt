package ai.xultron.app.ui

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
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
import ai.xultron.app.BuildConfig
import ai.xultron.app.core.network.BackendEndpoint
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

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
