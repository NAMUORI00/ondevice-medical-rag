package com.mededge.rag

import android.content.Context
import android.os.SystemClock
import java.util.Locale

class MedEdgeRagEngine(
    context: Context,
    private val generator: AnswerGenerator = LiteRtGemmaEngine(context),
    assetFileName: String = "medical_qa_sample.jsonl",
) {
    private val records: List<QARecord> =
        context.assets.open(assetFileName).use { MedicalQaAssetLoader.load(it) }
    private val index = HashingVectorIndex(records)

    fun answer(question: String, topK: Int = 3): AnswerResult {
        val totalStart = SystemClock.elapsedRealtimeNanos()
        val retrievalStart = SystemClock.elapsedRealtimeNanos()
        val hits = index.search(question, topK)
        val retrievalMs = elapsedMs(retrievalStart)
        val prompt = buildPrompt(question, hits)
        var generationMs = 0L
        val generated =
            if (hits.isEmpty()) {
                Result.failure(IllegalStateException("No local evidence matched the question."))
            } else if (generator.isReady()) {
                val generationStart = SystemClock.elapsedRealtimeNanos()
                val result = runCatching { generator.generate(prompt) }
                generationMs = elapsedMs(generationStart)
                result
            } else {
                Result.failure(IllegalStateException("Local Gemma4 model file is not available."))
            }

        val answer =
            generated.getOrElse { error ->
                fallbackAnswer(question, hits, error.message ?: "Local generation failed.")
            }.sanitizeAnswerText().withDisclaimer()

        return AnswerResult(
            answer = answer,
            hits = hits,
            prompt = prompt,
            usedLocalModel = generated.isSuccess,
            retrievalMs = retrievalMs,
            generationMs = generationMs,
            totalMs = elapsedMs(totalStart),
        )
    }

    private fun buildPrompt(question: String, hits: List<SearchHit>): String {
        val evidence =
            hits.mapIndexed { idx, hit ->
                val record = hit.record
                val score = String.format(Locale.US, "%.3f", hit.score)
                "- 근거 ${idx + 1}: domain=${record.domain}, type=${record.qType}, score=$score\n  Q: ${record.question}\n  A: ${record.answer}"
            }.joinToString(separator = "\n")

        return """
            <system>
            너는 한국어 의료 정보 보조 시스템이다.
            제공된 근거에 없는 내용은 단정하지 않는다.
            진단, 처방, 응급 판단을 대체하지 않는다.
            $DISCLAIMER
            </system>
            <question>
            $question
            </question>
            <evidence>
            $evidence
            </evidence>
            답변은 1) 요약, 2) 근거:, 3) 주의 문구 순서로 짧게 작성한다.
            답변에는 sample-001 같은 내부 ID를 쓰지 말고 근거 1, 근거 2처럼 표시한다.
        """.trimIndent()
    }

    private fun fallbackAnswer(question: String, hits: List<SearchHit>, reason: String): String {
        if (hits.isEmpty()) {
            return """
                질문: $question
                로컬 검색 인덱스에서 관련 근거를 찾지 못했습니다. 증상이 심하거나 지속되면 의료진에게 상담해야 합니다.
                근거:
                - 없음
                $DISCLAIMER
            """.trimIndent()
        }

        val primary = hits.first().record
        val evidence =
            hits.mapIndexed { idx, hit ->
                val score = String.format(Locale.US, "%.3f", hit.score)
                "- 근거 ${idx + 1} / ${hit.record.domain} / ${hit.record.qType} / score=$score: ${hit.record.answer}"
            }.joinToString(separator = "\n")

        return """
            질문: $question
            로컬 Gemma4 생성기를 사용할 수 없어 검색 근거 기반 템플릿 답변을 표시합니다. 원인: $reason
            요약: ${primary.answer}
            근거:
            $evidence
            $DISCLAIMER
        """.trimIndent()
    }

    private fun String.withDisclaimer(): String =
        if (contains(DISCLAIMER)) this else "$this\n\n$DISCLAIMER"

    private fun elapsedMs(startNanos: Long): Long =
        (SystemClock.elapsedRealtimeNanos() - startNanos) / 1_000_000

    private fun String.sanitizeAnswerText(): String =
        replace(CONTROL_TOKEN_PATTERN, "")
            .replace(ROLE_LINE_PATTERN, "")
            .replace(ROLE_PREFIX_PATTERN, "")
            .replace(XML_PROMPT_TAG_PATTERN, "")
            .replace(BULLET_INTERNAL_ID_PATTERN, "- ")
            .replace(INTERNAL_ID_PATTERN, "")
            .replace(MARKDOWN_HEADING_PATTERN, "")
            .replace(MARKDOWN_LIST_MARKER_PATTERN, "")
            .replace(MARKDOWN_MARKER_PATTERN, "")
            .replace(TRAILING_SPACE_PATTERN, "\n")
            .replace(EXCESS_BLANK_LINE_PATTERN, "\n\n")
            .trim()

    companion object {
        const val DISCLAIMER =
            "본 답변은 연구용 의료 정보 보조 결과이며 진단, 처방, 응급 판단을 대체하지 않습니다. 증상이 심하거나 지속되면 의료진 또는 응급의료기관에 상담하세요."
        private val CONTROL_TOKEN_PATTERN =
            Regex(
                "<\\|?/?(?:start_of_turn|end_of_turn|turn|bos|eos|pad|start_header_id|end_header_id|eot_id|begin_of_text|end_of_text)[^>]*>|</?turn>",
                RegexOption.IGNORE_CASE,
            )
        private val ROLE_LINE_PATTERN = Regex("(?im)^\\s*(?:model|assistant|user)\\s*:?\\s*$\\n?")
        private val ROLE_PREFIX_PATTERN = Regex("(?im)^\\s*(?:model|assistant)\\s*:\\s*")
        private val XML_PROMPT_TAG_PATTERN = Regex("</?(?:system|question|evidence|answer)>", RegexOption.IGNORE_CASE)
        private val BULLET_INTERNAL_ID_PATTERN = Regex("(?im)^\\s*[-*]\\s*(?:sample|row)-\\d+\\s*[:/,-]?\\s*")
        private val INTERNAL_ID_PATTERN = Regex("(?i)\\b(?:sample|row)-\\d+\\s*[:/,-]?\\s*")
        private val MARKDOWN_HEADING_PATTERN = Regex("(?m)^\\s{0,3}#{1,6}\\s*")
        private val MARKDOWN_LIST_MARKER_PATTERN = Regex("(?m)^\\s*[-*]\\s+")
        private val MARKDOWN_MARKER_PATTERN = Regex("(?:\\*\\*|__|`{1,3})")
        private val TRAILING_SPACE_PATTERN = Regex("[ \\t]+\\n")
        private val EXCESS_BLANK_LINE_PATTERN = Regex("\\n{3,}")
    }
}
