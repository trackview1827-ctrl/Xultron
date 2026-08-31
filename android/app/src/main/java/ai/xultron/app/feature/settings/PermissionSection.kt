package ai.xultron.app.feature.settings

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.xultron.app.core.capabilities.CapabilityDecision
import ai.xultron.app.core.capabilities.CapabilityEngine
import ai.xultron.app.core.capabilities.CapabilityRequest
import ai.xultron.app.core.capabilities.PermissionDisposition
import ai.xultron.app.core.capabilities.PhaseCapabilityPolicy
import ai.xultron.app.core.permissions.AndroidPermissionManager
import ai.xultron.app.core.permissions.PermissionSnapshot
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class PermissionViewModel(
    private val manager: AndroidPermissionManager,
    private val engine: CapabilityEngine,
) : ViewModel() {
    private val mutableState = MutableStateFlow<List<PermissionSnapshot>>(emptyList())
    val state: StateFlow<List<PermissionSnapshot>> = mutableState.asStateFlow()
    init { refresh() }
    fun refresh() { mutableState.value = manager.snapshots() }
    fun decision(snapshot: PermissionSnapshot): CapabilityDecision = engine.evaluate(
        CapabilityRequest(
            capability = snapshot.capability,
            userEnabled = PhaseCapabilityPolicy.isUserEnabled(snapshot.capability),
            permission = snapshot.disposition,
            featureImplemented = PhaseCapabilityPolicy.isImplemented(snapshot.capability),
        ),
    )
    fun settingsIntent(snapshot: PermissionSnapshot): Intent = manager.settingsIntent(snapshot)
}

class PermissionViewModelFactory(
    private val manager: AndroidPermissionManager,
    private val engine: CapabilityEngine,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = PermissionViewModel(manager, engine) as T
}

@Composable
fun PermissionSection(manager: AndroidPermissionManager, engine: CapabilityEngine) {
    val context = LocalContext.current
    val viewModel: PermissionViewModel = viewModel(factory = rememberPermissionFactory(manager, engine))
    val snapshots by viewModel.state.collectAsStateWithLifecycle()
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { viewModel.refresh() }
    val settingsLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { viewModel.refresh() }
    LaunchedEffect(Unit) { viewModel.refresh() }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Android izinleri", style = MaterialTheme.typography.titleMedium)
            Text("Durumlar Android'den okunur. Bilinmeyen veya kısıtlı durumlar fail-closed reddedilir.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            snapshots.forEach { snapshot ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(snapshot.title)
                        Text(snapshot.disposition.label(), style = MaterialTheme.typography.labelMedium, color = snapshot.disposition.color())
                        Text(snapshot.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    when (val decision = viewModel.decision(snapshot)) {
                        is CapabilityDecision.RequestPermission -> snapshot.runtimePermission?.let { permission ->
                            Button(onClick = {
                                manager.markRequested(permission)
                                permissionLauncher.launch(permission)
                            }) { Text("İzin iste") }
                        } ?: OutlinedButton(onClick = { settingsLauncher.launch(viewModel.settingsIntent(snapshot)) }) { Text("Ayarlar") }
                        is CapabilityDecision.OpenSettings -> OutlinedButton(onClick = { settingsLauncher.launch(viewModel.settingsIntent(snapshot)) }) { Text("Ayarlar") }
                        is CapabilityDecision.Denied -> Text(
                            decision.reason,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        else -> Unit
                    }
                }
            }
        }
    }
}

@Composable
private fun rememberPermissionFactory(manager: AndroidPermissionManager, engine: CapabilityEngine) =
    androidx.compose.runtime.remember(manager, engine) { PermissionViewModelFactory(manager, engine) }

@Composable
private fun PermissionDisposition.color() = when (this) {
    PermissionDisposition.GRANTED -> MaterialTheme.colorScheme.primary
    PermissionDisposition.DENIED, PermissionDisposition.REQUIRES_SETTINGS -> MaterialTheme.colorScheme.tertiary
    else -> MaterialTheme.colorScheme.error
}

private fun PermissionDisposition.label(): String = when (this) {
    PermissionDisposition.GRANTED -> "Granted"
    PermissionDisposition.DENIED -> "Denied"
    PermissionDisposition.REQUIRES_SETTINGS -> "Requires Settings"
    PermissionDisposition.RESTRICTED -> "Restricted"
    PermissionDisposition.NOT_AVAILABLE -> "Not available"
    PermissionDisposition.UNKNOWN -> "Unknown"
}
