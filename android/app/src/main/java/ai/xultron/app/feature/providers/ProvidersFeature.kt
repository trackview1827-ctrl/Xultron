package ai.xultron.app.feature.providers

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.xultron.app.core.model.Loadable
import ai.xultron.app.core.network.ProviderDto
import ai.xultron.app.data.XultronRepository
import ai.xultron.app.feature.common.LoadablePane
import ai.xultron.app.feature.common.toLoadableError
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ProvidersUiState(
    val providers: Loadable<List<ProviderDto>> = Loadable.Idle,
    val testingId: String? = null,
    val testMessage: String? = null,
)

class ProvidersViewModel(private val repository: XultronRepository, private val backendUrl: String) : ViewModel() {
    private val mutableState = MutableStateFlow(ProvidersUiState())
    val state: StateFlow<ProvidersUiState> = mutableState.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(providers = Loadable.Loading)
        runCatching { repository.providers(backendUrl) }
            .onSuccess { mutableState.value = mutableState.value.copy(providers = if (it.isEmpty()) Loadable.Empty("Backend web arayüzünden bir provider ekleyin.") else Loadable.Content(it)) }
            .onFailure { mutableState.value = mutableState.value.copy(providers = it.toLoadableError()) }
    }
    fun test(providerId: String) = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(testingId = providerId, testMessage = null)
        runCatching { repository.testProvider(backendUrl, providerId) }
            .onSuccess { mutableState.value = mutableState.value.copy(testingId = null, testMessage = "Provider bağlantısı başarılı.") }
            .onFailure { mutableState.value = mutableState.value.copy(testingId = null, testMessage = it.message ?: "Provider testi başarısız.") }
    }
}

@Composable
fun ProvidersScreen(viewModel: ProvidersViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        state.testMessage?.let { Text(it, modifier = Modifier.padding(16.dp), color = MaterialTheme.colorScheme.primary) }
        LoadablePane(state.providers, viewModel::refresh) { providers ->
            LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(providers, key = { it.id }) { provider ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                Column {
                                    Text(provider.name, style = MaterialTheme.typography.titleMedium)
                                    Text("${provider.kind} · ${provider.adapter}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                if (provider.isDefault) AssistChip(onClick = {}, label = { Text("Varsayılan") })
                            }
                            Text(provider.model ?: "Model seçilmemiş")
                            Text(if (provider.credential.configured) "Kimlik bilgisi: ${provider.credential.masked ?: "yapılandırılmış"}" else "Kimlik bilgisi eksik")
                            Button(onClick = { viewModel.test(provider.id) }, enabled = state.testingId == null) { Text(if (state.testingId == provider.id) "Test ediliyor" else "Bağlantıyı test et") }
                        }
                    }
                }
            }
        }
    }
}
