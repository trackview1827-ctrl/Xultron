package ai.xultron.app.feature.terminal

/**
 * The terminal boundary accepts only these local, versioned action identifiers.
 * It deliberately has no API for command strings, executable paths, or environment maps.
 */
@JvmInline
value class TerminalActionId(val value: String)

enum class TerminalMode {
    FULL_ACCESS,
    RESTRICTED_ACCESS,
    XULTRON_DIRECTORY_ONLY,
    NO_TERMINAL_ACCESS,
}

enum class TerminalAdapterKind {
    APP_SANDBOX,
    TERMUX,
    SHIZUKU,
    ROOT,
}

data class ConfirmationMetadata(
    val approvedByUser: Boolean,
    val actionId: TerminalActionId,
    val requestId: String,
    val nonce: String,
    val approvedAtEpochMs: Long,
)

data class TerminalActionRequest(
    val actionId: TerminalActionId,
    val schemaVersion: Int,
    val requestId: String,
    val issuedAtEpochMs: Long,
    val expiresAtEpochMs: Long,
    val capabilityApproved: Boolean,
    val confirmation: ConfirmationMetadata? = null,
)

data class TerminalAuditRecord(
    val requestId: String,
    val actionId: TerminalActionId,
    val schemaVersion: Int,
    val mode: TerminalMode,
    val adapter: TerminalAdapterKind,
    val outcome: TerminalAuditOutcome,
    val reason: String?,
    val confirmationNonce: String?,
    val outputBytes: Int,
    val startedAtEpochMs: Long,
    val completedAtEpochMs: Long,
)

enum class TerminalAuditOutcome {
    ALLOWED,
    DENIED,
    FAILED,
    TIMED_OUT,
    OUTPUT_TRUNCATED,
}

sealed interface TerminalResult {
    val audit: TerminalAuditRecord

    data class Completed(
        val output: String,
        override val audit: TerminalAuditRecord,
    ) : TerminalResult

    data class Rejected(
        val reason: TerminalRejection,
        override val audit: TerminalAuditRecord,
    ) : TerminalResult
}

enum class TerminalRejection {
    TERMINAL_DISABLED,
    CAPABILITY_NOT_APPROVED,
    UNKNOWN_ACTION,
    UNSUPPORTED_SCHEMA,
    EXPIRED_REQUEST,
    INVALID_REQUEST_ID,
    CONFIRMATION_REQUIRED,
    INVALID_CONFIRMATION,
    CONFIRMATION_REPLAYED,
    EXECUTOR_UNAVAILABLE,
    POLICY_VIOLATION,
    TIME_LIMIT_EXCEEDED,
}
