package ai.xultron.app.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import ai.xultron.app.MainActivity
import ai.xultron.app.R

/**
 * A passive, branded entry point from the launcher.
 *
 * The widget deliberately does not expose voice, monitoring, or background state. Its sole
 * action opens the app, where those capabilities remain explicitly user-controlled.
 */
class XultronAppWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        appWidgetIds.forEach { appWidgetId ->
            appWidgetManager.updateAppWidget(appWidgetId, createRemoteViews(context))
        }
    }

    companion object {
        private const val ACTION_OPEN_FROM_WIDGET = "ai.xultron.app.action.OPEN_FROM_WIDGET"

        internal fun createRemoteViews(context: Context): RemoteViews =
            RemoteViews(context.packageName, R.layout.xultron_app_widget).apply {
                setOnClickPendingIntent(R.id.xultron_widget_root, openAppPendingIntent(context))
            }

        private fun openAppPendingIntent(context: Context): PendingIntent {
            val intent = Intent(context, MainActivity::class.java).apply {
                action = ACTION_OPEN_FROM_WIDGET
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            return PendingIntent.getActivity(
                context,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }
    }
}
