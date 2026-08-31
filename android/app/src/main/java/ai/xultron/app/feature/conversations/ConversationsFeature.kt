package ai.xultron.app.feature.conversations

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.clickable
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.xultron.app.core.model.Loadable
import ai.xultron.app.core.network.ConversationDto
import ai.xultron.app.data.XultronRepository
import ai.xultron.app.feature.common.LoadablePane
import ai.xultron.app.feature.common.toLoadableError
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ConversationsViewModel(
    private val repository: XultronRepository,
    private val backendUrl: String,
) : ViewModel() {
    private val mutableState = MutableStateFlow<Loadable<List<ConversationDto>>>(Loadable.Idle)
    val state: StateFlow<Loadable<List<ConversationDto>>> = mutableState.asStateFlow()

    init { refresh() }

    fun refresh() = viewModelScope.launch {
        mutableState.value = Loadable.Loading
        runCatching { repository.conversations(backendUrl) }
            .onSuccess { mutableState.value = if (it.isEmpty()) Loadable.Empty("İlk konuşmanızı Chat ekranından başlatın.") else Loadable.Content(it) }
            .onFailure { mutableState.value = it.toLoadableError() }
    }
}

@Composable
fun ConversationsScreen(viewModel: ConversationsViewModel, onOpenConversation: (String) -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LoadablePane(state, viewModel::refresh) { conversations ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(conversations, key = { it.id }) { conversation ->
                Card(modifier = Modifier.fillMaxWidth().clickable { onOpenConversation(conversation.id) }) {
                    Column(Modifier.padding(16.dp)) {
                        Text(conversation.title, style = MaterialTheme.typography.titleMedium)
                        Text(conversation.updatedAt, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Aç", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    }
}
