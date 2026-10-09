package com.mededge.rag

import java.security.MessageDigest
import kotlin.math.sqrt

class HashingVectorIndex(
    records: List<QARecord>,
    private val dimensions: Int = 384,
) {
    private val entries: List<VectorEntry> =
        records.map { record ->
            VectorEntry(record, vectorize("${record.question} ${record.answer} ${record.domain} ${record.qType}"))
        }

    fun search(query: String, topK: Int = 3): List<SearchHit> {
        val queryVector = vectorize(query)
        return entries
            .map { SearchHit(it.record, cosine(queryVector, it.vector)) }
            .filter { it.score > 0.0 }
            .sortedByDescending { it.score }
            .take(topK)
    }

    private fun vectorize(text: String): DoubleArray {
        val vector = DoubleArray(dimensions)
        tokenize(text).forEach { token ->
            vector[stableIndex(token)] += 1.0
        }

        val norm = sqrt(vector.sumOf { it * it })
        if (norm > 0.0) {
            for (index in vector.indices) {
                vector[index] /= norm
            }
        }
        return vector
    }

    private fun tokenize(text: String): List<String> =
        tokenPattern
            .findAll(text.lowercase())
            .map { normalizeToken(it.value) }
            .filter { it.length >= 2 && it !in stopwords }
            .toList()

    private fun normalizeToken(token: String): String {
        val suffix = suffixes.firstOrNull { token.length > it.length + 1 && token.endsWith(it) }
        return if (suffix == null) token else token.dropLast(suffix.length)
    }

    private fun stableIndex(token: String): Int {
        val digest = MessageDigest.getInstance("SHA-1").digest(token.toByteArray(Charsets.UTF_8))
        var value = 0L
        for (i in 0 until 8) {
            value = (value shl 8) or (digest[i].toLong() and 0xff)
        }
        return ((value and Long.MAX_VALUE) % dimensions).toInt()
    }

    private fun cosine(left: DoubleArray, right: DoubleArray): Double =
        left.indices.sumOf { left[it] * right[it] }

    private data class VectorEntry(
        val record: QARecord,
        val vector: DoubleArray,
    )

    private companion object {
        val tokenPattern = Regex("[A-Za-z0-9]+|[가-힣]+")
        val stopwords =
            setOf(
                "그리고",
                "그러나",
                "대한",
                "무엇",
                "어떻게",
                "어떤",
                "언제",
                "있으면",
                "있을",
                "해야",
                "하나요",
                "합니다",
            )
        val suffixes =
            listOf(
                "입니다",
                "합니다",
                "해야",
                "하게",
                "에서",
                "으로",
                "에게",
                "부터",
                "까지",
                "과",
                "와",
                "을",
                "를",
                "이",
                "가",
                "은",
                "는",
                "도",
                "만",
            )
    }
}
