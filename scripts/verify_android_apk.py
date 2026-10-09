from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APK = ROOT / "android" / "MedEdgeRag" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
FORBIDDEN_SUFFIXES = (".task", ".litertlm", ".safetensors", ".gguf")
FORBIDDEN_FILENAMES = ("model.bin", "pytorch_model.bin")
FORBIDDEN_PARTS = ("data/raw/", ".env", "aihub")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the MedEdge Android APK is on-device safe.")
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK)
    parser.add_argument("--aapt", type=Path, default=None)
    parser.add_argument("--allow-internet", action="store_true")
    parser.add_argument("--require-internet", action="store_true")
    args = parser.parse_args()

    apk = args.apk.resolve()
    if not apk.is_file():
        raise SystemExit(f"APK not found: {apk}")

    verify_zip_contents(apk)
    verify_permissions(apk, args.aapt, allow_internet=args.allow_internet, require_internet=args.require_internet)
    print(f"Android APK verification passed: {apk}")
    return 0


def verify_zip_contents(apk: Path) -> None:
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()

    required = [
        "assets/medical_qa_sample.jsonl",
        "lib/arm64-v8a/libLiteRt.so",
        "lib/arm64-v8a/liblitertlm_jni.so",
        "lib/x86_64/libLiteRt.so",
        "lib/x86_64/liblitertlm_jni.so",
    ]
    missing = [name for name in required if name not in names]
    if missing:
        raise SystemExit(f"APK is missing required on-device runtime assets: {missing}")

    forbidden = [
        name
        for name in names
        if name.lower().endswith(FORBIDDEN_SUFFIXES)
        or name.lower().replace("\\", "/").split("/")[-1] in FORBIDDEN_FILENAMES
        or any(part in name.lower().replace("\\", "/") for part in FORBIDDEN_PARTS)
    ]
    if forbidden:
        raise SystemExit(f"APK bundles forbidden private/model artifacts: {forbidden[:10]}")


def verify_permissions(
    apk: Path,
    explicit_aapt: Path | None,
    allow_internet: bool,
    require_internet: bool,
) -> None:
    aapt = find_aapt(explicit_aapt)
    result = subprocess.run(
        [str(aapt), "dump", "permissions", str(apk)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "Failed to inspect APK permissions with aapt.")
    has_internet = "android.permission.INTERNET" in result.stdout
    if has_internet and not allow_internet:
        raise SystemExit("Built APK declares INTERNET permission.")
    if require_internet and not has_internet:
        raise SystemExit("Built APK does not declare INTERNET permission.")


def find_aapt(explicit_aapt: Path | None) -> Path:
    if explicit_aapt is not None:
        candidate = explicit_aapt.resolve()
        if candidate.is_file():
            return candidate
        raise SystemExit(f"aapt not found: {candidate}")

    roots = [
        os.environ.get("ANDROID_HOME"),
        os.environ.get("ANDROID_SDK_ROOT"),
        r"C:\Program Files (x86)\Android\android-sdk",
    ]
    for root in roots:
        if not root:
            continue
        build_tools = Path(root) / "build-tools"
        if not build_tools.is_dir():
            continue
        candidates = sorted(build_tools.rglob("aapt.exe"), reverse=True)
        if candidates:
            return candidates[0]

    raise SystemExit("aapt.exe was not found. Set ANDROID_HOME or pass --aapt.")


if __name__ == "__main__":
    sys.exit(main())
