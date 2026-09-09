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
    fun openDocumentIntent(params: WebChromeClient.FileChooserParams): Intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
        addCategory(Intent.CATEGORY_OPENABLE)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        type = "*/*"
        val mimeTypes = params.acceptTypes.filter(::isMimeType).distinct()
        if (mimeTypes.isNotEmpty()) putExtra(Intent.EXTRA_MIME_TYPES, mimeTypes.toTypedArray())
        putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE)
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

    private fun isMimeType(value: String): Boolean = MIME_TYPE.matches(value)

    private val MIME_TYPE = Regex("^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+*-]+$")
}
