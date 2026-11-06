# 댐·하천 유해남조류(녹조) 7일 예측 — 2026 DATA·AI 분석 경진대회 제출물

| 항목 | 내용 |
|---|---|
| 대회 | 2026 DATA·AI 분석 경진대회 문제해결 부문 (KISTI 주관) |
| 과제 | 7. 수질·수문·기상 융합 기반 댐·하천 유해남조류(녹조) 7일 예측 AI 모델 개발 |
| 팀 | 19일의 월요일 (팀원: 홍석민, 임소망, 주효빈, 강민주) |
| 저장소 | https://github.com/Nautika01/data.AI |
| 제출 파일 | `reports/submission.csv` (124행, `sample_submission.csv` 양식) |
| 방법 설명서 | [docs/method_description.md](docs/method_description.md) |
| AI 활용범위 및 검토 과정 | [docs/ai_usage_report.md](docs/ai_usage_report.md) |

문제: 조류경보제 5개 지점(해평, 강정·고령, 칠서, 물금·매리, 회남)에서 기준일로부터 7일 뒤 유해남조류 세포수(cells/mL)를 예측한다. 모델은 LightGBM 회귀(목표 log10(세포수+1))이며, 입력은 기준일 포함 과거 자료만 쓴다.

## 1. 결과물 구성

```
.
├── README.md                 # 이 파일: 구성, 데이터·모델, 실행 방법, 실행환경
├── data/
│   ├── raw/                  # 대회 배포 번들 8개 (수정 없음) + 주최 측 README
│   ├── external/             # 팀 수집 외부 자료: wamis_daily.csv (WAMIS 하천 수위)
│   ├── processed/            # make data 산출물 bloom.parquet (git 제외, 재생성)
│   └── README.md             # 데이터 출처·라이선스·열 설명
├── model/
│   ├── lgb_final.joblib      # 학습된 최종 모델 (LightGBM Booster)
│   └── train_meta.json       # 결측 전략, 반복 수, 입력 피처 132개 목록
├── src/data_ai/              # 소스코드 패키지
│   ├── bloom.py              #   데이터 결합 (기상·댐·하천·상류 지점 피처, 정답·분할 규칙)
│   ├── features.py           #   입력 허용 목록, 결측 대체 전략 3안
│   ├── models.py             #   LightGBM 학습·예측·저장·중요도
│   ├── evaluate.py           #   지표 (log10 RMSE·MAE, R², NSE, F1@10,000)
│   ├── config.py, utils.py, viz.py, data.py
├── notebooks/
│   ├── 02_pipeline_end_to_end.ipynb   # 적재→전처리→학습→롤링 검증→추론→시각화→SHAP (실행 결과 포함)
│   ├── 01_eda_bloom.ipynb             # 탐색적 분석
│   └── 00_code_guide.ipynb            # 코드 구조 안내
├── scripts/
│   ├── make_dataset.py       # 데이터 결합 → data/processed/bloom.parquet
│   ├── train.py              # 결측 전략 비교 → 롤링 검증 → 최종 학습 → submission.csv, model/
│   ├── predict.py            # 저장된 모델로 평가 조합 추론 (데모용)
│   ├── evaluate.py, score_submission.py, make_figures.py
│   ├── experiments*.py       # 변형 실험 (기록용, 제출 모델과 무관)
│   └── fetch_wamis.py, fetch_data_go_kr.py   # 외부 자료 수집 (실행에 불필요)
├── demo/                     # 데모영상 + 녹화 시나리오 (README.md)
├── figures/                  # 그림 16장 (EDA 9, 모델 결과 5, SHAP 2)
├── reports/                  # submission.csv, metrics.csv, 실험 결과 csv
├── docs/                     # 방법 설명서, 모델링 기록, AI 활용 보고서, 제출 체크리스트
├── configs/bloom.yaml        # 열 이름 매핑, 집계 창, 지점-댐·관측소 대응
├── tests/                    # 단위 테스트 27개 (미래 정보 차단, 정답 열 누수 차단 등)
├── requirements.txt          # 정확한 버전 고정 (pip freeze 상당)
├── requirements-min.txt      # 버전 범위만 적은 개발용 목록
├── pyproject.toml, Makefile
```

## 2. 데이터

최종 모델에 들어가는 자료 4종. 모두 저장소에 포함돼 있어 별도 다운로드가 필요 없다.

| 자료 | 파일 | 출처·이용조건 | 기간 | 사용 |
|---|---|---|---|---|
| 조류경보제 측정자료 | `data/raw/algae_measure.csv` | 국립환경과학원 물환경정보시스템, 공공저작물 제1유형 (대회 배포) | 2012.04~2026.09, 2,939행 | 예측 대상(세포수), 수질 항목, 이전 측정값, 같은 수계 상류 지점 세포수 |
| 기상 ASOS 일자료 | `data/raw/asos_daily.csv` | 기상청 (대회 배포) | 2012.01~2026.09, 6개 관측소 | 지점별 최근접 관측소, 과거 7·14·28일 집계 |
| 다목적댐 일자료 | `data/raw/dam_daily.csv` | K-water WAMIS, 공공누리 (대회 배포) | 2012.01~2026.09, 15개 댐 | 지점별 상류 댐 합산 유입·방류·강우, 대표 댐 저수위 |
| 하천 수위 | `data/external/wamis_daily.csv` | K-water WAMIS OpenAPI, 공공누리 (팀 수집, `scripts/fetch_wamis.py`) | 2016.01~2026.10 | 낙동강 본류 보 4곳 수위 |

