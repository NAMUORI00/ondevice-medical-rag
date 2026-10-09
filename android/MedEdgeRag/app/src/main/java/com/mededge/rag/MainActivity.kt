package com.mededge.rag

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var engine: MedEdgeRagEngine
    private lateinit var downloadButton: Button
    private lateinit var askButton: Button
    private lateinit var progress: ProgressBar
    private lateinit var statusText: TextView
    private lateinit var downloadProgressText: TextView
    private lateinit var answerText: TextView
    private lateinit var evidenceText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        engine = MedEdgeRagEngine(this)

        val questionInput =
            EditText(this).apply {
                setSingleLine(false)
                minLines = 3
                hint = "증상, 나이, 지속 시간 등을 입력하세요."
                setText("아이가 고열일 때 언제 응급실에 가야 하나요?")
                textSize = 16f
                setPadding(dp(12), dp(10), dp(12), dp(10))
                layoutParams = fullWidthParams(topMarginDp = 10)
            }

        downloadButton = secondaryButton("Gemma4 모델 다운로드")
        askButton = primaryButton("온디바이스 답변 생성")
        progress =
            ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
                visibility = View.GONE
                isIndeterminate = true
                layoutParams = fullWidthParams(topMarginDp = 12)
            }
        statusText = statusBadge(modelStatusText())
        downloadProgressText =
            smallMutedText("다운로드 진행률: 대기 중").apply {
                visibility = View.GONE
                layoutParams = fullWidthParams(topMarginDp = 10)
            }
        answerText = bodyText("답변이 여기에 표시됩니다.")
        evidenceText = monoText("검색 근거가 여기에 표시됩니다.")

        downloadButton.setOnClickListener {
            downloadModel()
        }

        askButton.setOnClickListener {
            val question = questionInput.text.toString().trim()
            if (question.isEmpty()) {
                answerText.text = "질문을 입력하세요."
                evidenceText.text = ""
                return@setOnClickListener
            }

            askButton.isEnabled = false
            downloadButton.isEnabled = false
            progress.visibility = View.VISIBLE
            answerText.text = ""
            evidenceText.text = ""

            executor.execute {
                val result = runCatching { engine.answer(question) }
                runOnUiThread {
                    askButton.isEnabled = true
                    downloadButton.isEnabled = true
                    progress.visibility = View.GONE
                    result
                        .onSuccess {
                            answerText.text = it.answer
                            evidenceText.text = formatEvidence(it)
                            statusText.text = if (it.usedLocalModel) readyStatusText() else modelStatusText()
                        }
                        .onFailure {
                            answerText.text = "오류: ${it.message}"
                            evidenceText.text = ""
                            statusText.text = modelStatusText()
                        }
                }
            }
        }

        refreshModelControls()

        val content =
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(20), dp(28), dp(20), dp(28))
                setBackgroundColor(Color.rgb(245, 247, 250))
                addView(header())
                addView(panel("모델 상태", statusText, downloadProgressText, downloadButton))
                addView(panel("질문", questionInput, askButton, progress))
                addView(panel("답변", answerText))
                addView(panel("근거", evidenceText))
            }

        setContentView(
            ScrollView(this).apply {
                setBackgroundColor(Color.rgb(245, 247, 250))
                addView(content)
            },
        )

        handleAutomationIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleAutomationIntent(intent)
    }

    private fun handleAutomationIntent(intent: Intent) {
        if (intent.getBooleanExtra(EXTRA_SMOKE_TEST, false)) {
            runSmokeTest()
        }
        if (intent.getBooleanExtra(EXTRA_BOOTSTRAP_DOWNLOAD_TEST, false)) {
            runBootstrapDownloadTest()
        }
        if (intent.getBooleanExtra(EXTRA_BENCHMARK_TEST, false)) {
            runBenchmarkTest(intent.getIntExtra(EXTRA_BENCHMARK_REPEAT, 1))
        }
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun downloadModel() {
        if (!ModelBootstrapper.isEnabled) {
            statusText.text = "이 빌드는 모델 다운로드를 지원하지 않습니다."
            return
        }

        downloadButton.isEnabled = false
        askButton.isEnabled = false
        progress.visibility = View.VISIBLE
        progress.isIndeterminate = false
        progress.max = 100
        progress.progress = 0
        downloadProgressText.visibility = View.VISIBLE
        downloadProgressText.text = "다운로드 0%"
        statusText.text = "Gemma4 모델 다운로드를 시작합니다."

        executor.execute {
            val result =
                runCatching {
                    ModelBootstrapper.download(this@MainActivity) { percent ->
                        runOnUiThread {
                            progress.progress = percent
                            downloadProgressText.text = "다운로드 $percent%"
                            statusText.text = "Gemma4 모델 다운로드 중입니다. $percent%"
                        }
                    }
                }
            runOnUiThread {
                downloadButton.isEnabled = true
                askButton.isEnabled = true
                progress.visibility = View.GONE
                progress.isIndeterminate = true
                result
                    .onSuccess {
                        engine = MedEdgeRagEngine(this)
                        refreshModelControls()
                        answerText.text = "Gemma 4 모델 준비가 완료되었습니다."
                    }
                    .onFailure {
                        refreshModelControls()
                        answerText.text = "모델 다운로드 오류: ${it.message}"
                    }
            }
        }
    }

    private fun refreshModelControls() {
        statusText.text = modelStatusText()
        downloadProgressText.visibility = View.GONE
        downloadButton.visibility = if (ModelBootstrapper.isEnabled && !LocalModelStore.hasModel(this)) View.VISIBLE else View.GONE
        downloadButton.text = "Gemma4 모델 다운로드"
    }

    private fun modelStatusText(): String =
        if (LocalModelStore.hasModel(this)) {
            readyStatusText()
        } else if (ModelBootstrapper.isEnabled) {
            "모델 다운로드 필요 · 최초 1회 다운로드 후 앱 내부 저장소에서 로컬 추론"
        } else {
            "오프라인 검증 빌드 · ADB로 ${LocalModelStore.LITERT_MODEL_FILE_NAME} 사전 배치 필요"
        }

    private fun readyStatusText(): String =
        "모델 준비 완료 · Gemma 4 LiteRT-LM 온디바이스 추론"

    private fun formatEvidence(result: AnswerResult): String =
        result.hits.mapIndexed { idx, hit ->
            val score = String.format(Locale.US, "%.3f", hit.score)
            "근거 ${idx + 1} · ${hit.record.domain} · ${hit.record.qType}\n질문: ${hit.record.question}\n답변: ${hit.record.answer}\n관련도: score=$score"
        }.joinToString(separator = "\n\n")

    private fun header(): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(
                TextView(this@MainActivity).apply {
                    text = "MedEdge RAG"
                    textSize = 28f
                    typeface = Typeface.DEFAULT_BOLD
                    setTextColor(Color.rgb(21, 32, 43))
                },
            )
            addView(
                TextView(this@MainActivity).apply {
                    text = "로컬 Gemma 4 의료 Q&A"
                    textSize = 15f
                    setTextColor(Color.rgb(84, 96, 110))
                    setPadding(0, dp(4), 0, dp(4))
                },
            )
        }

    private fun panel(title: String, vararg children: View): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(16), dp(18), dp(18))
            background = rounded(fill = Color.WHITE, stroke = Color.rgb(220, 226, 232))
            layoutParams = fullWidthParams(topMarginDp = 14)
            addView(sectionTitle(title))
            children.forEach { addView(it) }
        }

    private fun sectionTitle(text: String): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 14f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.rgb(44, 54, 65))
            setPadding(0, 0, 0, dp(8))
        }

    private fun statusBadge(text: String): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 14f
            setTextColor(Color.rgb(23, 99, 78))
            setPadding(dp(12), dp(10), dp(12), dp(10))
            background = rounded(fill = Color.rgb(232, 245, 237), stroke = Color.rgb(178, 220, 196))
            layoutParams = fullWidthParams()
        }

    private fun bodyText(text: String): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 16f
            setTextColor(Color.rgb(29, 39, 49))
            setLineSpacing(0f, 1.15f)
            layoutParams = fullWidthParams()
        }

    private fun smallMutedText(text: String): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 13f
            setTextColor(Color.rgb(84, 96, 110))
            layoutParams = fullWidthParams()
        }

    private fun monoText(text: String): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 13f
            typeface = Typeface.MONOSPACE
            setTextColor(Color.rgb(55, 67, 79))
            setLineSpacing(0f, 1.1f)
            layoutParams = fullWidthParams()
        }

    private fun primaryButton(text: String): Button =
        Button(this).apply {
            this.text = text
            setAllCaps(false)
            textSize = 15f
            setTextColor(Color.WHITE)
            minHeight = dp(48)
            background = rounded(fill = Color.rgb(23, 99, 78))
            layoutParams = fullWidthParams(topMarginDp = 12)
        }

    private fun secondaryButton(text: String): Button =
        Button(this).apply {
            this.text = text
            setAllCaps(false)
            textSize = 15f
            setTextColor(Color.rgb(23, 99, 78))
            minHeight = dp(48)
            background = rounded(fill = Color.rgb(236, 243, 241), stroke = Color.rgb(178, 220, 196))
            layoutParams = fullWidthParams(topMarginDp = 12)
        }

    private fun rounded(fill: Int, stroke: Int? = null): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dp(8).toFloat()
            setColor(fill)
            stroke?.let { setStroke(dp(1), it) }
        }

    private fun fullWidthParams(topMarginDp: Int = 0): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ).apply {
            if (topMarginDp > 0) {
                setMargins(0, dp(topMarginDp), 0, 0)
            }
        }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    private fun runSmokeTest() {
        executor.execute {
            val result = runCatching { engine.answer(SMOKE_QUESTION) }
            result
                .onSuccess {
                    Log.i(
                        LOG_TAG,
                        "MEDEDGE_RAG_SMOKE usedLocalModel=${it.usedLocalModel} evidence=${it.hits.size}",
                    )
                }
                .onFailure {
                    Log.e(LOG_TAG, "MEDEDGE_RAG_SMOKE failed=${it.message}")
                }
        }
    }

    private fun runBootstrapDownloadTest() {
        executor.execute {
            val result =
                runCatching {
                    ModelBootstrapper.download(this@MainActivity) { percent ->
                        Log.i(LOG_TAG, "MEDEDGE_BOOTSTRAP_DOWNLOAD progress=$percent")
                    }
                }
            result
                .onSuccess {
                    engine = MedEdgeRagEngine(this)
                    Log.i(
                        LOG_TAG,
                        "MEDEDGE_BOOTSTRAP_DOWNLOAD ready=true bytes=${it.length()}",
                    )
                }
                .onFailure {
                    Log.e(LOG_TAG, "MEDEDGE_BOOTSTRAP_DOWNLOAD failed=${it.message}")
                }
        }
    }

    private fun runBenchmarkTest(requestedRepeats: Int) {
        val repeats = requestedRepeats.coerceIn(1, 10)
        executor.execute {
            var count = 0
            repeat(repeats) { round ->
                BENCHMARK_QUESTIONS.forEachIndexed { index, question ->
                    val result = runCatching { engine.answer(question) }
                    count += 1
                    result
                        .onSuccess {
                            Log.i(
                                LOG_TAG,
                                "MEDEDGE_RAG_BENCHMARK ${
                                    JSONObject()
                                        .put("seq", count)
                                        .put("round", round + 1)
                                        .put("question_index", index + 1)
                                        .put("question", question)
                                        .put("used_local_model", it.usedLocalModel)
                                        .put("evidence", it.hits.size)
                                        .put("retrieval_ms", it.retrievalMs)
                                        .put("generation_ms", it.generationMs)
                                        .put("total_ms", it.totalMs)
                                }",
                            )
                        }
                        .onFailure {
                            Log.e(
                                LOG_TAG,
                                "MEDEDGE_RAG_BENCHMARK ${
                                    JSONObject()
                                        .put("seq", count)
                                        .put("round", round + 1)
                                        .put("question_index", index + 1)
                                        .put("question", question)
                                        .put("used_local_model", false)
                                        .put("error", it.message ?: "unknown")
                                }",
                            )
                        }
                }
            }
            Log.i(LOG_TAG, "MEDEDGE_RAG_BENCHMARK_DONE count=$count")
        }
    }

    companion object {
        private const val EXTRA_SMOKE_TEST = "smoke_test"
        private const val EXTRA_BOOTSTRAP_DOWNLOAD_TEST = "bootstrap_download_test"
        private const val EXTRA_BENCHMARK_TEST = "benchmark_test"
        private const val EXTRA_BENCHMARK_REPEAT = "benchmark_repeat"
        private const val LOG_TAG = "MedEdgeRag"
        private const val SMOKE_QUESTION = "아이가 고열일 때 언제 응급실에 가야 하나요?"
        private val BENCHMARK_QUESTIONS =
            listOf(
                "아이가 고열일 때 언제 응급실에 가야 하나요?",
                "임신 중 복통이 있으면 어떻게 해야 하나요?",
                "갑자기 한쪽 팔다리에 힘이 빠지면 어떻게 해야 하나요?",
            )
    }
}
