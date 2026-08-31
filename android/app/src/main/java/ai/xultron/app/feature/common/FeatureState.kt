package ai.xultron.app.feature.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ai.xultron.app.core.model.Loadable
import java.io.IOException

fun Throwable.toLoadableError(): Loadable<Nothing> = when (this) {
    is IOException -> Loadable.Offline
    else -> Loadable.Error(message ?: "İstek tamamlanamadı.")
}

@Composable
fun <T> LoadablePane(
    state: Loadable<T>,
    onRetry: () -> Unit,
    content: @Composable (T) -> Unit,
) {
    when (state) {
        Loadable.Idle, Loadable.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        Loadable.Offline -> StateMessage("Çevrimdışısınız", "Ağ bağlantısı geldiğinde yeniden deneyin.", onRetry)
        is Loadable.Empty -> StateMessage("Henüz içerik yok", state.message, onRetry)
        is Loadable.Error -> StateMessage("Bir sorun oluştu", state.message, if (state.retryable) onRetry else null)
        is Loadable.Content -> content(state.value)
    }
}

@Composable
private fun StateMessage(title: String, message: String, onRetry: (() -> Unit)?) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(title, style = MaterialTheme.typography.titleLarge)
        Text(message, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        onRetry?.let { Button(onClick = it, modifier = Modifier.padding(top = 12.dp)) { Text("Yeniden dene") } }
    }
}
