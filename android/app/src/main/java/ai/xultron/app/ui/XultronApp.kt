package ai.xultron.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.xultron.app.AppContainer
import ai.xultron.app.core.network.BackendEndpoint

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
        if (state.backendUrl.isBlank() || state.backendUrl == BackendEndpoint.LOCAL) {
            WebFrontendBootstrapScreen(
                backendUrl = state.backendUrl,
                connection = state.connection,
                busy = state.authBusy,
                error = state.error,
                onSaveBackendUrl = rootViewModel::saveBackendUrl,
            )
        } else {
            // The web app owns login, navigation, chat, memory, providers and settings.
            WebFrontendScreen(backendUrl = state.backendUrl)
        }
    }
}
