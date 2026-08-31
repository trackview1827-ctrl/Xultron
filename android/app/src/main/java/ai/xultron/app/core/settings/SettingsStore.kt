package ai.xultron.app.core.settings

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import ai.xultron.app.core.network.BackendEndpoint
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.xultronDataStore by preferencesDataStore(name = "xultron_settings")

class SettingsStore(private val context: Context) {
    val backendUrl: Flow<String> = context.xultronDataStore.data.map { preferences ->
        preferences[BACKEND_URL] ?: BackendEndpoint.LOCAL
    }

    val lowDataMode: Flow<Boolean> = booleanFlow(LOW_DATA_MODE, false)

    suspend fun setBackendUrl(value: String): Result<String> {
        val normalized = BackendEndpoint.normalize(value)
            ?: return Result.failure(IllegalArgumentException("HTTPS backend URL veya Termux için http://127.0.0.1:5000 girin."))
        context.xultronDataStore.edit { it[BACKEND_URL] = normalized }
        return Result.success(normalized)
    }

    suspend fun setLowDataMode(enabled: Boolean) {
        context.xultronDataStore.edit { it[LOW_DATA_MODE] = enabled }
    }

    private fun booleanFlow(key: Preferences.Key<Boolean>, default: Boolean): Flow<Boolean> =
        context.xultronDataStore.data.map { it[key] ?: default }

    private companion object {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val LOW_DATA_MODE = booleanPreferencesKey("low_data_mode")
    }
}
