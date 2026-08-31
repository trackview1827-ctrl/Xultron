package ai.xultron.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import ai.xultron.app.AppContainer
import ai.xultron.app.feature.chat.ChatViewModel
import ai.xultron.app.feature.conversations.ConversationsViewModel
import ai.xultron.app.feature.memory.MemoryViewModel
import ai.xultron.app.feature.providers.ProvidersViewModel
import ai.xultron.app.feature.settings.SettingsViewModel

class FeatureViewModelFactory(
    private val container: AppContainer,
    private val backendUrl: String,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = when {
        modelClass.isAssignableFrom(ChatViewModel::class.java) -> ChatViewModel(container.repository, backendUrl)
        modelClass.isAssignableFrom(ConversationsViewModel::class.java) -> ConversationsViewModel(container.repository, backendUrl)
        modelClass.isAssignableFrom(MemoryViewModel::class.java) -> MemoryViewModel(container.repository, backendUrl)
        modelClass.isAssignableFrom(ProvidersViewModel::class.java) -> ProvidersViewModel(container.repository, backendUrl)
        modelClass.isAssignableFrom(SettingsViewModel::class.java) -> SettingsViewModel(container.repository, backendUrl)
        else -> error("Unknown ViewModel: ${modelClass.name}")
    } as T
}
