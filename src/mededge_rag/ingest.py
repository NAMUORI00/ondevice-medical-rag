from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .schema import QARecord

Q_TYPE_NAMES = {
    "1": "객관식",
    "2": "단답형",
    "3": "서술형",
}


def load_records(path: str | Path) -> list[QARecord]:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    if input_path.is_dir():
        records: list[QARecord] = []
        for child in sorted(input_path.rglob("*")):
            if child.suffix.lower() in {".json", ".jsonl", ".zip"}:
                records.extend(load_records(child))
        return records

    if input_path.suffix.lower() == ".jsonl":
        return _load_jsonl(input_path)

    if input_path.suffix.lower() == ".zip":
        return _load_zip(input_path)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return list(_records_from_any(payload, source=str(input_path), domain_hint=input_path.parent.name))


def write_records(records: Iterable[QARecord], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def _load_jsonl(path: Path) -> list[QARecord]:
    records: list[QARecord] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                record = QARecord.from_dict(row, fallback_id=f"{path.stem}-{idx}")
                if record:
                    _enrich_record(record, source=str(path), domain_hint=path.parent.name)
                    records.append(record)
    return records


def _load_zip(path: Path) -> list[QARecord]:
    records: list[QARecord] = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if name.lower().endswith(".json")
        )
        for name in names:
            payload = json.loads(archive.read(name).decode("utf-8-sig"))
            zip_record_id = Path(name).stem
            is_root_entry = Path(name).parent.name in {"", "."}
            domain_hint = path.stem if is_root_entry else Path(name).parent.name
            for record in _records_from_any(payload, source=f"{path.name}:{name}", prefix=zip_record_id, domain_hint=domain_hint):
                if is_root_entry and zip_record_id and record.qa_id != zip_record_id:
                    record.metadata["original_qa_id"] = record.qa_id
                    record.qa_id = zip_record_id
                records.append(record)
    return records


def _records_from_any(payload: Any, source: str, prefix: str = "row", domain_hint: str = "") -> Iterable[QARecord]:
    if isinstance(payload, dict):
        record = QARecord.from_dict(payload, fallback_id=prefix)
        if record:
            _enrich_record(record, source=source, domain_hint=domain_hint)
            yield record
            return
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                yield from _records_from_any(value, source=source, prefix=f"{prefix}-{key}", domain_hint=domain_hint)
    elif isinstance(payload, list):
        for idx, item in enumerate(payload, start=1):
            yield from _records_from_any(item, source=source, prefix=f"{prefix}-{idx}", domain_hint=domain_hint)


def _enrich_record(record: QARecord, source: str, domain_hint: str = "") -> None:
    record.source = source
    if domain_hint and record.domain.isdigit():
        record.metadata["domain_code"] = record.domain
        record.domain = domain_hint
    if record.q_type in Q_TYPE_NAMES:
        record.metadata["q_type_code"] = record.q_type
        record.q_type = Q_TYPE_NAMES[record.q_type]
