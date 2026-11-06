# 데모 영상

저장된 학습 모델로 평가 조합 124건을 추론하고, 제출 파일과 비교하는 과정을 녹화한 영상이다.

- 파일: `demo_inference.mp4` (약 2분 30초, 1920×1080)
- 촬영 환경: Windows 11 Pro, Python 3.14.6 (lightgbm 4.7.0, numpy 2.5.3, pandas 3.0.5, scikit-learn 1.9.1)

## 영상 구성

| 구간(약) | 화면 | 보여주는 것 |
|---|---|---|
| 0:00 ~ 0:35 | `dir` | 제출 폴더 구조: `README.md`, `data/`, `model/`, `src/`, `notebooks/`, `scripts/`, `demo/`, `figures/` 등 |
| 0:35 ~ 1:20 | `python --version`, `pip list` | 실행 환경: Python 버전과 주요 라이브러리 버전 |
| 1:20 ~ 1:55 | `dir model`, `Get-Content reports\submission.csv` | 학습된 모델 파일(`lgb_final.joblib`, `train_meta.json`)과 제출 파일 앞부분 |
| 1:55 ~ 2:30 | `python scripts\predict.py` | 저장된 모델로 평가 조합 124건을 추론하고 제출 파일과 비교 |

## 추론 결과 (영상 마지막 장면)

`python scripts\predict.py` 실행 시 아래 순서로 출력된다.

```
모델: lgb_final.joblib, 결측 전략 ffill_flag, 피처 132개
추론: 평가 조합 124건 (기준일 2026-05-04 ~ 2026-09-03)
제출 파일과 비교: 124건 중 불일치 0건
```

이어서 지점별 기준일, 예측 대상일, 기준일 세포수, 경보 단계, 예측 세포수(`pred_cells`)가 표로 나온다. 예측값은 `reports/submission.csv`와 124건 모두 일치한다.

## 직접 실행하려면

프로젝트 폴더에서 가상환경을 켜고 아래 순서로 실행한다. 설치와 환경 구성은 루트의 `README.md`를 따른다.

```powershell
pip install -r requirements.txt
pip install -e .
python scripts\make_dataset.py     # data/raw → data/processed 가공 데이터 생성
python scripts\predict.py          # 저장된 모델로 124건 추론, 제출 파일과 비교
```

모델은 학습 자료(≤2024)만으로 시드 42로 학습했으며, 추론에는 `model/lgb_final.joblib`을 그대로 사용한다.
