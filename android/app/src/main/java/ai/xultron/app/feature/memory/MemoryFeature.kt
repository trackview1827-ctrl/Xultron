package ai.xultron.app.feature.memory

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.xultron.app.core.model.Loadable
import ai.xultron.app.core.network.MemoryDto
import ai.xultron.app.data.XultronRepository
import ai.xultron.app.feature.common.LoadablePane
import ai.xultron.app.feature.common.toLoadableError
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MemoryViewModel(private val repository: XultronRepository, private val backendUrl: String) : ViewModel() {
    private val mutableState = MutableStateFlow<Loadable<List<MemoryDto>>>(Loadable.Idle)
    val state: StateFlow<Loadable<List<MemoryDto>>> = mutableState.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        mutableState.value = Loadable.Loading
        runCatching { repository.memories(backendUrl) }
            .onSuccess { mutableState.value = if (it.isEmpty()) Loadable.Empty("Hatırlanmış bilgi bulunmuyor.") else Loadable.Content(it) }
            .onFailure { mutableState.value = it.toLoadableError() }
    }
}

@Composable
fun MemoryScreen(viewModel: MemoryViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LoadablePane(state, viewModel::refresh) { memories ->
        LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(memories, key = { it.id }) { memory ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(memory.title, style = MaterialTheme.typography.titleMedium)
                        Text(memory.category.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                        Text(memory.content, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}
