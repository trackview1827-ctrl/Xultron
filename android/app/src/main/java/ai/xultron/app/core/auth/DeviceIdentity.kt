package ai.xultron.app.core.auth

import android.content.Context
import android.os.Build
import ai.xultron.app.BuildConfig
import ai.xultron.app.core.network.DeviceDescriptorDto
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.UUID

class DeviceIdentity(context: Context) {
    private val preferences = context.getSharedPreferences("xultron_device_identity", Context.MODE_PRIVATE)

    fun descriptor(): DeviceDescriptorDto {
        val installationId = preferences.getString(INSTALLATION_ID, null)
            ?: UUID.randomUUID().toString().also { preferences.edit().putString(INSTALLATION_ID, it).apply() }
        return DeviceDescriptorDto(
            installationId = installationId,
            name = "${Build.MANUFACTURER} ${Build.MODEL}".trim().take(120),
            appVersion = BuildConfig.VERSION_NAME,
            metadata = buildJsonObject {
                put("sdk", Build.VERSION.SDK_INT)
                put("release", Build.VERSION.RELEASE)
                put("supportedAbis", Build.SUPPORTED_ABIS.joinToString(","))
            },
        )
    }

    private companion object { const val INSTALLATION_ID = "installation_id" }
}