번들의 나머지 파일(`stations.csv`, `eval_pairs.csv`, `sample_submission.csv`, `dam_operation_api.csv`)은 지점 대응·채점 쌍·제출 양식에 쓰거나(앞 셋) 학습 구간이 없어 미사용(`dam_operation_api.csv`).

검토했으나 제출 모델에 쓰지 않은 외부 자료: DataON 「댐유역 하천 일평균수위」(재배포 금지 조건이라 저장소 미포함, 2024년까지만 수록), 다목적댐 운영자료(저수량), 국립환경과학원 수질자동측정망. 검증 결과는 [docs/modeling_notes.md](docs/modeling_notes.md). 지점·관측소·댐 대응의 세부는 [data/README.md](data/README.md)와 `configs/bloom.yaml`.

## 3. 모델

- LightGBM 회귀, 목표 log10(세포수+1), L2 손실, `extra_trees` 사용, 시드 42. 5개 지점 통합 모델.
- 입력 132열: 조류 항목(기준일·이전 1~3회·속별 비율), 기상·댐 과거 7·14·28일 집계, 하천 수위, 같은 수계 상류 지점의 최근 세포수, 월·연중일, 지점.
- 결측 대체: 세 전략(기본 처리 / 직전값+결측 표시 / 지점·월 중앙값+결측 표시)을 검증에서 비교해 자동 선택. 현재 선택: 직전값+결측 표시(ffill_flag).
- 반복 수 146(공식 검증 early stopping). 최종 모델은 대회 Q&A ⑤에 따라 학습 자료(split=train, ≤2024, 2,310행)만으로 학습하며, 2025년 검증 자료는 전략·반복 수 결정에만 쓴다.

| 구간 | n | rmse_log10 | mae_log10 | R²(피어슨 제곱) | NSE | F1@10,000 |
|---|---|---|---|---|---|---|
| 공식 검증 2025 (학습 ≤2024) | 256 | 0.704 | 0.527 | 0.202 | 0.173 | 0.651 |
| 롤링 2022 (학습 ≤2021) | 271 | 0.832 | 0.631 | 0.318 | 0.014 | 0.429 |
| 롤링 2023 (학습 ≤2022) | 248 | 0.763 | 0.574 | 0.046 | 0.027 | 0.375 |

R²는 운영사무국 답변에 따라 관측·예측의 피어슨 상관계수 제곱(원 단위), NSE는 1−SSE/SST. `reports/metrics.csv`의 `r2_pearson`·`nse` 열이다(`r2` 열은 1−SSE/SST라 NSE와 같다). 기준선(검증 2025): 기준일 값 유지(persistence) rmse_log10 0.883. 과제 목표 R² 0.6·NSE 0.5에는 못 미치며 원인과 시도 내역은 방법 설명서 5~7절에 있다.

## 4. 실행환경

GPU를 쓰지 않는다(CUDA·NVIDIA Driver 불필요). 외부 AI 서비스·API도 실행에 필요 없다.

| 항목 | 재현 확인 환경 | 비고 |
|---|---|---|
| 운영체제 | Ubuntu 24.04.5 LTS (x86_64) | Windows 10/11, macOS에서도 동작 (팀원 PC Windows에서 학습·수집 수행) |
| Python | 3.13.16 | 3.10 이상이면 동작. CI는 3.11 |
| numpy / pandas / scipy | 2.5.3 / 3.0.5 / 1.18.1 | |
| scikit-learn / lightgbm | 1.9.1 / 4.7.0 | 모델 |
| pyarrow | 26.0.0 | parquet 입출력 |
| shap | 0.54.1 | 해석(노트북 7절, SHAP 그림) |
| matplotlib / seaborn | 3.11.2 / 0.13.2 | 그림 |
| joblib / PyYAML / requests / python-dotenv | 1.6.0 / 6.0.1 / 2.34.2 / 1.2.3 | |
| nbconvert / ipykernel | 7.17.2 / 7.4.0 | 노트북 실행 |
| pytest / ruff | 9.1.1 / 0.17.1 | 테스트·린트 |
| 메모리·시간 | 2GB 미만, `make data` 약 20초 + `make train` 약 1분 (CPU 4코어 기준) | |

전체 목록은 `requirements.txt`(84개 패키지, 정확한 버전). 소스 설치는 `pip install -e .`(pyproject.toml).

## 5. 환경 구성 및 실행 방법

