package ai.xultron.app.ui

import android.content.Intent
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Static contracts guard the security-sensitive WebView-to-SAF boundary. */
class WebFileChooserContractTest {
    @Test
    fun `manifest keeps SAF uploads free of broad storage and media permissions`() {
        val manifest = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(File("src/main/AndroidManifest.xml"))
        val permissions = manifest.getElementsByTagName("uses-permission")
        val declared = (0 until permissions.length).associate { index ->
            val permission = permissions.item(index).attributes
            permission.getNamedItem("android:name").nodeValue to permission.getNamedItem("android:maxSdkVersion")?.nodeValue
        }

        assertFalse("android.permission.READ_MEDIA_IMAGES" in declared)
        assertFalse("android.permission.READ_MEDIA_VIDEO" in declared)
        assertFalse("android.permission.READ_EXTERNAL_STORAGE" in declared)
        assertFalse("android.permission.MANAGE_EXTERNAL_STORAGE" in declared)
    }

    @Test
    fun `picker is SAF read-only and never converts selected content to file paths`() {
        val policy = source("WebFileChooserPolicy.kt")
        assertTrue(policy.contains("Intent.ACTION_OPEN_DOCUMENT"))
        assertTrue(policy.contains("Intent.CATEGORY_OPENABLE"))
        assertTrue(policy.contains("Intent.FLAG_GRANT_READ_URI_PERMISSION"))
        assertTrue(policy.contains("it.scheme == \"content\""))
        assertFalse(policy.contains("getRealPath"))
    }

    @Test
    fun `picker routes image and video accepts to gallery compatible MIME scopes`() {
        val policy = source("WebFileChooserPolicy.kt")
        assertTrue(policy.contains("PickerScope.IMAGES -> \"image/*\""))
        assertTrue(policy.contains("PickerScope.VIDEOS -> \"video/*\""))
        assertTrue(policy.contains("mimeTypes.all { it.startsWith(\"image/\") }"))
        assertTrue(policy.contains("mimeTypes.all { it.startsWith(\"video/\") }"))
        assertTrue(policy.contains("Intent.EXTRA_MIME_TYPES"))
    }

    @Test
    fun `image and video accepts select only their requested picker scope`() {
        assertEquals(
            WebFileChooserPolicy.PickerScope.IMAGES,
            WebFileChooserPolicy.scopeFor(WebFileChooserPolicy.requestedMimeTypes(arrayOf("image/*"))),
        )
        assertEquals(
            WebFileChooserPolicy.PickerScope.VIDEOS,
            WebFileChooserPolicy.scopeFor(WebFileChooserPolicy.requestedMimeTypes(arrayOf("video/mp4"))),
        )
        assertEquals(
            listOf("image/jpeg", "image/png"),
            WebFileChooserPolicy.requestedMimeTypes(arrayOf(" image/jpeg,IMAGE/PNG ")),
        )
    }

    @Test
    fun `picker falls back to general documents for ordinary mixed and malformed accepts`() {
        val policy = source("WebFileChooserPolicy.kt")
        assertTrue(policy.contains("PickerScope.DOCUMENTS -> \"*/*\""))
        assertTrue(policy.contains(".filter(::isMimeType)"))
        assertTrue(policy.contains("Regex(\"^[A-Za-z0-9!#$&^_.+-]+/"))
    }

    @Test
    fun `mixed ordinary and malformed accepts fail closed to the general document scope`() {
        assertEquals(
            WebFileChooserPolicy.PickerScope.DOCUMENTS,
            WebFileChooserPolicy.scopeFor(WebFileChooserPolicy.requestedMimeTypes(arrayOf("image/*", "video/*"))),
        )
        assertEquals(
            emptyList<String>(),
            WebFileChooserPolicy.requestedMimeTypes(arrayOf("image/*;unsafe", "not-a-mime", "../image/png")),
        )
        assertEquals(
            WebFileChooserPolicy.PickerScope.DOCUMENTS,
            WebFileChooserPolicy.scopeFor(emptyList()),
        )
    }

    @Test
    fun `supported text attachments use the document picker with exact MIME types`() {
        val types = arrayOf("text/plain", "text/markdown", "application/json", "text/csv")
        val intent = WebFileChooserPolicy.openDocumentIntent(types, allowMultiple = false)
        assertEquals(WebFileChooserPolicy.PickerScope.DOCUMENTS, WebFileChooserPolicy.scopeFor(WebFileChooserPolicy.requestedMimeTypes(types)))
        assertEquals("*/*", intent.type)
        assertEquals(types.toList(), intent.getStringArrayExtra(Intent.EXTRA_MIME_TYPES)?.toList())
    }

    @Test
    fun `WebView chooser is origin-bound rejects duplicates and fails closed`() {
        val screen = source("WebFrontendScreen.kt")
        assertTrue(screen.contains("override fun onShowFileChooser"))
        assertTrue(screen.contains("trustedOrigin != WebFrontendUrl.originRule(rootUrl)"))
        assertTrue(screen.contains("pendingFileChooser != null"))
        assertTrue(screen.contains("trustedCurrentOrigin == pending?.trustedOrigin"))
        assertTrue(screen.contains("filePathCallback.onReceiveValue(null)"))
        assertTrue(screen.contains("pendingFileChooser?.callback?.onReceiveValue(null)"))
        assertTrue(screen.contains("settings.allowContentAccess = true"))
        assertFalse(screen.contains("Manifest.permission.READ_MEDIA_IMAGES"))
        assertFalse(screen.contains("Manifest.permission.READ_MEDIA_VIDEO"))
    }

    private fun source(fileName: String): String =
        File("src/main/java/ai/xultron/app/ui/$fileName").readText()
}
