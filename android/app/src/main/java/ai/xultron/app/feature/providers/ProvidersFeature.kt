package ai.xultron.app.feature.providers

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
    val busyId: String? = null,
    val message: String? = null,
    val discoveredModels: Map<String, List<String>> = emptyMap(),
)

class ProvidersViewModel(private val repository: XultronRepository, private val backendUrl: String) : ViewModel() {
    private val mutableState = MutableStateFlow(ProvidersUiState())
    val state: StateFlow<ProvidersUiState> = mutableState.asStateFlow()
    init { refresh() }

    fun refresh() = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(providers = Loadable.Loading)
        runCatching { repository.providers(backendUrl) }
            .onSuccess { providers ->
                mutableState.value = mutableState.value.copy(
                    providers = if (providers.isEmpty()) Loadable.Empty("İlk provider'ınızı ekleyin.") else Loadable.Content(providers),
                )
            }
            .onFailure { mutableState.value = mutableState.value.copy(providers = it.toLoadableError()) }
    }

    fun save(
        providerId: String?,
        name: String,
        kind: String,
        adapter: String,
        baseUrl: String,
        model: String,
        apiKey: String,
        onSaved: () -> Unit,
    ) = viewModelScope.launch {
        if (name.isBlank() || kind.isBlank() || adapter.isBlank()) {
            mutableState.value = mutableState.value.copy(message = "Ad, tür ve adapter zorunludur.")
            return@launch
        }
        mutableState.value = mutableState.value.copy(busyId = providerId ?: "new", message = null)
        runCatching {
            if (providerId == null) {
                repository.createProvider(backendUrl, name, kind, adapter, baseUrl, model, apiKey)
            } else {
                repository.updateProvider(backendUrl, providerId, name, kind, adapter, baseUrl, model, apiKey)
            }
        }.onSuccess {
            mutableState.value = mutableState.value.copy(busyId = null, message = "Provider kaydedildi.")
            onSaved()
            refresh()
        }.onFailure {
            mutableState.value = mutableState.value.copy(busyId = null, message = it.message ?: "Provider kaydedilemedi.")
        }
    }

    fun test(providerId: String) = action(providerId, "Provider bağlantısı başarılı.") {
        repository.testProvider(backendUrl, providerId)
    }

    fun delete(providerId: String) = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(busyId = providerId, message = null)
        runCatching { repository.deleteProvider(backendUrl, providerId) }
            .onSuccess {
                mutableState.value = mutableState.value.copy(busyId = null, message = "Provider silindi.")
                refresh()
            }
            .onFailure { mutableState.value = mutableState.value.copy(busyId = null, message = it.message ?: "Provider silinemedi.") }
    }

    fun discoverModels(providerId: String) = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(busyId = providerId, message = null)
        runCatching { repository.providerModels(backendUrl, providerId) }
            .onSuccess { models ->
                mutableState.value = mutableState.value.copy(
                    busyId = null,
                    discoveredModels = mutableState.value.discoveredModels + (providerId to models),
                    message = if (models.isEmpty()) "Model bulunamadı." else "${models.size} model bulundu.",
                )
            }
            .onFailure { mutableState.value = mutableState.value.copy(busyId = null, message = it.message ?: "Modeller alınamadı.") }
    }

    fun selectModel(provider: ProviderDto, model: String) = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(busyId = provider.id, message = null)
        runCatching {
            repository.updateProvider(
                backendUrl,
                provider.id,
                provider.name,
                provider.kind,
                provider.adapter,
                provider.baseUrl,
                model,
                null,
            )
        }.onSuccess {
            mutableState.value = mutableState.value.copy(busyId = null, message = "Model seçildi.")
            refresh()
        }.onFailure { mutableState.value = mutableState.value.copy(busyId = null, message = it.message ?: "Model seçilemedi.") }
    }

    private fun action(providerId: String, successMessage: String, block: suspend () -> Unit) = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(busyId = providerId, message = null)
        runCatching { block() }
            .onSuccess { mutableState.value = mutableState.value.copy(busyId = null, message = successMessage) }
            .onFailure { mutableState.value = mutableState.value.copy(busyId = null, message = it.message ?: "İşlem başarısız.") }
    }
}

