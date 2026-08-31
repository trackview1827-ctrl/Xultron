package ai.xultron.app.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.xultron.app.AppContainer
import ai.xultron.app.core.network.UserDto
import ai.xultron.app.feature.chat.ChatScreen
import ai.xultron.app.feature.chat.ChatViewModel
import ai.xultron.app.feature.conversations.ConversationsScreen
import ai.xultron.app.feature.conversations.ConversationsViewModel
import ai.xultron.app.feature.memory.MemoryScreen
import ai.xultron.app.feature.memory.MemoryViewModel
import ai.xultron.app.feature.providers.ProvidersScreen
import ai.xultron.app.feature.providers.ProvidersViewModel
import ai.xultron.app.feature.settings.SettingsScreen
import ai.xultron.app.feature.settings.SettingsViewModel

private enum class Destination(val label: String) {
    Chat("Chat"), Conversations("Konuşmalar"), Memory("Memory"), Providers("Provider"), Settings("Ayarlar")
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun AuthenticatedShell(
    container: AppContainer,
    backendUrl: String,
    connection: ConnectionState,
    user: UserDto,
    lowDataMode: Boolean,
    onSetBackendUrl: (String) -> Unit,
    onLowDataModeChange: (Boolean) -> Unit,
    onLogout: () -> Unit,
    permissionsContent: @Composable () -> Unit = {},
) {
    var destination by remember { mutableStateOf(Destination.Chat) }
    val factory = remember(backendUrl) { FeatureViewModelFactory(container, backendUrl) }
    val chatViewModel = viewModel<ChatViewModel>(key = "chat-$backendUrl", factory = factory)
    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            TopAppBar(
                title = { Text(destination.label) },
                actions = { Text(if (connection is ConnectionState.Connected) "Bağlı" else "Çevrimdışı") },
            )
        },
        bottomBar = {
            NavigationBar {
                Destination.entries.forEach { item ->
                    NavigationBarItem(
                        selected = destination == item,
                        onClick = { destination = item },
                        icon = { Text(item.label.take(1)) },
                        label = { Text(item.label) },
                    )
                }
            }
        },
    ) { padding ->
        androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().then(Modifier.padding(padding))) {
            when (destination) {
                Destination.Chat -> ChatScreen(chatViewModel)
                Destination.Conversations -> ConversationsScreen(
                    viewModel = viewModel<ConversationsViewModel>(key = "conversations-$backendUrl", factory = factory),
                    onOpenConversation = { conversationId ->
                        chatViewModel.openConversation(conversationId)
                        destination = Destination.Chat
                    },
                )
                Destination.Memory -> MemoryScreen(viewModel<MemoryViewModel>(key = "memory-$backendUrl", factory = factory))
                Destination.Providers -> ProvidersScreen(viewModel<ProvidersViewModel>(key = "providers-$backendUrl", factory = factory))
                Destination.Settings -> SettingsScreen(
                    viewModel = viewModel<SettingsViewModel>(key = "settings-$backendUrl", factory = factory),
                    user = user,
                    backendUrl = backendUrl,
                    connection = connection,
                    lowDataMode = lowDataMode,
                    onSetBackendUrl = onSetBackendUrl,
                    onLowDataModeChange = onLowDataModeChange,
                    onLogout = onLogout,
                    permissionsContent = permissionsContent,
                )
            }
        }
    }
}
