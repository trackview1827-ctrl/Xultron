package ai.xultron.app.core.model

sealed interface Loadable<out T> {
    data object Idle : Loadable<Nothing>
    data object Loading : Loadable<Nothing>
    data object Offline : Loadable<Nothing>
    data class Content<T>(val value: T) : Loadable<T>
    data class Empty(val message: String) : Loadable<Nothing>
    data class Error(val message: String, val retryable: Boolean = true) : Loadable<Nothing>
}
