# data.AI — 2026 DATA·AI 분석 경진대회

> **데이터와 AI 기반의 사회·과학 문제 해결로 국내 연구데이터 생태계 저변을 확대**

한국과학기술정보연구원(KISTI)이 주관하는 **2026 DATA·AI 분석 경진대회** 문제해결 부문 참가를 위한 작업 저장소입니다.
데이터 수집·전처리, 탐색적 분석(EDA), 모델링, 평가, 보고서·발표자료 작성을 하나의 재현 가능한 파이프라인으로 관리합니다.

## 대회 개요

| 항목 | 내용 |
|---|---|
| 대회명 | 2026 DATA·AI 분석 경진대회 (제7회) |
| 주관 | 한국과학기술정보연구원(KISTI) |
| 공동 주최 | 국가과학기술연구회(NST), 국회도서관, 대전광역시, 해양경찰청, 한국수자원공사, 대전 중구청 |
| 부문 | 문제발굴 부문 / **문제해결 부문** |
| 참가 자격 | 데이터 분석·활용에 관심 있는 개인 또는 **4인 이하 팀** |
| 접수 마감 | **2026-11-06 (문제해결 부문)** |
| 서류 평가 | 2026-11-09 ~ 11-13 |
| 최종 발표평가·시상식 | 2026-11-25, KISTI 대전본원 키움관 |
| 가점 | 서로 다른 분야의 데이터를 **융합**한 해결안 |
| 신청 | [DataON 경진대회](https://dataon.kisti.re.kr/) · [AIDA](https://aida.kisti.re.kr/competition/main/overview.do) |

자세한 내용은 [docs/competition.md](docs/competition.md)를 참고하세요. 일정과 규정은 공식 공고가 우선합니다.

## 문제해결 부문 과제 (7개)

| # | 과제 | 분야 |
|---|---|---|
| 1 | 한국어 웹 대체텍스트(alt text) 품질 판정 AI 모델 | NLP / 웹 접근성 |
| 2 | 전북 고속도로 결빙 위험도 분석 | 기상 · 도로환경 |
| 3 | 하수 감시 데이터 기반 감염병 유행 조기예측 | 보건 · 환경 |
| 4 | 호우 시 6시간 최대 하천수위 상승량 예측 | 수자원 · 기상 |
| 5 | 광역 지방의회 회의록 기반 지방정책 이슈 트렌드 분석 및 흐름 예측 | NLP / 정책 |
| 6 | 어선 사고예방을 위한 항적데이터 분석 | 해양 · 시공간 |
| 7 | 댐·하천 유해남조류(녹조) 7일 예측 AI 모델 개발 | 수질 · 시계열 |

과제별 비교와 선택 기준은 [docs/task_candidates.md](docs/task_candidates.md)에 정리합니다.

## 저장소 구조

```
.
├── data/                # 데이터 (git 추적 제외, .gitkeep만 유지)
│   ├── raw/             # 원본 데이터 (수정 금지)
│   ├── external/        # 외부·융합 데이터 (기상, 인구, 지리 등)
│   ├── interim/         # 중간 산출물
│   └── processed/       # 모델 입력용 최종 데이터
├── notebooks/           # EDA·실험 노트북 (번호-주제 명명: 01_eda_xxx.ipynb)
├── src/data_ai/         # 재사용 가능한 파이썬 패키지
│   ├── config.py        # 경로·시드 등 공통 설정
│   ├── data.py          # 데이터 로딩·저장
│   ├── features.py      # 피처 엔지니어링
│   ├── models.py        # 학습·추론
│   ├── evaluate.py      # 평가 지표
│   └── utils.py         # 로깅·시드 고정 등
├── scripts/             # 파이프라인 실행 스크립트
├── reports/             # 보고서·발표자료·그림
├── docs/                # 대회 안내, 과제 후보, 해결안 양식
├── tests/               # 단위 테스트
├── requirements.txt
├── Makefile
└── README.md
```

## 시작하기

```bash
# 1. 가상환경 생성 및 의존성 설치
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# 2. 환경 변수
cp .env.example .env             # 필요 시 API 키 등 입력

# 3. 파이프라인 실행
make data        # 원본 → processed
make train       # 모델 학습
make evaluate    # 평가 지표 산출
make report      # 보고서용 그림 생성

# 4. 노트북
jupyter lab
```

## 작업 원칙

- **재현성**: 모든 결과는 `scripts/`로 재현 가능해야 하며, 난수 시드는 `src/data_ai/config.py`에서 고정합니다.
- **데이터 관리**: `data/` 아래 실제 데이터는 git에 올리지 않습니다. 출처·라이선스·수집 일자는 `data/README.md`에 기록합니다.
- **융합 데이터**: 가점 요건이므로, 과제 데이터와 결합할 외부 데이터(기상, 인구, 지리, 교통 등)를 `data/external/`에 두고 출처를 명시합니다.
- **노트북 → 코드**: 노트북에서 검증된 로직은 `src/data_ai/`로 옮겨 테스트합니다.
- **문서화**: 제출용 해결안은 [docs/proposal_template.md](docs/proposal_template.md) 양식을 따릅니다.

## 일정 체크리스트

- [ ] 과제 선정 및 팀 역할 분담
- [ ] 과제 데이터 다운로드·메타데이터 정리 (`data/README.md`)
- [ ] 융합 외부 데이터 확보
- [ ] EDA 및 베이스라인 모델
- [ ] 모델 고도화 및 평가
- [ ] 해결안 보고서 작성 (`reports/`)
- [ ] **11-06 접수**
- [ ] 발표자료 준비 (**11-25 발표평가**)

## 참고 자료

- [DataON 국가연구데이터플랫폼](https://dataon.kisti.re.kr/)
- [AIDA — 2026 DATA·AI 분석 경진대회 안내](https://aida.kisti.re.kr/competition/main/overview.do)
- [헤럴드경제 — KISTI, 'DATA·AI'로 사회과학 문제 해결한다](https://biz.heraldcorp.com/article/10837054)
- [충청뉴스 — 2026 DATA·AI 분석 경진대회 문제해결 부문 공모](http://www.ccnnews.co.kr/news/articleView.html?idxno=415045)
