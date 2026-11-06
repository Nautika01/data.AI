# demo/ — 추론 과정 데모 영상

`demo_inference.mp4` (1280×720, 약 51초): 터미널(bash)에서 아래 순서로 명령을 붙여넣어 실행하는 과정을 그대로 화면 녹화한 영상이다. 출력은 실행 시점(2026-11-06, Ubuntu 24.04 / Python 3.13)에 프로그램이 실제로 낸 것이다.
`ls model`(학습된 모델 파일) → `head -n 5 reports/submission.csv`(제출 파일 앞부분) → `python scripts/predict.py`(저장된 모델로 124건 추론, 제출 파일과 불일치 0건) → `python scripts/score_submission.py reports/submission.csv`(형식 검사) → `ls figures` → 결과 그림 2장.
아래는 같은 내용을 직접 녹화할 때의 시나리오다.

# 데모 영상 시나리오 (추론 과정, 약 3분)

화면 녹화 도구(Windows: Win+G 또는 OBS)로 터미널 화면을 녹화한다. 말로 설명하지 않아도 되며, 아래 순서대로 명령을 치고 결과가 나오는 것을 보여 주면 된다. 녹화 전에 `git pull` 로 최신 main 상태인지 확인한다.

| 순서 | 보여줄 것 | 명령 | 화면에 나와야 하는 것 |
|---|---|---|---|
| 1 | 저장소 구조 (10초) | `dir` 또는 `ls` | data/, model/, src/, scripts/, notebooks/, figures/, demo/ 폴더 |
| 2 | 입력 데이터 결합 (30초) | `python scripts/make_dataset.py` | "기상 결합", "댐 결합", "하천 결합", "상류 지점 결합" 로그와 최종 2,939행 × 134열 |
| 3 | 저장된 모델로 추론 (30초) | `python scripts/predict.py --station HP` | 모델·전략·피처 수, 평가 조합 124건, "제출 파일과 비교: 불일치 0건", 해평 지점 예측 표 |
| 4 | 제출 파일 확인 (20초) | `python scripts/score_submission.py reports/submission.csv` | 124행 형식 검사 통과, 지점별 참고 점수 표 |
| 5 | 검증 지표 (20초) | `python scripts/evaluate.py` | 결측 전략 비교표, 롤링 검증표, 피처 중요도 상위 15 |
| 6 | 그림 (20초) | `figures/` 폴더를 열어 `fig_valid2025_scatter.png`, `fig_submission_2026.png` 표시 | 실측 vs 예측 산점도, 2026 예측 시계열 |

선택: 처음부터 학습까지 보여 주려면 3번 앞에 `python scripts/train.py`(약 1분)를 넣는다. 끝나면 `reports/submission.csv`가 다시 만들어지고 내용은 같다.

## 자주 생기는 문제

- `make` 명령이 없으면 위 표처럼 `python scripts/...` 로 직접 실행한다.
- `ModuleNotFoundError: data_ai` → `pip install -e .` 를 먼저 실행한다.
- 한글 폰트가 없으면 그림의 한글이 네모로 나온다. 그림은 저장소에 있는 png 를 그대로 보여 주면 된다.
