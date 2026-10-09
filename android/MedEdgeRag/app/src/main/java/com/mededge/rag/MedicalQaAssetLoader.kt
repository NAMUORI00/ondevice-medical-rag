package com.mededge.rag

import java.io.InputStream
import org.json.JSONObject

object MedicalQaAssetLoader {
    fun load(input: InputStream): List<QARecord> =
        input.bufferedReader(Charsets.UTF_8).useLines { lines ->
            lines
                .map { it.trim() }
                .filter { it.isNotEmpty() }
                .map { parse(JSONObject(it)) }
                .toList()
        }

    private fun parse(json: JSONObject): QARecord =
        QARecord(
            qaId = json.getString("qa_id"),
            domain = json.getString("domain"),
            qType = json.getString("q_type"),
            question = json.getString("question"),
            answer = json.getString("answer"),
            source = json.optString("source", "unknown"),
        )
}
