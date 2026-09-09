package ai.xultron.app.widget

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Static contract checks keep the AppWidget registration and its security boundary explicit.
 * Android framework rendering is covered by the debug build resource linker.
 */
class XultronAppWidgetContractTest {
    @Test
    fun `provider metadata declares a resizable four by three home screen widget`() {
        val metadata = androidFile("src/main/res/xml/xultron_app_widget_info.xml").readText()

        assertContains(metadata, "android:initialLayout=\"@layout/xultron_app_widget\"")
        assertContains(metadata, "android:minWidth=\"250dp\"")
        assertContains(metadata, "android:minHeight=\"132dp\"")
        assertContains(metadata, "android:minResizeWidth=\"110dp\"")
        assertContains(metadata, "android:minResizeHeight=\"132dp\"")
        assertContains(metadata, "android:resizeMode=\"horizontal|vertical\"")
        assertContains(metadata, "android:targetCellWidth=\"4\"")
        assertContains(metadata, "android:targetCellHeight=\"3\"")
        assertContains(metadata, "android:widgetCategory=\"home_screen\"")
    }

    @Test
    fun `widget is private and opens MainActivity with an immutable pending intent`() {
        val manifest = androidFile("src/main/AndroidManifest.xml").readText()
        val provider = androidFile(
            "src/main/java/ai/xultron/app/widget/XultronAppWidgetProvider.kt",
        ).readText()

        assertContains(manifest, "android:name=\".widget.XultronAppWidgetProvider\"")
        assertContains(manifest, "android:exported=\"false\"")
        assertContains(manifest, "android:resource=\"@xml/xultron_app_widget_info\"")
        assertContains(provider, "Intent(context, MainActivity::class.java)")
        assertContains(provider, "PendingIntent.FLAG_IMMUTABLE")
        assertContains(provider, "setOnClickPendingIntent")
    }

    @Test
    fun `widget copy only presents an app shortcut`() {
        val strings = androidFile("src/main/res/values/strings.xml").readText()

        assertContains(strings, "A shortcut that opens Xultron.")
        assertContains(strings, "Open the app to continue.")
    }

    private fun androidFile(relativePath: String): File {
        val moduleRelative = File(relativePath)
        return if (moduleRelative.isFile) moduleRelative else File("app/$relativePath")
    }

    private fun assertContains(content: String, expected: String) {
        assertTrue("Expected <$expected> in static AppWidget contract", content.contains(expected))
    }
}
