package ai.xultron.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun WebFrontendBootstrapScreen(
    backendUrl: String,
    connection: ConnectionState,
    busy: Boolean,
    error: String?,
    onSaveBackendUrl: (String) -> Unit,
) {
    var url by remember(backendUrl) { mutableStateOf(backendUrl.takeUnless { it == "local://xultron" }.orEmpty()) }
    val connected = connection is ConnectionState.Connected

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier.fillMaxSize().padding(horizontal = 28.dp, vertical = 32.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.Start,
        ) {
            Text("XULTRON", style = MaterialTheme.typography.displaySmall, color = MaterialTheme.colorScheme.primary)
            Text("Web workspace", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            Text(
                "Uygulamanın tüm ana arayüzü backend üzerinden web olarak açılır. Önce backend adresini bağlayın.",
                style = MaterialTheme.typography.bodyLarge,
            )
            Spacer(Modifier.height(24.dp))
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Backend URL") },
                supportingText = { Text("Termux: http://127.0.0.1:5000 · VDS: https://alan-adiniz") },
                singleLine = true,
                enabled = !busy,
            )
            Spacer(Modifier.height(12.dp))
            Button(
                onClick = { onSaveBackendUrl(url) },
                enabled = url.isNotBlank() && !busy,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (busy) CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.height(20.dp))
                else Text("Web arayüzünü aç")
            }
            Spacer(Modifier.height(12.dp))
            Text(
                when {
                    connected -> "Backend bağlı. Web arayüzü hazırlanıyor."
                    connection is ConnectionState.Unreachable -> "Backend'e erişilemiyor. Adresi ve servisi kontrol edin."
                    else -> "Web giriş ekranı bağlantıdan sonra açılacak."
                },
                color = if (connection is ConnectionState.Unreachable) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium,
            )
            error?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
