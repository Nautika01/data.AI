# demo/ — 추론 과정 데모 영상

`demo_inference.mp4` (1280×720, 약 66초): 아래 "녹화 시나리오"를 Linux(Ubuntu 24.04, bash, Python 3.13)에서 그대로 따라 실행하며 화면 녹화한 영상이다. 저장소를 새로 clone 한 폴더(`~/work/data.AI-check`)에서 가상환경을 켜고 `ls model` → `head -n 5 reports/submission.csv` → `python scripts/predict.py` 순으로 한 줄씩 입력했다. 출력은 프로그램이 실제로 낸 것이며, 마지막에 "124건 중 불일치 0건" 줄이 보이는 상태로 멈춘다. Windows 에서는 아래 PowerShell 명령이 같은 역할을 한다.

## 녹화 시나리오 (1~2분)

새로 clone 한 폴더에서 `python scripts/make_dataset.py`를 한 번 실행해 둔 뒤(처리 결과 `data/processed/`는 저장소에 없음) 명령을 한 줄씩 천천히 입력한다.

| 순서 | Windows PowerShell | Linux/macOS bash | 보여줄 것 |
|---|---|---|---|
| 1 | `cd $HOME\work\data.AI-check` | `cd ~/work/data.AI-check` | 저장소 폴더로 이동 |
| 2 | `.venv\Scripts\activate` | `source .venv/bin/activate` | 프롬프트에 `(.venv)` |
| 3 | `cls` | `clear` | 화면 정리 |
| 4 | `dir model` | `ls model` | 학습된 모델 파일 `lgb_final.joblib` |
| 5 | `Get-Content reports\submission.csv -TotalCount 5` | `head -n 5 reports/submission.csv` | 제출 예측값 파일 앞부분 |
| 6 | `python scripts/predict.py` | 같음 | 핵심 장면. 124건 추론, "124건 중 불일치 0건" 줄이 나오면 3~4초 멈춤 |

## 자주 생기는 문제

- `make` 명령이 없으면 위 표처럼 `python scripts/...` 로 직접 실행한다.
- `ModuleNotFoundError: data_ai` → `pip install -e .` 를 먼저 실행한다.
- 한글 폰트가 없으면 그림의 한글이 네모로 나온다. 그림은 저장소에 있는 png 를 그대로 보여 주면 된다.