@Composable
fun ProvidersScreen(viewModel: ProvidersViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf<ProviderDto?>(null) }
    var creating by remember { mutableStateOf(false) }
    var pendingDelete by remember { mutableStateOf<ProviderDto?>(null) }

    pendingDelete?.let { provider ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("Provider silinsin mi?") },
            text = { Text("${provider.name} kalıcı olarak silinecek.") },
            confirmButton = {
                TextButton(onClick = { viewModel.delete(provider.id); pendingDelete = null }) { Text("Sil") }
            },
            dismissButton = { TextButton(onClick = { pendingDelete = null }) { Text("Vazgeç") } },
        )
    }

    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            state.message?.let { Text(it, modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.primary) }
            Button(onClick = { editing = null; creating = true }) { Text("Provider ekle") }
        }
        if (creating || editing != null) {
            ProviderEditor(
                provider = editing,
                busy = state.busyId != null,
                onCancel = { creating = false; editing = null },
                onSave = { name, kind, adapter, baseUrl, model, apiKey ->
                    viewModel.save(editing?.id, name, kind, adapter, baseUrl, model, apiKey) {
                        creating = false
                        editing = null
                    }
                },
            )
        }
        LoadablePane(state.providers, viewModel::refresh) { providers ->
            LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
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
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = { viewModel.test(provider.id) }, enabled = state.busyId == null) { Text("Test") }
                                OutlinedButton(onClick = { viewModel.discoverModels(provider.id) }, enabled = state.busyId == null) { Text("Modeller") }
                                OutlinedButton(onClick = { editing = provider; creating = false }, enabled = state.busyId == null) { Text("Düzenle") }
                                TextButton(onClick = { pendingDelete = provider }, enabled = state.busyId == null) { Text("Sil") }
                            }
                            state.discoveredModels[provider.id]?.forEach { model ->
                                AssistChip(onClick = { viewModel.selectModel(provider, model) }, label = { Text(model) })
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ProviderEditor(
    provider: ProviderDto?,
    busy: Boolean,
    onCancel: () -> Unit,
    onSave: (String, String, String, String, String, String) -> Unit,
) {
    var name by remember(provider?.id) { mutableStateOf(provider?.name.orEmpty()) }
    var kind by remember(provider?.id) { mutableStateOf(provider?.kind ?: "ai") }
    var adapter by remember(provider?.id) { mutableStateOf(provider?.adapter ?: "openai") }
    var baseUrl by remember(provider?.id) { mutableStateOf(provider?.baseUrl.orEmpty()) }
    var model by remember(provider?.id) { mutableStateOf(provider?.model.orEmpty()) }
    var apiKey by remember(provider?.id) { mutableStateOf("") }
    Card(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(if (provider == null) "Yeni provider" else "Provider düzenle", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(name, { name = it }, label = { Text("Ad") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(kind, { kind = it }, label = { Text("Tür: ai, stt veya tts") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(adapter, { adapter = it }, label = { Text("Adapter") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(baseUrl, { baseUrl = it }, label = { Text("Base URL, isteğe bağlı") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(model, { model = it }, label = { Text("Model, isteğe bağlı") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(apiKey, { apiKey = it }, label = { Text(if (provider == null) "API anahtarı" else "Yeni API anahtarı, boşsa değişmez") }, modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { onSave(name, kind, adapter, baseUrl, model, apiKey) }, enabled = !busy) { Text("Kaydet") }
                OutlinedButton(onClick = onCancel, enabled = !busy) { Text("Vazgeç") }
            }
        }
    }
}
