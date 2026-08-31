package ai.xultron.app.core.permissions

import android.Manifest
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import ai.xultron.app.core.capabilities.Capability
import ai.xultron.app.core.capabilities.PermissionDisposition

data class PermissionSnapshot(
    val capability: Capability,
    val title: String,
    val disposition: PermissionDisposition,
    val detail: String,
    val runtimePermission: String? = null,
)

class AndroidPermissionManager(private val context: Context) {
    private val requestHistory = context.getSharedPreferences("xultron_permission_history", Context.MODE_PRIVATE)

    fun snapshots(): List<PermissionSnapshot> = listOf(
        runtime(Capability.MICROPHONE, "Mikrofon", Manifest.permission.RECORD_AUDIO, PackageManager.FEATURE_MICROPHONE),
        runtime(Capability.CAMERA, "Kamera", Manifest.permission.CAMERA, PackageManager.FEATURE_CAMERA_ANY),
        foregroundLocation(),
        backgroundLocation(),
        runtime(Capability.SENSORS, "Vücut sensörleri", Manifest.permission.BODY_SENSORS, PackageManager.FEATURE_SENSOR_HEART_RATE),
        notifications(),
        overlay(),
    )

    fun settingsIntent(snapshot: PermissionSnapshot): Intent = when {
        snapshot.capability == Capability.LOCATION_FOREGROUND && !locationServicesEnabled() ->
            Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
        snapshot.capability == Capability.NOTIFICATIONS ->
            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
        snapshot.capability == Capability.DISPLAY_OVER_OTHER_APPS ->
            Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION).setData(Uri.parse("package:${context.packageName}"))
        else -> Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).setData(Uri.parse("package:${context.packageName}"))
    }.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    fun markRequested(permission: String) {
        requestHistory.edit().putBoolean(permission, true).apply()
    }

    private fun foregroundLocation(): PermissionSnapshot {
        if (!context.packageManager.hasSystemFeature(PackageManager.FEATURE_LOCATION)) {
            return unavailable(Capability.LOCATION_FOREGROUND, "Konum")
        }
        if (!locationServicesEnabled()) {
            return PermissionSnapshot(
                Capability.LOCATION_FOREGROUND,
                "Konum",
                PermissionDisposition.REQUIRES_SETTINGS,
                "Cihaz konum servisleri kapalı.",
                Manifest.permission.ACCESS_FINE_LOCATION,
            )
        }
        return runtime(Capability.LOCATION_FOREGROUND, "Konum", Manifest.permission.ACCESS_FINE_LOCATION, null)
    }

    private fun backgroundLocation(): PermissionSnapshot {
        if (!isGranted(Manifest.permission.ACCESS_FINE_LOCATION)) {
            return PermissionSnapshot(
                Capability.LOCATION_BACKGROUND,
                "Arka plan konumu",
                PermissionDisposition.DENIED,
                "Önce foreground konum izni verilmelidir.",
                null,
            )
        }
        if (isGranted(Manifest.permission.ACCESS_BACKGROUND_LOCATION)) {
            return granted(Capability.LOCATION_BACKGROUND, "Arka plan konumu")
        }
        return PermissionSnapshot(
            Capability.LOCATION_BACKGROUND,
            "Arka plan konumu",
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) PermissionDisposition.REQUIRES_SETTINGS else permissionDisposition(Manifest.permission.ACCESS_BACKGROUND_LOCATION),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) "Android ayarlarından “Her zaman izin ver” seçilmelidir." else "Ayrı kullanıcı onayı gerekir.",
            if (Build.VERSION.SDK_INT == Build.VERSION_CODES.Q) Manifest.permission.ACCESS_BACKGROUND_LOCATION else null,
        )
    }

    private fun notifications(): PermissionSnapshot {
        val title = "Bildirimler"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !isGranted(Manifest.permission.POST_NOTIFICATIONS)) {
            return PermissionSnapshot(
                Capability.NOTIFICATIONS,
                title,
                permissionDisposition(Manifest.permission.POST_NOTIFICATIONS),
                "Android 13+ bildirim izni gerekli.",
                Manifest.permission.POST_NOTIFICATIONS,
            )
        }
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            return PermissionSnapshot(Capability.NOTIFICATIONS, title, PermissionDisposition.REQUIRES_SETTINGS, "Bildirimler uygulama ayarlarında kapalı.")
        }
        return granted(Capability.NOTIFICATIONS, title)
    }

    private fun overlay(): PermissionSnapshot {
        val title = "Diğer uygulamaların üzerinde göster"
        return if (Settings.canDrawOverlays(context)) {
            granted(Capability.DISPLAY_OVER_OTHER_APPS, title)
        } else {
            PermissionSnapshot(
                Capability.DISPLAY_OVER_OTHER_APPS,
                title,
                PermissionDisposition.REQUIRES_SETTINGS,
                "Bu özel erişim yalnız Android ayarlarından kullanıcı tarafından verilebilir.",
            )
        }
    }

    private fun runtime(capability: Capability, title: String, permission: String, feature: String?): PermissionSnapshot {
        if (feature != null && !context.packageManager.hasSystemFeature(feature)) return unavailable(capability, title)
        if (isGranted(permission)) return granted(capability, title)
        return PermissionSnapshot(capability, title, permissionDisposition(permission), "Android izni verilmedi.", permission)
    }

    private fun permissionDisposition(permission: String): PermissionDisposition {
        return if (requestHistory.getBoolean(permission, false)) {
            PermissionDisposition.REQUIRES_SETTINGS
        } else {
            PermissionDisposition.DENIED
        }
    }

    private fun isGranted(permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    private fun locationServicesEnabled(): Boolean =
        context.getSystemService(LocationManager::class.java).isLocationEnabled

    private fun granted(capability: Capability, title: String) =
        PermissionSnapshot(capability, title, PermissionDisposition.GRANTED, "İzin verildi.")

    private fun unavailable(capability: Capability, title: String) =
        PermissionSnapshot(capability, title, PermissionDisposition.NOT_AVAILABLE, "Bu cihazda ilgili donanım/özellik yok.")
}
