from __future__ import annotations

import json
import zipfile
from pathlib import Path

from mededge_rag.ingest import load_records


def test_load_records_reads_zip_files_inside_directory_without_02_prefix(tmp_path: Path) -> None:
    zip_path = tmp_path / "TL_내과.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "/필수_9002.json",
            json.dumps(
                {
                    "qa_id": 9002,
                    "domain": 17,
                    "q_type": 1,
                    "question": "테스트용 합성 질문입니다. 무엇을 확인해야 하나요?",
                    "answer": "테스트용 합성 답변입니다.",
                },
                ensure_ascii=False,
            ),
        )

    records = load_records(tmp_path)

    assert len(records) == 1
    assert records[0].qa_id == "필수_9002"
    assert records[0].metadata["original_qa_id"] == "9002"
    assert records[0].domain == "TL_내과"
    assert records[0].q_type == "객관식"
