package ai.xultron.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.xultron.app.AppContainer
import ai.xultron.app.feature.auth.AuthScreen
import ai.xultron.app.feature.settings.PermissionSection

@Composable
fun XultronApp(container: AppContainer) {
    val rootViewModel: RootViewModel = viewModel(factory = RootViewModelFactory(container))
    val state by rootViewModel.state.collectAsStateWithLifecycle()
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = androidx.compose.ui.graphics.Color(0xFF2DE2E6),
            secondary = androidx.compose.ui.graphics.Color(0xFF8A7CFF),
            background = androidx.compose.ui.graphics.Color(0xFF071015),
            surface = androidx.compose.ui.graphics.Color(0xFF101B22),
        ),
    ) {
        if (state.user == null) {
            AuthScreen(
                backendUrl = state.backendUrl,
                connectionState = state.connection,
                busy = state.authBusy,
                error = state.error,
                onSaveBackendUrl = rootViewModel::saveBackendUrl,
                onLogin = rootViewModel::login,
                onEnroll = rootViewModel::enroll,
                onGuest = rootViewModel::continueAsGuest,
                onRetry = rootViewModel::retryConnection,
            )
        } else {
            AuthenticatedShell(
                container = container,
                backendUrl = state.backendUrl,
                connection = state.connection,
                user = requireNotNull(state.user),
                lowDataMode = state.lowDataMode,
                onSetBackendUrl = rootViewModel::saveBackendUrl,
                onLowDataModeChange = rootViewModel::setLowDataMode,
                onLogout = rootViewModel::logout,
                permissionsContent = {
                    PermissionSection(container.permissionManager, container.capabilityEngine)
                },
            )
        }
    }
}
