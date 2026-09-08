package ai.xultron.app.service

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceServiceStateMachineTest {
    @Test
    fun `permission failure fails closed before service starts`() {
        val result = VoiceServiceStateMachine.reduce(
            VoiceServiceStatus(),
            VoiceServiceEvent.StartRequested(VoiceBlockReason.MICROPHONE_PERMISSION_MISSING),
        )
        assertEquals(VoiceServiceState.BLOCKED, result.state)
        assertEquals(VoiceBlockReason.MICROPHONE_PERMISSION_MISSING, result.blockReason)
    }

    @Test
    fun `missing detector model blocks before the microphone can open`() {
        val result = VoiceServiceStateMachine.reduce(
            VoiceServiceStatus(),
            VoiceServiceEvent.StartRequested(VoiceBlockReason.MODEL_UNAVAILABLE),
        )
        assertEquals(VoiceServiceState.BLOCKED, result.state)
        assertEquals(VoiceBlockReason.MODEL_UNAVAILABLE, result.blockReason)
        assertTrue(result.detail.contains("microphone will not open"))
    }

    @Test
    fun `user start and stop follow deterministic local-only lifecycle`() {
        val starting = VoiceServiceStateMachine.reduce(VoiceServiceStatus(), VoiceServiceEvent.StartRequested())
        val running = VoiceServiceStateMachine.reduce(starting, VoiceServiceEvent.ForegroundServiceStarted)
        val stopping = VoiceServiceStateMachine.reduce(running, VoiceServiceEvent.StopRequested)
        val stopped = VoiceServiceStateMachine.reduce(stopping, VoiceServiceEvent.ServiceStopped)

        assertEquals(VoiceServiceState.STARTING, starting.state)
        assertEquals(VoiceServiceState.MONITORING_EXPERIMENTAL, running.state)
        assertEquals(VoiceServiceState.STOPPING, stopping.state)
        assertEquals(VoiceServiceState.STOPPED, stopped.state)
        assertFalse(running.diagnostic.cloudSttEnabled)
        assertFalse(running.diagnostic.rawAudioUploadEnabled)
        assertFalse(running.diagnostic.pollingEnabled)
        assertFalse(running.diagnostic.persistentWebSocketEnabled)
        assertFalse(running.diagnostic.rawAudioPersisted)
    }

    @Test
    fun `a failure records diagnostic and never claims monitoring is active`() {
        val failed = VoiceServiceStateMachine.reduce(VoiceServiceStatus(), VoiceServiceEvent.Failure("AudioRecord unavailable"))
        assertEquals(VoiceServiceState.ERROR, failed.state)
        assertEquals("AudioRecord unavailable", failed.diagnostic.lastError)
        assertTrue(failed.detail.contains("AudioRecord"))
    }
}
