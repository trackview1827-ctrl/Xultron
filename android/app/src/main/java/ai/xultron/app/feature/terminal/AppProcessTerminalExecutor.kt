package ai.xultron.app.feature.terminal

import java.nio.charset.StandardCharsets

fun interface EpochClock { fun nowMs(): Long }
fun interface MonotonicClock { fun nowMs(): Long }

class AppProcessTerminalExecutor(
    private val policy: TerminalPolicy,
    private val epochClock: EpochClock = EpochClock { System.currentTimeMillis() },
    private val monotonicClock: MonotonicClock = MonotonicClock { System.nanoTime() / 1_000_000 },
    private val confirmationReplayGuard: ConfirmationReplayGuard = InMemoryConfirmationReplayGuard(),
) {
    fun execute(request: TerminalActionRequest): TerminalResult {
        val startedAt = epochClock.nowMs()
        fun reject(reason: TerminalRejection): TerminalResult.Rejected = TerminalResult.Rejected(
            reason = reason,
            audit = audit(request, TerminalAuditOutcome.DENIED, reason.name, 0, startedAt),
        )

        if (policy.mode == TerminalMode.NO_TERMINAL_ACCESS) return reject(TerminalRejection.TERMINAL_DISABLED)
        if (!request.capabilityApproved) return reject(TerminalRejection.CAPABILITY_NOT_APPROVED)
        if (!REQUEST_ID.matches(request.requestId)) return reject(TerminalRejection.INVALID_REQUEST_ID)
        if (request.expiresAtEpochMs < startedAt || request.issuedAtEpochMs > startedAt) return reject(TerminalRejection.EXPIRED_REQUEST)

        val action = TerminalActionRegistry.find(request.actionId) ?: return reject(TerminalRejection.UNKNOWN_ACTION)
        if (request.schemaVersion != action.schemaVersion) return reject(TerminalRejection.UNSUPPORTED_SCHEMA)
        if (action.executable != TerminalAdapterKind.APP_SANDBOX || action.argv !in APPROVED_ARGV) {
            return reject(TerminalRejection.POLICY_VIOLATION)
        }
        if (!policy.allows(action.scope)) return reject(TerminalRejection.POLICY_VIOLATION)
        if (action.requiresConfirmation) {
            val confirmation = request.confirmation
            if (confirmation == null) return reject(TerminalRejection.CONFIRMATION_REQUIRED)
            if (!confirmation.approvedByUser || confirmation.actionId != action.id || confirmation.requestId != request.requestId || confirmation.nonce.isBlank() ||
                confirmation.approvedAtEpochMs !in request.issuedAtEpochMs..request.expiresAtEpochMs
            ) {
                return reject(TerminalRejection.INVALID_CONFIRMATION)
            }
            if (!confirmationReplayGuard.consume(request.requestId, confirmation.nonce)) {
                return reject(TerminalRejection.CONFIRMATION_REPLAYED)
            }
        }

        val startMono = monotonicClock.nowMs()
        val output = action.handler()
        if (monotonicClock.nowMs() - startMono > policy.bounds.timeoutMs) {
            return TerminalResult.Rejected(
                TerminalRejection.TIME_LIMIT_EXCEEDED,
                audit(request, TerminalAuditOutcome.TIMED_OUT, TerminalRejection.TIME_LIMIT_EXCEEDED.name, 0, startedAt),
            )
        }
        val bounded = BoundedOutput.limitUtf8(output, policy.bounds.outputByteLimit)
        val outcome = if (bounded.truncated) TerminalAuditOutcome.OUTPUT_TRUNCATED else TerminalAuditOutcome.ALLOWED
        return TerminalResult.Completed(
            bounded.value,
            audit(request, outcome, null, bounded.byteCount, startedAt),
        )
    }

    private fun audit(
        request: TerminalActionRequest,
        outcome: TerminalAuditOutcome,
        reason: String?,
        outputBytes: Int,
        startedAt: Long,
    ) = TerminalAuditRecord(
        requestId = request.requestId,
        actionId = request.actionId,
        schemaVersion = request.schemaVersion,
        mode = policy.mode,
        adapter = TerminalAdapterKind.APP_SANDBOX,
        outcome = outcome,
        reason = reason,
        confirmationNonce = request.confirmation?.nonce,
        outputBytes = outputBytes,
        startedAtEpochMs = startedAt,
        completedAtEpochMs = epochClock.nowMs(),
    )

    private companion object {
        val REQUEST_ID = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
        val APPROVED_ARGV = TerminalActionRegistry.all.map { it.argv }.toSet()
    }
}

private fun TerminalPolicy.allows(scope: TerminalActionScope): Boolean = when (mode) {
    TerminalMode.FULL_ACCESS -> true // Still only compiled AppSandboxAdapter actions, never root or a shell.
    TerminalMode.RESTRICTED_ACCESS -> scope == TerminalActionScope.APP_SANDBOX
    TerminalMode.XULTRON_DIRECTORY_ONLY -> scope == TerminalActionScope.XULTRON_DIRECTORY
    TerminalMode.NO_TERMINAL_ACCESS -> false
}

fun interface ConfirmationReplayGuard {
    /** Atomically marks the approval as consumed; reused approvals are always denied. */
    fun consume(requestId: String, nonce: String): Boolean
}

class InMemoryConfirmationReplayGuard : ConfirmationReplayGuard {
    private val consumed = mutableSetOf<String>()

    override fun consume(requestId: String, nonce: String): Boolean = synchronized(consumed) {
        consumed.add("$requestId:$nonce")
    }
}

data class BoundedText(val value: String, val byteCount: Int, val truncated: Boolean)

object BoundedOutput {
    fun limitUtf8(value: String, limit: Int): BoundedText {
        val bytes = value.toByteArray(StandardCharsets.UTF_8)
        if (bytes.size <= limit) return BoundedText(value, bytes.size, false)
        var end = limit
        while (end > 0 && (bytes[end].toInt() and 0xC0) == 0x80) end--
        return BoundedText(String(bytes, 0, end, StandardCharsets.UTF_8), end, true)
    }
}
