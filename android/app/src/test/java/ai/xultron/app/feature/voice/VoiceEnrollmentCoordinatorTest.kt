package ai.xultron.app.feature.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceEnrollmentCoordinatorTest {
    private val accepted = VoiceSampleMetrics(durationMs = 2_000, speechFrameRatio = 0.6, rmsDbfs = -22.0, clippingRatio = 0.0)

    @Test
    fun `profile becomes available only after five explicit accepted attempts`() {
        val coordinator = VoiceEnrollmentCoordinator()
        repeat(4) { coordinator.submit(accepted) }
        assertTrue(coordinator.status() is EnrollmentStatus.Collecting)

        val status = coordinator.submit(accepted)
        assertTrue(status is EnrollmentStatus.Complete)
        assertEquals(5, (status as EnrollmentStatus.Complete).profile.enrolledAttempts)
    }

    @Test
    fun `each quality gate rejects unsuitable sample while consuming explicit attempt`() {
        val coordinator = VoiceEnrollmentCoordinator()
        coordinator.submit(accepted.copy(durationMs = 1_499))
        coordinator.submit(accepted.copy(speechFrameRatio = 0.34))
        coordinator.submit(accepted.copy(rmsDbfs = -42.1))
        coordinator.submit(accepted.copy(clippingRatio = 0.021))
        coordinator.submit(accepted)

        val collecting = coordinator.status() as EnrollmentStatus.Collecting
        assertEquals(listOf(EnrollmentRejection.TOO_SHORT, EnrollmentRejection.NO_SPEECH, EnrollmentRejection.TOO_QUIET, EnrollmentRejection.CLIPPED, null), collecting.attempts.map { it.rejection })
        assertFalse(collecting.attempts.all { it.accepted })
    }

    @Test
    fun `silence produces a no-speech quality rejection without retaining a waveform`() {
        val metrics = VoiceSampleQuality.metrics(ShortArray(16_000 * 2), 16_000)
        assertEquals(EnrollmentRejection.NO_SPEECH, metrics.rejection())
        assertEquals(2_000, metrics.durationMs)
    }
}
