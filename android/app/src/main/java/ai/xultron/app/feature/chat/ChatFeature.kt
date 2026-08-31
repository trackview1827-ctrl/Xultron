package ai.xultron.app.feature.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.xultron.app.core.model.Loadable
import ai.xultron.app.core.network.MessageDto
import ai.xultron.app.data.XultronRepository
import ai.xultron.app.feature.common.LoadablePane
import ai.xultron.app.feature.common.toLoadableError
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatUiState(
    val conversationId: String? = null,
    val messages: Loadable<List<MessageDto>> = Loadable.Idle,
    val sending: Boolean = false,
    val sendError: String? = null,
)

class ChatViewModel(private val repository: XultronRepository, private val backendUrl: String) : ViewModel() {
    private val mutableState = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = mutableState.asStateFlow()
    init { refresh() }

    fun refresh() = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(messages = Loadable.Loading)
        runCatching {
            val conversation = repository.conversations(backendUrl).firstOrNull()
            conversation?.let { it.id to repository.messages(backendUrl, it.id) }
        }.onSuccess { loaded ->
            mutableState.value = if (loaded == null) {
                mutableState.value.copy(conversationId = null, messages = Loadable.Empty("Mesaj yazarak yeni bir konuşma başlatın."))
            } else {
                mutableState.value.copy(conversationId = loaded.first, messages = if (loaded.second.isEmpty()) Loadable.Empty("Bu konuşmada mesaj yok.") else Loadable.Content(loaded.second))
            }
        }.onFailure { mutableState.value = mutableState.value.copy(messages = it.toLoadableError()) }
    }

    fun openConversation(conversationId: String) = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(conversationId = conversationId, messages = Loadable.Loading, sendError = null)
        runCatching { repository.messages(backendUrl, conversationId) }
            .onSuccess { messages ->
                mutableState.value = mutableState.value.copy(
                    messages = if (messages.isEmpty()) Loadable.Empty("Bu konuşmada mesaj yok.") else Loadable.Content(messages),
                )
            }
            .onFailure { mutableState.value = mutableState.value.copy(messages = it.toLoadableError()) }
    }

    fun newConversation() {
        mutableState.value = ChatUiState(messages = Loadable.Empty("Mesaj yazarak yeni bir konuşma başlatın."))
    }

    fun send(message: String) = viewModelScope.launch {
        if (message.isBlank() || mutableState.value.sending) return@launch
        mutableState.value = mutableState.value.copy(sending = true, sendError = null)
        runCatching { repository.sendMessage(backendUrl, message, mutableState.value.conversationId) }
            .onSuccess { response ->
                val existing = (mutableState.value.messages as? Loadable.Content)?.value.orEmpty()
                mutableState.value = mutableState.value.copy(
                    conversationId = response.conversation.id,
                    messages = Loadable.Content(existing + response.messages),
                    sending = false,
                )
            }
            .onFailure { mutableState.value = mutableState.value.copy(sending = false, sendError = it.message ?: "Mesaj gönderilemedi.") }
    }
}

@Composable
fun ChatScreen(viewModel: ChatViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var input by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp), horizontalArrangement = Arrangement.End) {
            Button(onClick = viewModel::newConversation, enabled = !state.sending) { Text("Yeni konuşma") }
        }
        Column(Modifier.weight(1f)) {
            LoadablePane(state.messages, viewModel::refresh) { messages ->
                LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(messages, key = { it.id }) { message ->
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(12.dp)) {
                                Text(if (message.role == "assistant") "Xultron" else "Sen", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                                Text(message.content)
                            }
                        }
                    }
                }
            }
        }
        state.sendError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp)) }
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(value = input, onValueChange = { input = it }, label = { Text("Mesaj") }, modifier = Modifier.weight(1f), maxLines = 4)
            Button(onClick = { viewModel.send(input); input = "" }, enabled = input.isNotBlank() && !state.sending) { Text(if (state.sending) "..." else "Gönder") }
        }
    }
}
