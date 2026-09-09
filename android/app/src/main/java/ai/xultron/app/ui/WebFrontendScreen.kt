package ai.xultron.app.ui

import android.annotation.SuppressLint
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
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
import androidx.activity.result.ActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import ai.xultron.app.feature.voice.VoiceEnrollmentController
import ai.xultron.app.feature.voice.VoiceEnrollmentSnapshot
import ai.xultron.app.core.network.BackendEndpoint
import ai.xultron.app.service.VoiceServiceController
import ai.xultron.app.service.VoiceServiceState
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
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

private data class PendingVoicePermissionStart(
    val start: PendingVoiceStart,
    val permissions: Set<String>,
)

private data class PendingVoiceEnrollmentPermission(
    val enrollment: PendingVoiceEnrollment,
)

private data class PendingFileChooser(
    val callback: android.webkit.ValueCallback<Array<android.net.Uri>>,
    val trustedOrigin: String,
)

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun WebFrontendScreen(
    backendUrl: String,
    voiceServiceController: VoiceServiceController,
    voiceEnrollmentController: VoiceEnrollmentController,
    modifier: Modifier = Modifier,
    onChangeBackend: () -> Unit = {},
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val rootUrl = remember(backendUrl) {
        if (backendUrl == BackendEndpoint.LOCAL) null else WebFrontendUrl.rootForBackend(backendUrl)
    }
    var loadError by remember(rootUrl) { mutableStateOf<String?>(null) }
    var pendingWebPermission by remember { mutableStateOf<PendingWebPermission?>(null) }
    var pendingGeoPermission by remember { mutableStateOf<Pair<String, GeolocationPermissions.Callback>?>(null) }
    var pendingVoiceStart by remember { mutableStateOf<PendingVoiceStart?>(null) }
    var pendingVoicePermissionStart by remember { mutableStateOf<PendingVoicePermissionStart?>(null) }
    var pendingVoiceEnrollment by remember { mutableStateOf<PendingVoiceEnrollment?>(null) }
    var pendingVoiceEnrollmentPermission by remember { mutableStateOf<PendingVoiceEnrollmentPermission?>(null) }
    var pendingFileChooser by remember { mutableStateOf<PendingFileChooser?>(null) }
    var webView by remember { mutableStateOf<WebView?>(null) }
    val fileChooserLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result: ActivityResult ->
        val pending = pendingFileChooser
        pendingFileChooser = null
        val currentUrl = webView?.url?.toHttpUrlOrNull()
        val trustedCurrentOrigin = currentUrl?.let(WebFrontendUrl::originRule)
        val selected = if (
            result.resultCode == android.app.Activity.RESULT_OK &&
            trustedCurrentOrigin == pending?.trustedOrigin
        ) WebFileChooserPolicy.selectedContentUris(result.data) else null
        // A cancelled picker, navigation away from the trusted origin, or an invalid result
        // never supplies a URI to the renderer.
        pending?.callback?.onReceiveValue(selected)
    }
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
    val voicePermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val pending = pendingVoicePermissionStart
        pendingVoicePermissionStart = null
        if (pending != null) {
            if (requestedPermissionsGranted(pending.permissions, result)) pending.start.reply.status(pending.start.id, voiceServiceController.start().status())
            else pending.start.reply.error("microphone_or_notification_permission_denied")
        }
    }
    val enrollmentPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val pending = pendingVoiceEnrollmentPermission
        pendingVoiceEnrollmentPermission = null
        if (pending != null) {
            if (requestedPermissionsGranted(setOf(Manifest.permission.RECORD_AUDIO), result)) {
                val started = voiceEnrollmentController.capture { snapshot -> pending.enrollment.reply.enrollment(pending.enrollment.id, snapshot) }
                if (started.state != VoiceEnrollmentSnapshot.State.CAPTURING) pending.enrollment.reply.enrollment(pending.enrollment.id, started)
            } else pending.enrollment.reply.error("microphone_permission_denied")
        }
    }

    fun beginEnrollmentCapture(pending: PendingVoiceEnrollment) {
        if (voiceEnrollmentController.snapshot().state == VoiceEnrollmentSnapshot.State.CAPTURING) {
            pending.reply.error("enrollment_capture_in_progress")
            return
        }
        val started = voiceEnrollmentController.capture { snapshot -> pending.reply.enrollment(pending.id, snapshot) }
        if (started.state != VoiceEnrollmentSnapshot.State.CAPTURING) pending.reply.enrollment(pending.id, started)
    }

    fun requestEnrollment(pending: PendingVoiceEnrollment) {
        when (pending.operation) {
            PendingVoiceEnrollment.Operation.CLEAR -> pending.reply.enrollment(pending.id, voiceEnrollmentController.clear())
            PendingVoiceEnrollment.Operation.CAPTURE -> {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    beginEnrollmentCapture(pending)
                } else {
                    pendingVoiceEnrollmentPermission = PendingVoiceEnrollmentPermission(pending)
                    enrollmentPermissionLauncher.launch(arrayOf(Manifest.permission.RECORD_AUDIO))
                }
            }
        }
    }

    fun requestVoiceServiceStart(pending: PendingVoiceStart) {
        val status = voiceServiceController.start().status()
        val missingPermissions = when (status.blockReason?.name) {
            "MICROPHONE_PERMISSION_MISSING" -> setOf(Manifest.permission.RECORD_AUDIO)
            "NOTIFICATION_PERMISSION_MISSING" -> if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) setOf(Manifest.permission.POST_NOTIFICATIONS) else emptySet()
            else -> emptySet()
        }
        if (status.state == VoiceServiceState.BLOCKED && missingPermissions.isNotEmpty()) {
            pendingVoicePermissionStart = PendingVoicePermissionStart(pending, missingPermissions)
            voicePermissionLauncher.launch(missingPermissions.toTypedArray())
        } else pending.reply.status(pending.id, status)
    }

    pendingVoiceStart?.let { pending ->
        AlertDialog(
            onDismissRequest = {
                pendingVoiceStart = null
                pending.reply.status(pending.id, voiceServiceController.status())
            },
            title = { Text("Yerel uyandırma sözcüğü dinlemesi") },
            text = { Text("Xultron yerel mikrofon foreground service başlatacak ve kalıcı bir Android bildirimi gösterecek. Ham ses yüklenmez veya saklanmaz. Model mevcut değilse mikrofon açılmaz.") },
            confirmButton = {
                TextButton(onClick = {
                    pendingVoiceStart = null
                    requestVoiceServiceStart(pending)
                }) { Text("BAŞLAT") }
            },
            dismissButton = {
                TextButton(onClick = {
                    pendingVoiceStart = null
                    pending.reply.status(pending.id, voiceServiceController.status())
                }) { Text("İPTAL") }
            },
        )
    }

    pendingVoiceEnrollment?.let { pending ->
        val capture = pending.operation == PendingVoiceEnrollment.Operation.CAPTURE
        AlertDialog(
            onDismissRequest = { pendingVoiceEnrollment = null; pending.reply.error("enrollment_not_confirmed") },
            title = { Text(if (capture) "Yerel ses profili örneği" else "Yerel ses profilini sil") },
            text = {
                Text(
                    if (capture) "Xultron yaklaşık iki saniyelik tek bir örneği yalnızca kalite analizi için bellekte tutar. Ham ses yüklenmez, kaydedilmez ve iş bittiğinde silinir. Beş kabul edilmiş örnek yalnızca şifreli deneysel profil oluşturur, uyandırma modeli oluşturmaz."
                    else "Şifreli deneysel ses profili ve kayıt ilerlemesi bu cihazdan silinecek. Ham ses zaten tutulmaz.",
                )
            },
            confirmButton = { TextButton(onClick = { pendingVoiceEnrollment = null; requestEnrollment(pending) }) { Text(if (capture) "KAYDET" else "SİL") } },
            dismissButton = { TextButton(onClick = { pendingVoiceEnrollment = null; pending.reply.error("enrollment_not_confirmed") }) { Text("İPTAL") } },
        )
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
                // HTML file inputs receive only vetted ACTION_OPEN_DOCUMENT content:// URIs.
                // WebView needs content access enabled to stream that selected URI to the trusted
                // current origin. File URLs stay disabled and chooser callbacks reject all others.
                settings.allowContentAccess = true
                settings.javaScriptCanOpenWindowsAutomatically = false
                settings.setSupportMultipleWindows(false)
                settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
                if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
                    WebViewCompat.addWebMessageListener(
                        this,
                        "XultronVoicePort",
                        setOf(WebFrontendUrl.originRule(rootUrl)),
                        VoiceWebMessageBridge(
                            voiceServiceController,
                            voiceEnrollmentController,
                            WebFrontendUrl.originRule(rootUrl),
                            onStartConfirmationRequired = { pending ->
                                post {
                                    if (pendingVoiceStart == null && pendingVoicePermissionStart == null) pendingVoiceStart = pending
                                    else pending.reply.error("voice_request_in_progress")
                                }
                            },
                            onEnrollmentConfirmationRequired = { pending ->
                                post {
                                    if (pendingVoiceEnrollment == null && pendingVoiceEnrollmentPermission == null) pendingVoiceEnrollment = pending
                                    else pending.reply.error("enrollment_request_in_progress")
                                }
                            },
                        ),
                    )
                }
                webChromeClient = object : WebChromeClient() {
                    override fun onShowFileChooser(
                        view: WebView,
                        filePathCallback: android.webkit.ValueCallback<Array<android.net.Uri>>,
                        fileChooserParams: FileChooserParams,
                    ): Boolean {
                        val currentUrl = view.url?.toHttpUrlOrNull()
                        val trustedOrigin = currentUrl?.let(WebFrontendUrl::originRule)
                        // The callback does not include an origin. Bind it to the currently
                        // rendered, configured origin and reject concurrent chooser requests.
                        if (
                            trustedOrigin != WebFrontendUrl.originRule(rootUrl) ||
                            pendingFileChooser != null
                        ) {
                            filePathCallback.onReceiveValue(null)
                            return true
                        }
                        pendingFileChooser = PendingFileChooser(filePathCallback, trustedOrigin)
                        fileChooserLauncher.launch(WebFileChooserPolicy.openDocumentIntent(fileChooserParams))
                        return true
                    }

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

                    override fun onPermissionRequestCanceled(request: PermissionRequest) {
                        if (pendingWebPermission?.request == request) pendingWebPermission = null
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
        onRelease = { view ->
            pendingWebPermission?.request?.deny()
            pendingWebPermission = null
            pendingFileChooser?.callback?.onReceiveValue(null)
            pendingFileChooser = null
            pendingGeoPermission?.let { it.second.invoke(it.first, false, false) }
            pendingGeoPermission = null
            pendingVoiceStart?.let {
                it.reply.status(it.id, voiceServiceController.status())
                pendingVoiceStart = null
            }
            pendingVoicePermissionStart?.let {
                it.start.reply.status(it.start.id, voiceServiceController.status())
                pendingVoicePermissionStart = null
            }
            pendingVoiceEnrollment?.let {
                it.reply.error("webview_released")
                pendingVoiceEnrollment = null
            }
            pendingVoiceEnrollmentPermission?.let {
                it.enrollment.reply.error("webview_released")
                pendingVoiceEnrollmentPermission = null
            }
            if (webView === view) webView = null
            view.stopLoading()
            view.onPause()
            view.removeAllViews()
            view.destroy()
        },
    )
}
