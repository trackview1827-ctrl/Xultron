package ai.xultron.app.core.capabilities

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CapabilityEngineTest {
    private val engine = CapabilityEngine()

    @Test
    fun `unknown permission fails closed`() {
        val decision = engine.evaluate(
            CapabilityRequest(
                capability = Capability.CAMERA,
                userEnabled = true,
                permission = PermissionDisposition.UNKNOWN,
                featureImplemented = true,
            ),
        )
        assertTrue(decision is CapabilityDecision.Denied)
    }

    @Test
    fun `unimplemented and disabled capabilities never become allowed`() {
        val unimplemented = engine.evaluate(
            CapabilityRequest(Capability.TERMINAL, true, PermissionDisposition.GRANTED, false),
        )
        val disabled = engine.evaluate(
            CapabilityRequest(Capability.MICROPHONE, false, PermissionDisposition.GRANTED, true),
        )
        assertTrue(unimplemented is CapabilityDecision.Denied)
        assertTrue(disabled is CapabilityDecision.Denied)
    }

    @Test
    fun `granted sensitive capability requires explicit confirmation`() {
        val pending = engine.evaluate(
            CapabilityRequest(
                capability = Capability.SCREEN_CAPTURE,
                userEnabled = true,
                permission = PermissionDisposition.GRANTED,
                featureImplemented = true,
                requiresConfirmation = true,
            ),
        )
        assertEquals(CapabilityDecision.Confirm(Capability.SCREEN_CAPTURE), pending)
    }

    @Test
    fun `phase three exposes permission state but enables no privileged feature`() {
        Capability.entries.forEach { capability ->
            assertTrue(!PhaseCapabilityPolicy.isImplemented(capability))
            assertTrue(!PhaseCapabilityPolicy.isUserEnabled(capability))
        }
    }
}
