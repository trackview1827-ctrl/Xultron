package ai.xultron.app.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
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
import ai.xultron.app.core.network.UserDto
import ai.xultron.app.data.XultronRepository
import ai.xultron.app.feature.common.LoadablePane
import ai.xultron.app.feature.common.toLoadableError
import ai.xultron.app.ui.ConnectionState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject

class SettingsViewModel(private val repository: XultronRepository, private val backendUrl: String) : ViewModel() {
    private val mutableState = MutableStateFlow<Loadable<JsonObject>>(Loadable.Idle)
    val state: StateFlow<Loadable<JsonObject>> = mutableState.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        mutableState.value = Loadable.Loading
        runCatching { repository.settings(backendUrl) }
            .onSuccess { mutableState.value = Loadable.Content(it) }
            .onFailure { mutableState.value = it.toLoadableError() }
    }
}

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    user: UserDto,
    backendUrl: String,
    connection: ConnectionState,
    lowDataMode: Boolean,
    onSetBackendUrl: (String) -> Unit,
    onLowDataModeChange: (Boolean) -> Unit,
    onLogout: () -> Unit,
    permissionsContent: @Composable () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var editedUrl by remember(backendUrl) { mutableStateOf(backendUrl) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Hesap", style = MaterialTheme.typography.titleMedium)
                Text(user.username)
                Text(if (user.isGuest) "Misafir oturumu" else user.email ?: "Yerel hesap", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button(onClick = onLogout) { Text("Çıkış yap") }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Backend bağlantısı", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(editedUrl, { editedUrl = it }, modifier = Modifier.fillMaxWidth(), label = { Text("HTTPS URL") })
                Text(connection.label(), color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button(onClick = { onSetBackendUrl(editedUrl) }) { Text("Kaydet") }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Düşük veri modu", style = MaterialTheme.typography.titleMedium)
                    Text("Yerel istemci ağ kullanımını sınırlar.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = lowDataMode, onCheckedChange = onLowDataModeChange)
            }
        }
        permissionsContent()
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Backend ayarları", style = MaterialTheme.typography.titleMedium)
                LoadablePane(state, viewModel::refresh) { settings ->
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        settings.entries.sortedBy { it.key }.forEach { (key, value) -> Text("$key: $value", style = MaterialTheme.typography.bodySmall) }
                    }
                }
            }
        }
    }
}

private fun ConnectionState.label(): String = when (this) {
    ConnectionState.NotConfigured -> "Yapılandırılmadı"
    ConnectionState.Offline -> "Çevrimdışı"
    ConnectionState.Checking -> "Kontrol ediliyor"
    is ConnectionState.Connected -> "Bağlı${version?.let { " · v$it" }.orEmpty()}"
    is ConnectionState.Unreachable -> "Erişilemiyor: $message"
}
