package ai.xultron.app.feature.voice

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Stores only an encrypted, derived profile. Enrollment recordings are never written to disk. */
class EncryptedVoiceProfileStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    fun read(): ExperimentalVoiceProfile? = preferences.getString(PROFILE, null)?.let { encoded ->
        runCatching {
            val packed = Base64.decode(encoded, Base64.NO_WRAP)
            require(packed.size > IV_SIZE)
            val cipher = Cipher.getInstance(TRANSFORMATION).apply {
                init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(TAG_BITS, packed.copyOfRange(0, IV_SIZE)))
            }
            Json.decodeFromString<StoredVoiceProfile>(cipher.doFinal(packed.copyOfRange(IV_SIZE, packed.size)).decodeToString()).toDomain()
        }.getOrElse {
            clear()
            null
        }
    }

    fun write(profile: ExperimentalVoiceProfile) {
        val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
        val plaintext = Json.encodeToString(StoredVoiceProfile.from(profile)).encodeToByteArray()
        val packed = cipher.iv + cipher.doFinal(plaintext)
        preferences.edit().putString(PROFILE, Base64.encodeToString(packed, Base64.NO_WRAP)).apply()
    }

    fun clear() = preferences.edit().remove(PROFILE).apply()

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE).apply {
            init(KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build())
        }.generateKey()
    }

    @Serializable
    private data class StoredVoiceProfile(
        val version: Int,
        val enrolledAttempts: Int,
        val meanRmsDbfs: Double,
        val meanSpeechFrameRatio: Double,
    ) {
        fun toDomain() = ExperimentalVoiceProfile(version, enrolledAttempts, meanRmsDbfs, meanSpeechFrameRatio)
        companion object { fun from(value: ExperimentalVoiceProfile) = StoredVoiceProfile(value.version, value.enrolledAttempts, value.meanRmsDbfs, value.meanSpeechFrameRatio) }
    }

    private companion object {
        const val PREFERENCES = "xultron_encrypted_voice_profile"
        const val PROFILE = "profile"
        const val KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "xultron.voice.profile.aes.v1"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_SIZE = 12
        const val TAG_BITS = 128
    }
}
