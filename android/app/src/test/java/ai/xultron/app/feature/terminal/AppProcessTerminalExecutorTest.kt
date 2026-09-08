package ai.xultron.app.feature.terminal

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppProcessTerminalExecutorTest {
    private val now = 10_000L

    @Test
    fun `no terminal mode fails closed before an action can run`() {
        val result = executor(TerminalMode.NO_TERMINAL_ACCESS).execute(request())

        assertRejected(result, TerminalRejection.TERMINAL_DISABLED)
        assertEquals(TerminalAuditOutcome.DENIED, result.audit.outcome)
    }

    @Test
    fun `full restricted and xultron-only modes enforce separate action scopes`() {
        assertTrue(executor(TerminalMode.FULL_ACCESS).execute(request()) is TerminalResult.Completed)
        assertTrue(executor(TerminalMode.RESTRICTED_ACCESS).execute(request()) is TerminalResult.Completed)
        assertRejected(executor(TerminalMode.XULTRON_DIRECTORY_ONLY).execute(request()), TerminalRejection.POLICY_VIOLATION)

        val directoryAction = request(action = "xultron.app.workspace-summary.v1").copy(
            confirmation = confirmation(action = "xultron.app.workspace-summary.v1"),
        )
        assertTrue(executor(TerminalMode.FULL_ACCESS).execute(directoryAction) is TerminalResult.Completed)
        assertRejected(executor(TerminalMode.RESTRICTED_ACCESS).execute(directoryAction), TerminalRejection.POLICY_VIOLATION)
        val directoryOnlyResult = executor(TerminalMode.XULTRON_DIRECTORY_ONLY).execute(directoryAction)
        assertTrue(directoryOnlyResult is TerminalResult.Completed)
        assertEquals(TerminalAdapterKind.APP_SANDBOX, directoryOnlyResult.audit.adapter)
    }

    @Test
    fun `unknown action schema expired request and absent capability fail closed`() {
        assertRejected(executor().execute(request(action = "backend.shell.v1")), TerminalRejection.UNKNOWN_ACTION)
        assertRejected(executor().execute(request(schemaVersion = 2)), TerminalRejection.UNSUPPORTED_SCHEMA)
        assertRejected(executor().execute(request(expiresAt = now - 1)), TerminalRejection.EXPIRED_REQUEST)
        assertRejected(
            executor().execute(request().copy(issuedAtEpochMs = now + 1)),
            TerminalRejection.EXPIRED_REQUEST,
        )
        assertRejected(executor().execute(request(capabilityApproved = false)), TerminalRejection.CAPABILITY_NOT_APPROVED)
    }

    @Test
    fun `confirmed action requires matching user approval within request lifetime`() {
        val protectedRequest = request(action = "xultron.app.workspace-summary.v1")
        val terminal = executor(TerminalMode.XULTRON_DIRECTORY_ONLY)
        assertRejected(terminal.execute(protectedRequest), TerminalRejection.CONFIRMATION_REQUIRED)
        assertRejected(
            terminal.execute(protectedRequest.copy(confirmation = confirmation(action = "xultron.app.sandbox-status.v1"))),
            TerminalRejection.INVALID_CONFIRMATION,
        )
        assertRejected(
            terminal.execute(protectedRequest.copy(confirmation = confirmation(action = "xultron.app.workspace-summary.v1", requestId = "other-request"))),
            TerminalRejection.INVALID_CONFIRMATION,
        )
        assertRejected(
            terminal.execute(protectedRequest.copy(confirmation = confirmation(action = "xultron.app.workspace-summary.v1").copy(approvedAtEpochMs = now + 2_000))),
            TerminalRejection.INVALID_CONFIRMATION,
        )
        val confirmedRequest = protectedRequest.copy(confirmation = confirmation(action = "xultron.app.workspace-summary.v1"))
        val result = terminal.execute(confirmedRequest)
        assertTrue(result is TerminalResult.Completed)
        assertEquals("approved-nonce", result.audit.confirmationNonce)
        assertRejected(terminal.execute(confirmedRequest), TerminalRejection.CONFIRMATION_REPLAYED)
    }

    @Test
    fun `output is bounded in utf8 bytes and audited as truncated`() {
        val result = executor(bounds = TerminalBounds(timeoutMs = 1_000, outputByteLimit = 5)).execute(request())

        assertTrue(result is TerminalResult.Completed)
        result as TerminalResult.Completed
        assertTrue(result.output.toByteArray().size <= 5)
        assertTrue(result.audit.outputBytes <= 5)
        assertEquals(TerminalAuditOutcome.OUTPUT_TRUNCATED, result.audit.outcome)
    }

    @Test
    fun `elapsed action is rejected after hard time limit`() {
        val ticks = longArrayOf(0, 11)
        var index = 0
        val result = AppProcessTerminalExecutor(
            policy = TerminalPolicy(TerminalMode.RESTRICTED_ACCESS, TerminalBounds(timeoutMs = 10, outputByteLimit = 128)),
            epochClock = EpochClock { now },
            monotonicClock = MonotonicClock { ticks[index++] },
        ).execute(request())

        assertRejected(result, TerminalRejection.TIME_LIMIT_EXCEEDED)
        assertEquals(TerminalAuditOutcome.TIMED_OUT, result.audit.outcome)
    }

    @Test
    fun `advanced adapters remain unavailable and never grant root`() {
        assertTrue(TermuxAdapter.availability() is AdapterAvailability.Unavailable)
        assertTrue(ShizukuAdapter.availability() is AdapterAvailability.Unavailable)
        val root = RootAdapter.availability() as AdapterAvailability.Unavailable
        assertTrue(root.reason.contains("not offered"))
    }

    private fun executor(
        mode: TerminalMode = TerminalMode.RESTRICTED_ACCESS,
        bounds: TerminalBounds = TerminalBounds(),
    ) = AppProcessTerminalExecutor(TerminalPolicy(mode, bounds), EpochClock { now })

    private fun request(
        action: String = "xultron.app.sandbox-status.v1",
        schemaVersion: Int = 1,
        expiresAt: Long = now + 1_000,
        capabilityApproved: Boolean = true,
    ) = TerminalActionRequest(
        actionId = TerminalActionId(action),
        schemaVersion = schemaVersion,
        requestId = "request-0001",
        issuedAtEpochMs = now - 1,
        expiresAtEpochMs = expiresAt,
        capabilityApproved = capabilityApproved,
    )

    private fun confirmation(action: String, requestId: String = "request-0001") = ConfirmationMetadata(
        approvedByUser = true,
        actionId = TerminalActionId(action),
        requestId = requestId,
        nonce = "approved-nonce",
        approvedAtEpochMs = now,
    )

    private fun assertRejected(result: TerminalResult, reason: TerminalRejection) {
        assertTrue(result is TerminalResult.Rejected)
        result as TerminalResult.Rejected
        assertEquals(reason, result.reason)
    }
}
