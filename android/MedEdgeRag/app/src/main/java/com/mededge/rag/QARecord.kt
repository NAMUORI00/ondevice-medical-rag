package com.mededge.rag

data class QARecord(
    val qaId: String,
    val domain: String,
    val qType: String,
    val question: String,
    val answer: String,
    val source: String,
)

data class SearchHit(
    val record: QARecord,
    val score: Double,
)

data class AnswerResult(
    val answer: String,
    val hits: List<SearchHit>,
    val prompt: String,
    val usedLocalModel: Boolean,
    val retrievalMs: Long = 0,
    val generationMs: Long = 0,
    val totalMs: Long = 0,
)

interface AnswerGenerator {
    fun isReady(): Boolean
    fun generate(prompt: String): String
}
