package ai.xultron.app.ui

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Static contracts guard the security-sensitive WebView-to-SAF boundary. */
class WebFileChooserContractTest {
    @Test
    fun `manifest declares scoped media permissions but never all-files access`() {
        val manifest = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(File("src/main/AndroidManifest.xml"))
        val permissions = manifest.getElementsByTagName("uses-permission")
        val declared = (0 until permissions.length).associate { index ->
            val permission = permissions.item(index).attributes
            permission.getNamedItem("android:name").nodeValue to permission.getNamedItem("android:maxSdkVersion")?.nodeValue
        }

        assertTrue("android.permission.READ_MEDIA_IMAGES" in declared)
        assertTrue("android.permission.READ_MEDIA_VIDEO" in declared)
        assertEquals("32", declared["android.permission.READ_EXTERNAL_STORAGE"])
        assertFalse("android.permission.MANAGE_EXTERNAL_STORAGE" in declared)
    }

    @Test
    fun `picker is SAF read-only and never converts selected content to file paths`() {
        val policy = source("WebFileChooserPolicy.kt")
        assertTrue(policy.contains("Intent.ACTION_OPEN_DOCUMENT"))
        assertTrue(policy.contains("Intent.CATEGORY_OPENABLE"))
        assertTrue(policy.contains("Intent.FLAG_GRANT_READ_URI_PERMISSION"))
        assertTrue(policy.contains("it.scheme == \"content\""))
        assertFalse(policy.contains("MANAGE_EXTERNAL_STORAGE"))
        assertFalse(policy.contains(".path"))
        assertFalse(policy.contains("getRealPath"))
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
