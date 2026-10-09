package com.mededge.rag

import android.content.Context
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import java.io.File

class LiteRtGemmaEngine(
    private val context: Context,
    private val modelPath: String? = null,
) : AnswerGenerator {
    override fun isReady(): Boolean = File(resolvedModelPath()).isFile

    @OptIn(ExperimentalApi::class)
    override fun generate(prompt: String): String {
        val activeModelPath = resolvedModelPath()
        require(File(activeModelPath).isFile) { "Local Gemma4 LiteRT-LM model file not found: $activeModelPath" }

        val engineConfig =
            EngineConfig(
                modelPath = activeModelPath,
                backend = Backend.CPU(),
                cacheDir = context.cacheDir.absolutePath,
            )

        Engine(engineConfig).use { engine ->
            engine.initialize()
            engine.createConversation().use { conversation ->
                val message = conversation.sendMessage(prompt)
                return conversation.renderMessageIntoString(message)
            }
        }
    }

    private fun resolvedModelPath(): String =
        modelPath ?: LocalModelStore.activeModelPath(context)

    companion object {
        const val DEFAULT_MODEL_PATH = "/data/local/tmp/llm/gemma-4-E2B-it.litertlm"
        const val DEFAULT_MODEL_FILE = "gemma-4-E2B-it.litertlm"
    }
}
