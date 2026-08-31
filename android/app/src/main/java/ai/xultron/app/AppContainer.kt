package ai.xultron.app

import android.content.Context
import ai.xultron.app.core.auth.AuthRepository
import ai.xultron.app.core.auth.EncryptedSessionStore
import ai.xultron.app.core.auth.DeviceIdentity
import ai.xultron.app.core.capabilities.CapabilityEngine
import ai.xultron.app.core.network.ApiFactory
import ai.xultron.app.core.network.ConnectivityObserver
import ai.xultron.app.core.permissions.AndroidPermissionManager
import ai.xultron.app.core.security.AndroidKeystoreSecretStorage
import ai.xultron.app.core.settings.SettingsStore
import ai.xultron.app.data.XultronRepository
import ai.xultron.app.data.LocalBackend

class AppContainer(context: Context) {
    private val appContext = context.applicationContext

    val settingsStore = SettingsStore(appContext)
    val connectivityObserver = ConnectivityObserver(appContext)
    val capabilityEngine = CapabilityEngine()
    val permissionManager = AndroidPermissionManager(appContext)
    val sessionStore = EncryptedSessionStore(
        storage = AndroidKeystoreSecretStorage(appContext),
    )
    val deviceIdentity = DeviceIdentity(appContext)
    val localBackend = LocalBackend(appContext)
    val apiFactory = ApiFactory(sessionStore)
    val authRepository = AuthRepository(apiFactory, sessionStore, deviceIdentity, localBackend)
    val repository = XultronRepository(apiFactory, authRepository, localBackend)
}
