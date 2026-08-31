package ai.xultron.app.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.util.Base64
import ai.xultron.app.core.network.ConversationDto
import ai.xultron.app.core.network.HealthDto
import ai.xultron.app.core.network.MemoryDto
import ai.xultron.app.core.network.MessageDto
import ai.xultron.app.core.network.ProviderCredentialDto
import ai.xultron.app.core.network.ProviderDto
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.security.SecureRandom
import java.time.Instant
import java.util.UUID
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * Small app-private backend for offline/device-only mode. It intentionally stores no
 * provider secret and never opens a network listener. Remote mode remains available
 * by setting an HTTPS backend URL.
 */
class LocalBackend(context: Context) {
    private val helper = LocalDatabase(context.applicationContext)

    fun health(): HealthDto = HealthDto(status = "ok", version = "local", time = now())

    fun enroll(username: String, email: String, password: String): ai.xultron.app.core.network.UserDto {
        require(username.isNotBlank() && email.isNotBlank() && password.length >= 8) { "Kullanıcı bilgileri geçersiz." }
        val db = helper.writableDatabase
        val normalizedUsername = username.trim()
        val normalizedEmail = email.trim().lowercase()
        if (exists(db, "username = ? OR email = ?", arrayOf(normalizedUsername, normalizedEmail))) {
            error("Kullanıcı adı veya e-posta zaten kullanılıyor.")
        }
        val id = "usr_local_${UUID.randomUUID()}"
        db.insertOrThrow("users", null, ContentValues().apply {
            put("id", id)
            put("username", normalizedUsername)
            put("email", normalizedEmail)
            put("password_hash", passwordHash(password))
            put("is_guest", 0)
            put("created_at", now())
        })
        return user(id)
    }

    fun guest(): ai.xultron.app.core.network.UserDto {
        val id = "usr_local_${UUID.randomUUID()}"
        helper.writableDatabase.insertOrThrow("users", null, ContentValues().apply {
            put("id", id)
            put("username", "guest_${UUID.randomUUID().toString().take(8)}")
            putNull("email")
            putNull("password_hash")
            put("is_guest", 1)
            put("created_at", now())
        })
        return user(id)
    }

    fun login(identifier: String, password: String): ai.xultron.app.core.network.UserDto {
        val db = helper.readableDatabase
        val record = db.query(
            "users",
            arrayOf("id", "password_hash"),
            "username = ? OR email = ?",
            arrayOf(identifier.trim(), identifier.trim().lowercase()),
            null,
            null,
            null,
            "1",
        ).use { cursor ->
            if (!cursor.moveToFirst()) null else cursor.getString(0) to cursor.getString(1)
        } ?: error("Kullanıcı adı veya parola hatalı.")
        if (!verifyPassword(password, record.second)) error("Kullanıcı adı veya parola hatalı.")
        return user(record.first)
    }

    fun user(userId: String): ai.xultron.app.core.network.UserDto = helper.readableDatabase.query(
        "users",
        arrayOf("id", "username", "email", "is_guest", "created_at"),
        "id = ?",
        arrayOf(userId),
        null,
        null,
        null,
        "1",
    ).use { cursor ->
        if (!cursor.moveToFirst()) error("Yerel kullanıcı bulunamadı.")
        ai.xultron.app.core.network.UserDto(
            id = cursor.getString(0),
            username = cursor.getString(1),
            email = cursor.getStringOrNull(2),
            isGuest = cursor.getInt(3) != 0,
            createdAt = cursor.getStringOrNull(4),
        )
    }

