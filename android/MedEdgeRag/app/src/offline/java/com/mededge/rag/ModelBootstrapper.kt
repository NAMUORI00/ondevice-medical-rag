package com.mededge.rag

import android.content.Context
import java.io.File

object ModelBootstrapper {
    const val isEnabled = false

    fun download(context: Context, onProgress: (Int) -> Unit): File {
        onProgress(0)
        throw UnsupportedOperationException("Model download is disabled in the offline build.")
    }
}
