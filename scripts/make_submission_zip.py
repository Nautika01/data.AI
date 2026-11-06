"""제출용 zip 두 개를 만든다 (접수 양식: 문서자료 zip + 모델자료 zip, 각각 폴더 하나를 압축).

    python scripts/make_submission_zip.py            # dist/model_19mon.zip, dist/docs_19mon.zip
    python scripts/make_submission_zip.py --no-docs  # 모델자료만

모델자료: **git 이 추적하는 파일만**(= GitHub 저장소 내용) + demo/ 의 영상 파일.
  로컬에만 있는 재배포 금지 자료(DataON parquet 등), 가상환경, 캐시,
  data/processed 는 자동으로 빠진다.
  추적 파일 중 reports/slides, submission.xls(팀원 채점용), .github 은 뺀다.
문서자료: docs/ 의 설명서·보고서·기록 + figures/ + data/README.md
  (+ docs/ 의 pdf·docx 가 있으면 포함)
demo/ 에 영상 파일(mp4 등)이 없으면 경고만 하고 계속 만든다.
"""

from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = "data.AI"  # zip 안의 최상위 폴더 이름
EXCLUDE_PATHS = ("reports/slides", "submission.xls", ".github")
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".gif"}
MUST_HAVE = [
    "README.md",
    "reports/submission.csv",
    "model/lgb_final.joblib",
    "model/train_meta.json",
    "requirements.txt",
    "notebooks/02_pipeline_end_to_end.ipynb",
    "data/raw/algae_measure.csv",
    "data/external/wamis_daily.csv",
]
DOC_FILES = [
    "docs/method_description.md",
    "docs/ai_usage_report.md",
    "docs/modeling_notes.md",
    "docs/submission_checklist.md",
    "data/README.md",
    "README.md",
]


def tracked_files() -> list[Path]:
    """git 이 추적하는 파일 목록 (저장소에 올라간 것과 같음)."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    return [ROOT / f for f in out.stdout.decode("utf-8").split("\0") if f]


def wanted(rel: Path) -> bool:
    s = rel.as_posix()
    return not any(s == e or s.startswith(e + "/") for e in EXCLUDE_PATHS)


def write_zip(out: Path, files: list[Path]) -> tuple[int, int]:
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f"{TOP}/{f.relative_to(ROOT).as_posix()}")
            total += f.stat().st_size
    return total, out.stat().st_size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-docs", action="store_true")
    args = ap.parse_args()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)

    videos = [p for p in (ROOT / "demo").glob("*") if p.suffix.lower() in VIDEO_EXT]
    if not videos:
        print("경고: demo/ 에 영상 파일이 없습니다. 녹화 파일을 demo/ 에 넣고 다시 실행하세요.")

    model_files = sorted(p for p in tracked_files() if p.is_file() and wanted(p.relative_to(ROOT)))
    model_files += [v for v in videos if v not in model_files]
    out = dist / "model_19mon.zip"
    raw, zipped = write_zip(out, model_files)
    mb = f"원본 {raw / 1e6:.1f} MB, zip {zipped / 1e6:.1f} MB"
    print(f"모델자료: {out} — 파일 {len(model_files)}개, {mb}")
    names = {f.relative_to(ROOT).as_posix() for f in model_files}
    missing = [m for m in MUST_HAVE if m not in names]
    print("필수 파일 누락:", missing if missing else "없음")
    print("영상 포함:", [v.name for v in videos] if videos else "없음")

    if args.no_docs:
        return
    doc_files = [ROOT / p for p in DOC_FILES if (ROOT / p).exists()]
    doc_files += sorted((ROOT / "figures").glob("*.png"))
    doc_files += sorted((ROOT / "docs").glob("*.pdf")) + sorted((ROOT / "docs").glob("*.docx"))
    out = dist / "docs_19mon.zip"
    raw, zipped = write_zip(out, doc_files)
    print(f"문서자료: {out} — 파일 {len(doc_files)}개, zip {zipped / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