    fun conversations(userId: String): List<ConversationDto> = helper.readableDatabase.query(
        "conversations", null, "user_id = ?", arrayOf(userId), null, null, "updated_at DESC"
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) add(
                ConversationDto(cursor.getString(0), cursor.getString(2), cursor.getString(3), cursor.getString(4))
            )
        }
    }

    fun messages(userId: String, conversationId: String): List<MessageDto> = helper.readableDatabase.query(
        "messages m JOIN conversations c ON c.id = m.conversation_id",
        arrayOf("m.id", "m.conversation_id", "m.role", "m.content", "m.created_at", "m.request_id"),
        "c.user_id = ? AND m.conversation_id = ?",
        arrayOf(userId, conversationId), null, null, "m.created_at ASC"
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) add(
                MessageDto(cursor.getString(0), cursor.getString(1), cursor.getString(2), cursor.getString(3), cursor.getString(4), cursor.getStringOrNull(5))
            )
        }
    }

    fun sendMessage(userId: String, message: String, conversationId: String?): ai.xultron.app.core.network.ChatResponse {
        require(message.isNotBlank()) { "Mesaj boş olamaz." }
        val db = helper.writableDatabase
        val now = now()
        val conversation = conversationId?.takeIf { ownsConversation(db, userId, it) } ?: "cnv_local_${UUID.randomUUID()}"
        db.beginTransaction()
        try {
            if (conversationId == null || !ownsConversation(db, userId, conversation)) {
                db.insertOrThrow("conversations", null, ContentValues().apply {
                    put("id", conversation)
                    put("user_id", userId)
                    put("title", message.trim().take(60))
                    put("created_at", now)
                    put("updated_at", now)
                })
            } else {
                db.update("conversations", ContentValues().apply { put("updated_at", now) }, "id = ?", arrayOf(conversation))
            }
            val requestId = "local_${UUID.randomUUID()}"
            db.insertOrThrow("messages", null, ContentValues().apply {
                put("id", "msg_local_${UUID.randomUUID()}")
                put("conversation_id", conversation)
                put("role", "user")
                put("content", message.trim())
                put("created_at", now)
                put("request_id", requestId)
            })
            db.insertOrThrow("messages", null, ContentValues().apply {
                put("id", "msg_local_${UUID.randomUUID()}")
                put("conversation_id", conversation)
                put("role", "assistant")
                put("content", "Yerel Xultron: ${message.trim()}")
                put("created_at", now())
                put("request_id", requestId)
            })
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        val conversationDto = conversations(userId).first { it.id == conversation }
        return ai.xultron.app.core.network.ChatResponse(conversationDto, messages(userId, conversation).takeLast(2))
    }

    fun memories(userId: String): List<MemoryDto> = helper.readableDatabase.query(
        "memories", null, "user_id = ?", arrayOf(userId), null, null, "updated_at DESC"
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) add(MemoryDto(cursor.getString(0), cursor.getString(2), cursor.getString(3), cursor.getString(4), cursor.getString(5), cursor.getString(6)))
        }
    }

    fun providers(userId: String): List<ProviderDto> = helper.readableDatabase.query(
        "providers", null, "user_id = ?", arrayOf(userId), null, null, "created_at ASC"
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) add(providerFrom(cursor))
        }
    }

    fun createProvider(userId: String, name: String, kind: String, adapter: String, baseUrl: String?, model: String?): ProviderDto {
        val id = "prv_local_${UUID.randomUUID()}"
        helper.writableDatabase.insertOrThrow("providers", null, ContentValues().apply {
            put("id", id); put("user_id", userId); put("name", name.trim()); put("kind", kind.trim()); put("adapter", adapter.trim())
            putNullable("base_url", baseUrl); putNullable("model", model); put("enabled", 1); put("is_default", 0); put("created_at", now())
        })
        return providers(userId).first { it.id == id }
    }

    fun updateProvider(userId: String, providerId: String, name: String, kind: String, adapter: String, baseUrl: String?, model: String?): ProviderDto {
        check(ownsProvider(helper.readableDatabase, userId, providerId)) { "Provider bulunamadı." }
        helper.writableDatabase.update("providers", ContentValues().apply {
            put("name", name.trim()); put("kind", kind.trim()); put("adapter", adapter.trim()); putNullable("base_url", baseUrl); putNullable("model", model)
        }, "id = ? AND user_id = ?", arrayOf(providerId, userId))
        return providers(userId).first { it.id == providerId }
    }

    fun deleteProvider(userId: String, providerId: String) {
        helper.writableDatabase.delete("providers", "id = ? AND user_id = ?", arrayOf(providerId, userId))
    }

    fun providerModels(userId: String, providerId: String): List<String> {
        val provider = providers(userId).firstOrNull { it.id == providerId } ?: return emptyList()
        return provider.model?.let(::listOf).orEmpty()
    }

    fun testProvider(userId: String, providerId: String): JsonObject {
        check(providers(userId).any { it.id == providerId }) { "Provider bulunamadı." }
        return buildJsonObject { put("ok", true); put("mode", "local") }
    }

    fun settings(userId: String): JsonObject {
        val values = mutableMapOf("lowDataMode" to "false", "memoryEnabled" to "true", "conversationHistory" to "true", "voiceHistory" to "false", "saveAudio" to "false", "analytics" to "false", "reducedMotion" to "false", "locale" to "tr", "timeZone" to "UTC")
        helper.readableDatabase.query("settings", arrayOf("key", "value"), "user_id = ?", arrayOf(userId), null, null, null).use { cursor ->
            while (cursor.moveToNext()) values[cursor.getString(0)] = cursor.getString(1)
        }
        return buildJsonObject {
            values.forEach { (key, value) ->
                if (value == "true" || value == "false") put(key, value.toBoolean()) else put(key, value)
            }
        }
    }

    fun patchBooleanSetting(userId: String, key: String, enabled: Boolean): JsonObject {
        helper.writableDatabase.insertWithOnConflict("settings", null, ContentValues().apply { put("user_id", userId); put("key", key); put("value", enabled.toString()) }, SQLiteDatabase.CONFLICT_REPLACE)
        return settings(userId)
    }

    private fun providerFrom(cursor: android.database.Cursor) = ProviderDto(
        id = cursor.getString(0), name = cursor.getString(2), kind = cursor.getString(3), adapter = cursor.getString(4),
        baseUrl = cursor.getStringOrNull(5), model = cursor.getStringOrNull(6), enabled = cursor.getInt(7) != 0, isDefault = cursor.getInt(8) != 0,
        credential = ProviderCredentialDto(configured = false),
    )

    private fun ownsConversation(db: SQLiteDatabase, userId: String, conversationId: String) = exists(db, "id = ? AND user_id = ?", arrayOf(conversationId, userId), "conversations")
    private fun ownsProvider(db: SQLiteDatabase, userId: String, providerId: String) = exists(db, "id = ? AND user_id = ?", arrayOf(providerId, userId), "providers")
    private fun exists(db: SQLiteDatabase, where: String, args: Array<String>, table: String = "users") = db.query(table, arrayOf("id"), where, args, null, null, null, "1").use { it.moveToFirst() }
    private fun now() = Instant.now().toString()

    private fun ContentValues.putNullable(key: String, value: String?) { if (value == null) putNull(key) else put(key, value) }

    private fun passwordHash(password: String): String {
        val salt = ByteArray(16).also(SecureRandom()::nextBytes)
        val spec = PBEKeySpec(password.toCharArray(), salt, 120_000, 256)
        val derived = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
        return "${Base64.encodeToString(salt, Base64.NO_WRAP)}:${Base64.encodeToString(derived, Base64.NO_WRAP)}"
    }

    private fun verifyPassword(password: String, stored: String): Boolean {
        val parts = stored.split(":", limit = 2)
        if (parts.size != 2) return false
        val salt = Base64.decode(parts[0], Base64.NO_WRAP)
        val expected = Base64.decode(parts[1], Base64.NO_WRAP)
        val actual = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(PBEKeySpec(password.toCharArray(), salt, 120_000, expected.size * 8)).encoded
        return java.security.MessageDigest.isEqual(expected, actual)
    }

    private class LocalDatabase(context: Context) : SQLiteOpenHelper(context, "xultron_local.db", null, 1) {
        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, email TEXT UNIQUE, password_hash TEXT, is_guest INTEGER NOT NULL, created_at TEXT NOT NULL)")
            db.execSQL("CREATE TABLE conversations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            db.execSQL("CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, request_id TEXT)")
            db.execSQL("CREATE TABLE memories (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, category TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            db.execSQL("CREATE TABLE providers (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, adapter TEXT NOT NULL, base_url TEXT, model TEXT, enabled INTEGER NOT NULL, is_default INTEGER NOT NULL, created_at TEXT NOT NULL)")
            db.execSQL("CREATE TABLE settings (user_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(user_id, key))")
            db.execSQL("CREATE INDEX messages_conversation_idx ON messages(conversation_id, created_at)")
        }
        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
    }
}

private fun android.database.Cursor.getStringOrNull(index: Int): String? = if (isNull(index)) null else getString(index)
