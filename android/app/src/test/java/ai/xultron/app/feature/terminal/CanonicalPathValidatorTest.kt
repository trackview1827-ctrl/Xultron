package ai.xultron.app.feature.terminal

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CanonicalPathValidatorTest {
    @Test
    fun `valid relative path resolves only below canonical root`() {
        withRoot { root ->
            val result = CanonicalPathValidator.validateRelativePath(root, "notes/today.txt")
            assertTrue(result is PathValidation.Allowed)
            assertTrue((result as PathValidation.Allowed).file.path.startsWith(root.canonicalPath))
        }
    }

    @Test
    fun `traversal null shell expansion chaining and absolute paths are rejected`() {
        withRoot { root ->
            val cases = mapOf(
                "../secret" to PathRejection.TRAVERSAL,
                "notes/../secret" to PathRejection.TRAVERSAL,
                "notes/\u0000secret" to PathRejection.SHELL_CHARACTER,
                "notes/${'$'}HOME" to PathRejection.SHELL_CHARACTER,
                "notes/${'$'}(id)" to PathRejection.SHELL_CHARACTER,
                "notes/a;id" to PathRejection.SHELL_CHARACTER,
                "/data/local/tmp" to PathRejection.ABSOLUTE_PATH,
            )
            cases.forEach { (raw, expected) ->
                val result = CanonicalPathValidator.validateRelativePath(root, raw)
                assertEquals("$raw must be denied", expected, (result as PathValidation.Rejected).reason)
            }
        }
    }

    @Test
    fun `saf uri is never interpreted as a posix path`() {
        withRoot { root ->
            val result = CanonicalPathValidator.validateRelativePath(root, "content://com.android.providers.documents/tree/1")
            assertEquals(PathRejection.SAF_URI_NOT_POSIX, (result as PathValidation.Rejected).reason)
        }
    }

    @Test
    fun `existing symlink is rejected even when target is inside root`() {
        withRoot { root ->
            val target = File(root, "target").apply { mkdirs() }
            val link = File(root, "shortcut")
            Files.createSymbolicLink(link.toPath(), target.toPath())
            val result = CanonicalPathValidator.validateRelativePath(root, "shortcut/private.txt")
            assertEquals(PathRejection.SYMLINK, (result as PathValidation.Rejected).reason)
        }
    }

    private fun withRoot(block: (File) -> Unit) {
        val root = Files.createTempDirectory("xultron-terminal-").toFile()
        try {
            block(root)
        } finally {
            root.deleteRecursively()
        }
    }
}
