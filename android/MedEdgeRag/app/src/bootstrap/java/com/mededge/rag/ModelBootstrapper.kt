package com.mededge.rag

import android.content.Context
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

object ModelBootstrapper {
    const val isEnabled = true

    fun download(context: Context, onProgress: (Int) -> Unit): File {
        val destination = LocalModelStore.appModelFile(context)
        destination.parentFile?.mkdirs()
        if (destination.isFile) {
            if (sha256(destination) == BuildConfig.MODEL_SHA256) {
                onProgress(100)
                return destination
            }
            destination.delete()
        }

        val partial = File(destination.parentFile, "${destination.name}.download")
        partial.delete()

        val connection = URL(BuildConfig.MODEL_DOWNLOAD_URL).openConnection() as HttpURLConnection
        connection.connectTimeout = 15_000
        connection.readTimeout = 60_000
        connection.instanceFollowRedirects = true
        connection.requestMethod = "GET"

        try {
            val responseCode = connection.responseCode
            require(responseCode in 200..299) { "Model download failed with HTTP $responseCode." }
            val totalBytes = connection.contentLengthLong
            var copiedBytes = 0L

            connection.inputStream.use { input ->
                partial.outputStream().use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                        copiedBytes += read
                        if (totalBytes > 0) {
                            onProgress(((copiedBytes * 100) / totalBytes).toInt().coerceIn(0, 99))
                        }
                    }
                }
            }

            val actualHash = sha256(partial)
            require(actualHash == BuildConfig.MODEL_SHA256) {
                "Model checksum mismatch. Expected ${BuildConfig.MODEL_SHA256} but got $actualHash"
            }

            destination.delete()
            require(partial.renameTo(destination)) { "Failed to move downloaded model into app storage." }
            onProgress(100)
            return destination
        } catch (error: Throwable) {
            partial.delete()
            throw error
        } finally {
            connection.disconnect()
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
