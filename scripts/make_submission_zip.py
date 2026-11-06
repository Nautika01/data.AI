"""제출용 zip 두 개를 만든다 (접수 양식: 문서자료 zip + 모델자료 zip, 각각 폴더 하나를 압축).

    python scripts/make_submission_zip.py            # dist/model_19mon.zip, dist/docs_19mon.zip
    python scripts/make_submission_zip.py --no-docs  # 모델자료만

모델자료: 저장소 전체에서 아래를 뺀 것 (README 1절의 구성과 같음)
  .git, .github, .venv, __pycache__, 캐시, data/processed·interim(재생성 산출물), reports/slides,
  submission.xls(팀원 채점용 파일), .env, dist
문서자료: docs/ 의 설명서·보고서·기록 + figures/ + data/README.md
demo/ 에 영상 파일(mp4 등)이 없으면 경고만 하고 계속 만든다.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = "data.AI"  # zip 안의 최상위 폴더 이름
EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
    "dist",
    "catboost_info",
    "data.AI.egg-info",
    "src/data_ai.egg-info",
}
EXCLUDE_PATHS = {"data/processed", "data/interim", "reports/slides", "submission.xls", ".env"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".gif"}


def wanted(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts):
        return False
    s = rel.as_posix()
    if any(s == e or s.startswith(e + "/") for e in EXCLUDE_PATHS):
        return False
    if rel.suffix in {".pyc", ".pyo", ".egg-info"}:
        return False
    return True


def add_tree(zf: zipfile.ZipFile, files: list[Path]) -> int:
    total = 0
    for f in files:
        zf.write(f, f"{TOP}/{f.relative_to(ROOT).as_posix()}")
        total += f.stat().st_size
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-docs", action="store_true")
    args = ap.parse_args()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)

    videos = [p for p in (ROOT / "demo").glob("*") if p.suffix.lower() in VIDEO_EXT]
    if not videos:
        print("경고: demo/ 에 영상 파일이 없습니다. 녹화 파일을 demo/ 에 넣고 다시 실행하세요.")

    model_files = sorted(p for p in ROOT.rglob("*") if p.is_file() and wanted(p.relative_to(ROOT)))
    out = dist / "model_19mon.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        size = add_tree(zf, model_files)
    zmb = out.stat().st_size / 1e6
    print(
        f"모델자료: {out} — 파일 {len(model_files)}개, 원본 {size / 1e6:.1f} MB, zip {zmb:.1f} MB"
    )
    must = [
        "README.md",
        "reports/submission.csv",
        "model/lgb_final.joblib",
        "model/train_meta.json",
        "requirements.txt",
        "notebooks/02_pipeline_end_to_end.ipynb",
        "data/raw/algae_measure.csv",
        "data/external/wamis_daily.csv",
    ]
    names = {f.relative_to(ROOT).as_posix() for f in model_files}
    missing = [m for m in must if m not in names]
    print("필수 파일 누락:", missing if missing else "없음")

    if args.no_docs:
        return
    doc_files = [
        ROOT / p
        for p in [
            "docs/method_description.md",
            "docs/ai_usage_report.md",
            "docs/modeling_notes.md",
            "docs/submission_checklist.md",
            "data/README.md",
            "README.md",
        ]
        if (ROOT / p).exists()
    ]
    doc_files += sorted((ROOT / "figures").glob("*.png"))
    doc_files += sorted((ROOT / "docs").glob("*.pdf")) + sorted((ROOT / "docs").glob("*.docx"))
    out = dist / "docs_19mon.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        size = add_tree(zf, doc_files)
    print(f"문서자료: {out} — 파일 {len(doc_files)}개, zip {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
