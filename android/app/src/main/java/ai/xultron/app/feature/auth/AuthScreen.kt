package ai.xultron.app.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import ai.xultron.app.ui.ConnectionState

@Composable
fun AuthScreen(
    backendUrl: String,
    connectionState: ConnectionState,
    busy: Boolean,
    error: String?,
    onSaveBackendUrl: (String) -> Unit,
    onLogin: (String, String) -> Unit,
    onEnroll: (String, String, String) -> Unit,
    onGuest: () -> Unit,
    onRetry: () -> Unit,
) {
    var url by remember(backendUrl) { mutableStateOf(backendUrl) }
    var identifier by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var registering by remember { mutableStateOf(false) }
    val connected = connectionState is ConnectionState.Connected

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text("XULTRON", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
            Text("Güvenli Android istemcisi", style = MaterialTheme.typography.bodyLarge)
            Spacer(Modifier.height(24.dp))

            Text("Backend", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("Backend URL") },
                supportingText = { Text("Uzak: https://... · Termux: http://127.0.0.1:5000") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Button(onClick = { onSaveBackendUrl(url) }, enabled = !busy) { Text("Kaydet ve test et") }
                ConnectionLabel(connectionState)
            }
            if (connectionState is ConnectionState.Unreachable) {
                OutlinedButton(onClick = onRetry) { Text("Yeniden dene") }
            }

            Spacer(Modifier.height(24.dp))
            HorizontalDivider()
            Spacer(Modifier.height(24.dp))
            Text(if (registering) "Hesap oluştur" else "Oturum aç", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = identifier,
                onValueChange = { identifier = it },
                label = { Text(if (registering) "Kullanıcı adı" else "Kullanıcı adı veya e-posta") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            if (registering) {
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("E-posta") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("Parola veya PIN") },
                visualTransformation = PasswordVisualTransformation(),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        if (registering) onEnroll(identifier, email, password)
                        else onLogin(identifier, password)
                    },
                    enabled = connected && identifier.isNotBlank() && password.isNotBlank() &&
                        (!registering || email.isNotBlank()) && !busy,
                ) { Text(if (registering) "Hesap oluştur" else "Giriş") }
                OutlinedButton(onClick = onGuest, enabled = connected && !busy) { Text("Misafir devam et") }
                if (busy) CircularProgressIndicator(modifier = Modifier.height(32.dp))
            }
            OutlinedButton(
                onClick = { registering = !registering },
                enabled = !busy,
            ) { Text(if (registering) "Zaten hesabım var" else "Yeni hesap oluştur") }
            error?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun ConnectionLabel(state: ConnectionState) {
    val label = when (state) {
        ConnectionState.NotConfigured -> "URL gerekli"
        ConnectionState.Offline -> "Çevrimdışı"
        ConnectionState.Checking -> "Kontrol ediliyor"
        is ConnectionState.Connected -> "Bağlı${state.version?.let { " · v$it" }.orEmpty()}"
        is ConnectionState.Unreachable -> "Erişilemiyor"
    }
    Text(label, color = if (state is ConnectionState.Connected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
}
