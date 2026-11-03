# 제출 체크리스트 (마감 11-06, 목표 11-05)

대회가 요구하는 산출물은 세 가지다. 셋 다 저장소에 있다.

| 산출물 | 위치 | 상태 (10-26) |
|---|---|---|
| 학습 모델(재현 코드) | 저장소 전체. `make data && make train` | 확정. 새 clone 재현 확인 완료 |
| 예측 결과 파일 | `reports/submission.csv` (124행) | 확정. 양식 검사 통과 |
| 방법 설명서 | `docs/method_description.md` | 수치 확정. **팀원 이름 기입 남음** |

벤치마크(국립환경과학원 AI 예측정보) 비교는 주최 측 평가 항목이라 우리가 할 일이 아니다.

제출 규격(개발 결과물 제출 안내)에 맞춘 추가 산출물 상태 (11-03):

| 항목 | 위치 | 상태 |
|---|---|---|
| 학습된 모델 파일 | `models/lgb_final.joblib`, `models/train_meta.json` | 저장소 포함. `python scripts/predict.py` 로 추론 재현(제출 파일과 124건 일치) |
| 데이터 | `data/raw/` 번들 8개, `data/external/wamis_daily.csv` | 저장소 포함(공공저작물). DataON 자료는 재배포 금지라 제외 |
| 처음부터 끝까지 실행 노트북 | `notebooks/02_pipeline_end_to_end.ipynb` | 실행 결과 포함(적재→결합→학습→검증→제출→그림) |
| 그림 | `reports/figures/` (EDA 9장 + 모델 5장) | 저장소 포함. `make report` 로 재생성 |
| 데모 영상 | `docs/demo_script.md` 시나리오 | **팀이 화면 녹화해야 함** |
| 버전 고정 파일 | `requirements-lock.txt` | 재현 확인 환경(Python 3.13) 기준 |
| README 규격 재작성 | `README.md` | **제출 안내 규격 확인 후 수정** |
| 5. AI 활용범위 보고서 | 팀 보관 docx | 5.1 빈칸, 5.2 메모, 5.4 "문의" 표현 확인 |
| 키·비밀 점검 | `.env` git 제외, 커밋 이력에 키 없음 | 확인 완료 |

## 남은 일 (순서대로)

1. **팀원 이름·역할 기입** — `docs/method_description.md` 맨 위 `[이름 기입]`. 팀에서 정해서 알려주면 반영.
2. **다른 PC 재현 확인** — 아래 "재현 확인 방법". 한 명이 맡아서 결과를 공유.
3. **설명서 읽기 검토** — 다른 팀원이 처음부터 읽고 이해 안 되는 문장·오탈자 표시.
4. **제출 형식 변환** — 설명서를 접수 양식(PDF 등)으로 변환. 접수 페이지가 요구하는 형식 확인.
5. **저장소 공개 범위 결정** — 비공개로 바꿀 거면 심사위원이 볼 방법(초대 또는 압축 파일 첨부)을 접수 안내에서 확인.
6. **제출** — 11-05. 제출 직후 저장소에 태그를 남긴다(아래).

## 재현 확인 방법 (다른 PC에서)

```bash
git clone https://github.com/Nautika01/data.AI.git
cd data.AI
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell. 실행 정책 오류가 나면: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
pip install -e .
make data                        # make 가 없으면: python scripts/make_dataset.py
make train                       # make 가 없으면: python scripts/train.py
make score                       # 형식 검사 + 자체 채점(참고)
```

끝나면 `reports/submission.csv`가 저장소의 파일과 같은지 본다. 같은 PC가 아니어도 124행 전부 같아야 정상이고, 다른 OS에서는 몇 건이 ±1 cells 정도 다를 수 있다(지표에 영향 없음). 많이 다르면 바로 공유한다.

## 제출 직전 점검 (제출하는 사람이)

- [ ] `git pull` 로 최신 main 인지 확인
- [ ] `reports/submission.csv`: 124행, 열 4개(station_id, base_date, target_date, pred_cells), 정수, 음수 없음 — `make score` 로 확인
- [ ] 설명서 맨 위 팀명·팀원·저장소 주소 기입됨
- [ ] 설명서 수치가 `reports/metrics.csv`와 같음 (검증 2025 rmse_log10 0.704)
- [ ] 실격 사유 셋 다 해당 없음: 하드코딩 없음, 실측 룩업 없음, 기준일 이후 자료 미사용 (`tests/`가 자동 검사)
- [ ] 제출 후 저장소에 태그: `git tag submission-2026-11 && git push origin submission-2026-11`

## 제출 후

- 11-09 ~ 11-13 서류 평가. 결과가 나올 때까지 저장소는 건드리지 않는다(재현성 검증 대비).
- 서류 통과 시에만 11-25 발표 준비를 시작한다.
