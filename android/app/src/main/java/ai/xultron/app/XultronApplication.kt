package ai.xultron.app

import android.app.Application

class XultronApplication : Application() {
    val container: AppContainer by lazy { AppContainer(this) }
}
