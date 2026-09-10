package ai.xultron.app.ui

import android.content.Intent
import android.net.Uri
import android.webkit.WebChromeClient

/**
 * Creates the least-privileged document picker used for HTML file inputs.
 * ACTION_OPEN_DOCUMENT grants the selected content URI directly to this app, so general file
 * selection works without MANAGE_EXTERNAL_STORAGE or a runtime storage permission.
 */
internal object WebFileChooserPolicy {
    /**
     * Keeps the platform picker scoped to the media family requested by an HTML accept attribute.
     * ACTION_OPEN_DOCUMENT remains the transport for every case: it is available on our minimum
     * SDK, works with gallery and document providers, and gives this app only a user-selected
     * content URI. We intentionally do not use runtime storage or media permissions.
     */
    fun openDocumentIntent(params: WebChromeClient.FileChooserParams): Intent = openDocumentIntent(
        acceptTypes = params.acceptTypes,
        allowMultiple = params.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE,
    )

    internal fun openDocumentIntent(acceptTypes: Array<String>, allowMultiple: Boolean): Intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
        addCategory(Intent.CATEGORY_OPENABLE)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        val mimeTypes = requestedMimeTypes(acceptTypes)
        type = when (scopeFor(mimeTypes)) {
            PickerScope.IMAGES -> "image/*"
            PickerScope.VIDEOS -> "video/*"
            PickerScope.DOCUMENTS -> "*/*"
        }
        if (mimeTypes.isNotEmpty()) putExtra(Intent.EXTRA_MIME_TYPES, mimeTypes.toTypedArray())
        putExtra(Intent.EXTRA_ALLOW_MULTIPLE, allowMultiple)
    }

    /** Returns only provider-backed, non-empty selections. File paths are never exposed. */
    fun selectedContentUris(result: Intent?): Array<Uri>? {
        val uris = buildList {
            result?.data?.let(::add)
            result?.clipData?.let { clip ->
                for (index in 0 until clip.itemCount) clip.getItemAt(index).uri?.let(::add)
            }
        }.distinct()
        return uris.takeIf { it.isNotEmpty() && it.all { it.scheme == "content" } }?.toTypedArray()
    }

    /** Accept values are untrusted renderer input, so malformed values never influence an intent. */
    internal fun requestedMimeTypes(acceptTypes: Array<String>): List<String> = acceptTypes
        .flatMap { it.split(',') }
        .map { it.trim().lowercase() }
        .filter(::isMimeType)
        .distinct()

    internal fun scopeFor(mimeTypes: List<String>): PickerScope = when {
        mimeTypes.isNotEmpty() && mimeTypes.all { it.startsWith("image/") } -> PickerScope.IMAGES
        mimeTypes.isNotEmpty() && mimeTypes.all { it.startsWith("video/") } -> PickerScope.VIDEOS
        else -> PickerScope.DOCUMENTS
    }

    internal enum class PickerScope { IMAGES, VIDEOS, DOCUMENTS }

    private fun isMimeType(value: String): Boolean = MIME_TYPE.matches(value)

    private val MIME_TYPE = Regex("^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+*-]+$")
}