```bash
git clone https://github.com/Nautika01/data.AI.git
cd data.AI
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\activate
pip install -r requirements.txt      # 정확한 버전
pip install -e .                     # src/data_ai 패키지

make data        # data/raw + data/external → data/processed/bloom.parquet  (python scripts/make_dataset.py)
make train       # 결측 전략 비교 → 롤링 검증 → 최종 학습 → reports/submission.csv, model/  (python scripts/train.py)
make evaluate    # 검증 지표 표                      (python scripts/evaluate.py)
make predict     # 저장된 model/ 로 평가 조합 추론, submission.csv 와 비교  (python scripts/predict.py)
make score       # 제출 파일 형식 검사               (python scripts/score_submission.py reports/submission.csv)
make report      # figures/ 그림 재생성               (python scripts/make_figures.py)
make test        # 단위 테스트 27개
```

`make`가 없는 환경(Windows 기본)에서는 괄호 안의 `python scripts/...` 명령을 그대로 쓴다. Windows PowerShell에서 가상환경 활성화가 막히면 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`를 먼저 실행한다.

노트북으로 보려면 `jupyter lab notebooks/02_pipeline_end_to_end.ipynb`. 실행 결과가 저장돼 있어 열어서 읽기만 해도 되고, "Run All"로 약 3분이면 처음부터 다시 실행된다.

재현 확인(2026-11-05, Q&A ⑤ 반영 후 Linux): `make train` 재실행 결과와 저장된 `model/lgb_final.joblib` 추론(`make predict`)이 `reports/submission.csv`와 124행 모두 동일했다. 다른 OS에서는 부동소수 차이로 몇 건이 ±1 cells 달라질 수 있다.

재현 확인(Windows 11 Pro, Python 3.14.6, 2026-11-05): 새 clone 후 README 5절 순서대로 실행하여 `reports/submission.csv`가 저장소 파일과 124행 모두 일치함을 확인했고, Q&A ⑤ 반영 후 교체된 제출 파일도 `git pull` 뒤 `predict.py`가 "불일치 0건"을 출력함. 단, `pyyaml==6.0.1`이 Python 3.14에서 설치되지 않아 6.0.3으로 대체했고, 재학습 시 `metrics.csv` 등은 부동소수점 끝자리 수준으로 달라짐.

## 6. 학습·평가·추론 흐름

1. **데이터 결합** (`make data`): 조류 측정(지점, 측정일)을 기준 행으로, 기상·댐·하천 일자료를 기준일 포함 과거 창으로 집계해 붙인다(`merge_asof backward`). 같은 수계 상류 지점의 기준일 이전 최근 세포수를 붙인다. 정답은 주최 측 `eval_pairs.csv`를 그대로 쓴다. 2026 평가 행의 정답 열은 비워 둔다.
2. **학습·검증** (`make train`): 학습 ≤2024 / 검증 2025로 결측 전략 3안을 비교해 선택하고, 롤링 검증(2022·2023·2025)으로 안정성을 확인한 뒤 ≤2025 전체로 최종 학습한다. 입력 열은 허용 목록으로만 고르며 정답·날짜 열이 섞이면 실행이 중단된다(`tests/`).
3. **추론** (`make predict`): 저장된 모델과 `train_meta.json`의 피처 목록으로 2026년 5~10월 평가 조합 124건을 예측하고 제출 파일과 대조한다.
4. **평가·시각화** (`make evaluate`, `make report`, 노트북): 지표 표, 피처 중요도, 실측 대 예측 산점도·시계열, SHAP.

## 7. 문서

| 문서 | 내용 |
|---|---|
| [docs/method_description.md](docs/method_description.md) | 방법 설명서 (제출용): 과제 이해, 데이터 결합, 결측 전략, 모델, 검증, 해석, 한계, 재현 |
| [docs/modeling_notes.md](docs/modeling_notes.md) | 모델링 기록: 실험 4차·외부 자료 5종 검증 표, 누수 사고 교훈, 모델 확정 |
| [docs/ai_usage_report.md](docs/ai_usage_report.md) | AI 활용범위 및 주요 검토 과정 (제출 규격 5번) |
| [docs/submission_checklist.md](docs/submission_checklist.md) | 제출 전 점검 목록 |
| [demo/README.md](demo/README.md) | 데모영상 녹화 시나리오 |
| [data/README.md](data/README.md) | 데이터 출처·라이선스·열 설명 |

## 8. 외부 자료 이용조건과 민감정보

- 외부 자료는 WAMIS 하천 수위(K-water, 공공누리)만 저장소에 포함했다. DataON 자료는 재배포 금지 조건을 따라 포함하지 않았고 제출 모델에도 쓰지 않았다.
- 외부 코드·사전학습 모델은 쓰지 않았다. 라이브러리는 모두 오픈소스(MIT·BSD·Apache)다.
- API 키·비밀번호·개인정보는 저장소와 커밋 이력에 없다(`.env`는 git 제외, 이력 전체 검색으로 확인). 실행에 인증정보가 필요하지 않다.
