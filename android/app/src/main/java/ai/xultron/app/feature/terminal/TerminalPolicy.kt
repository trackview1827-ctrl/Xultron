package ai.xultron.app.feature.terminal

import java.io.File
import java.nio.file.Files

/** Immutable limits: callers cannot enlarge them with a backend payload. */
data class TerminalBounds(
    val timeoutMs: Long = 1_000,
    val outputByteLimit: Int = 4_096,
) {
    init {
        require(timeoutMs in 1..5_000)
        require(outputByteLimit in 1..16_384)
    }
}

data class TerminalPolicy(
    val mode: TerminalMode,
    val bounds: TerminalBounds = TerminalBounds(),
    val allowNetwork: Boolean = false,
) {
    init {
        require(!allowNetwork) { "Terminal network access is not supported." }
    }
}

/** POSIX path validation is intentionally separate from SAF document references. */
object CanonicalPathValidator {
    private val forbiddenCharacters = Regex("[\\u0000\\$`;&|<>()*?\\[\\]{}'\\\"\\\\]")

    fun validateRelativePath(root: File, rawPath: String): PathValidation {
        if (rawPath.isBlank()) return PathValidation.Rejected(PathRejection.EMPTY)
        if (rawPath.startsWith("content://")) return PathValidation.Rejected(PathRejection.SAF_URI_NOT_POSIX)
        if (rawPath.startsWith('/') || rawPath.startsWith('\\')) return PathValidation.Rejected(PathRejection.ABSOLUTE_PATH)
        if (forbiddenCharacters.containsMatchIn(rawPath)) return PathValidation.Rejected(PathRejection.SHELL_CHARACTER)

        val components = rawPath.split('/', '\\')
        if (components.any { it.isEmpty() || it == "." || it == ".." }) {
            return PathValidation.Rejected(PathRejection.TRAVERSAL)
        }

        val canonicalRoot = root.canonicalFile
        var cursor = canonicalRoot
        for (component in components) {
            cursor = File(cursor, component)
            if (cursor.exists() && Files.isSymbolicLink(cursor.toPath())) {
                return PathValidation.Rejected(PathRejection.SYMLINK)
            }
        }
        val canonicalCandidate = cursor.canonicalFile
        if (!canonicalCandidate.toPath().startsWith(canonicalRoot.toPath())) {
            return PathValidation.Rejected(PathRejection.OUTSIDE_ROOT)
        }
        return PathValidation.Allowed(canonicalCandidate)
    }
}

sealed interface PathValidation {
    data class Allowed(val file: File) : PathValidation
    data class Rejected(val reason: PathRejection) : PathValidation
}

enum class PathRejection {
    EMPTY,
    ABSOLUTE_PATH,
    TRAVERSAL,
    SHELL_CHARACTER,
    SYMLINK,
    OUTSIDE_ROOT,
    SAF_URI_NOT_POSIX,
}
