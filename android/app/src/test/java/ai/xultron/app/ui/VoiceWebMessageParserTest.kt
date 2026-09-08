package ai.xultron.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class VoiceWebMessageParserTest {
    @Test
    fun `accepts only versioned fixed voice actions`() {
        assertEquals(
            VoiceWebMessage.Status("voice-12345678"),
            VoiceWebMessageParser.parse("""{"v":1,"id":"voice-12345678","action":"voice.status"}"""),
        )
        assertEquals(
            VoiceWebMessage.Start("voice-12345678"),
            VoiceWebMessageParser.parse("""{"v":1,"id":"voice-12345678","action":"voice.start"}"""),
        )
    }

    @Test
    fun `rejects unknown fields actions and malformed identifiers`() {
        assertNull(VoiceWebMessageParser.parse("""{"v":1,"id":"voice-12345678","action":"terminal.exec"}"""))
        assertNull(VoiceWebMessageParser.parse("""{"v":1,"id":"short","action":"voice.start"}"""))
        assertNull(VoiceWebMessageParser.parse("""{"v":1,"id":"voice-12345678","action":"voice.start","input":"ignored"}"""))
        assertNull(VoiceWebMessageParser.parse("not-json"))
    }

    @Test
    fun `source must exactly match the configured trusted origin`() {
        assertTrue(isTrustedVoiceSource("https://xultron.example", "https://xultron.example"))
        assertTrue(isTrustedVoiceSource("https://xultron.example/", "https://xultron.example"))
        assertTrue(!isTrustedVoiceSource("https://evil.example", "https://xultron.example"))
        assertTrue(!isTrustedVoiceSource("https://xultron.example:444", "https://xultron.example"))
    }
}
