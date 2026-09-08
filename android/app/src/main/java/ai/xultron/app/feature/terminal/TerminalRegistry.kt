package ai.xultron.app.feature.terminal

/**
 * A deliberately small static registry. The arguments and handler are compiled into the APK.
 * No request, UI value, backend response, or environment variable can supply an executable or argv.
 */
data class TerminalActionDefinition(
    val id: TerminalActionId,
    val schemaVersion: Int,
    val executable: TerminalAdapterKind,
    val argv: List<String>,
    val scope: TerminalActionScope,
    val requiresConfirmation: Boolean,
    val handler: () -> String,
)

enum class TerminalActionScope {
    APP_SANDBOX,
    XULTRON_DIRECTORY,
}

object TerminalActionRegistry {
    val all: List<TerminalActionDefinition> = listOf(
        TerminalActionDefinition(
            id = TerminalActionId("xultron.app.sandbox-status.v1"),
            schemaVersion = 1,
            executable = TerminalAdapterKind.APP_SANDBOX,
            argv = listOf("xultron-internal", "sandbox-status"),
            scope = TerminalActionScope.APP_SANDBOX,
            requiresConfirmation = false,
            handler = { "sandbox=ready\nnetwork=blocked\n" },
        ),
        TerminalActionDefinition(
            id = TerminalActionId("xultron.app.workspace-summary.v1"),
            schemaVersion = 1,
            executable = TerminalAdapterKind.APP_SANDBOX,
            argv = listOf("xultron-internal", "workspace-summary"),
            scope = TerminalActionScope.XULTRON_DIRECTORY,
            requiresConfirmation = true,
            handler = { "workspace=app-sandbox\naccess=metadata-only\n" },
        ),
    )

    fun find(id: TerminalActionId): TerminalActionDefinition? = all.firstOrNull { it.id == id }
}

sealed interface AdapterAvailability {
    data object Available : AdapterAvailability
    data class Unavailable(val reason: String) : AdapterAvailability
}

interface TerminalAdapter {
    val kind: TerminalAdapterKind
    fun availability(): AdapterAvailability
}

object AppSandboxAdapter : TerminalAdapter {
    override val kind = TerminalAdapterKind.APP_SANDBOX
    override fun availability() = AdapterAvailability.Available
}

/** Advanced integrations intentionally expose availability only. They execute nothing in Phase 4. */
object TermuxAdapter : TerminalAdapter {
    override val kind = TerminalAdapterKind.TERMUX
    override fun availability() = AdapterAvailability.Unavailable("Termux integration is opt-in and unavailable.")
}

object ShizukuAdapter : TerminalAdapter {
    override val kind = TerminalAdapterKind.SHIZUKU
    override fun availability() = AdapterAvailability.Unavailable("Shizuku integration is opt-in and unavailable.")
}

object RootAdapter : TerminalAdapter {
    override val kind = TerminalAdapterKind.ROOT
    override fun availability() = AdapterAvailability.Unavailable("Root access is not offered by a normal Android app.")
}
