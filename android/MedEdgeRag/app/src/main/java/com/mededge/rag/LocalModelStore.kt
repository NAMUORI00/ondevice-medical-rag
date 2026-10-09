package com.mededge.rag

import android.content.Context
import java.io.File

object LocalModelStore {
    const val LITERT_MODEL_FILE_NAME = "gemma-4-E2B-it.litertlm"
    const val ADB_LITERT_MODEL_PATH = "/data/local/tmp/llm/gemma-4-E2B-it.litertlm"

    fun appModelFile(context: Context): File =
        File(File(context.filesDir, "models"), LITERT_MODEL_FILE_NAME)

    fun activeModelPath(context: Context): String {
        val model = candidateModelFiles(context).firstOrNull { it.isFile }
        return model?.absolutePath ?: ADB_LITERT_MODEL_PATH
    }

    fun hasModel(context: Context): Boolean =
        candidateModelFiles(context).any { it.isFile }

    private fun candidateModelFiles(context: Context): List<File> =
        listOf(
            File(File(context.filesDir, "models"), LITERT_MODEL_FILE_NAME),
            File(ADB_LITERT_MODEL_PATH),
        )
}
