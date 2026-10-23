# 데이터

## data/raw — 대회 배포 번들 (생성일 '26. 9. 12.)

주최 측이 배포한 8개 파일을 그대로 둔다. 상세 설명은 `data/raw/README.md`(주최 측 원문) 참조.

| 파일 | 행수 | 내용 |
|---|---:|---|
| `stations.csv` | 5 | 지점 메타(지점 ID, 조사지점코드, 수계, 최근접 ASOS 지점) |
| `algae_measure.csv` | 2,939 | 조류경보제 측정자료. 예측 대상 `iem_bgalage_cell_co` 포함. 2012-04 ~ 2026-09 |
| `dam_daily.csv` | 79,964 | 낙동강·금강 다목적댐 15개소 일자료(WAMIS). 2012-01 ~ 2026-09-11 |
| `asos_daily.csv` | 32,208 | ASOS 일자료 6개 지점. 2012-01 ~ 2026-09-11 |
| `dam_operation_api.csv` | 1,128 | 댐 저수량·저수율·전년 비교(보조, '26-06-10 ~ 09-11) |
| `eval_pairs.csv` | 2,754 | 채점 대상 (지점, 기준일, 정답측정일, lag_days, split) |
| `sample_submission.csv` | 124 | 제출 형식 (station_id, base_date, target_date, pred_cells) |

출처·라이선스: 조류경보제 조회서비스(국립환경과학원, 공공저작물 제1유형), 다목적댐 일자료(WAMIS·K-water, 공공누리),
다목적댐 운영정보(K-water), ASOS(기상청). 보고서에 출처를 표기한다.

## data/processed — `python scripts/make_dataset.py` 산출물 (git 제외)

- `bloom.parquet`, `bloom.csv`: (지점, 측정일) 한 행. 조류 항목 + 이전 측정 lag + 기상 7·14·28일 집계(`w_`) + 상류 댐 합산 집계(`d_`) + 정답·분할.
- `split`: train / valid / test / excluded(README: '26년 5~10월 밖) / none(채점 쌍에 없는 측정일).
- test 행의 `target_cells`는 의도적으로 비워 둠(번들에 '26년 실측이 있어 누수 방지).

## 번들 미포함 — DataON 「댐유역 하천 일평균수위」

국가참조표준센터 이용 준수사항 때문에 주최 측이 재배포하지 않음. 필요 시 각자 내려받아 `data/external/`에 두고, **저장소에 올리지 않는다**.
2024년 데이터까지만 수록되어 '25 검증·'26 평가 구간에는 쓸 수 없다.

## data/external — WAMIS 하천 수위·유량 일자료 (`python scripts/fetch_wamis.py`, 2026-10-23 수집본 저장소 포함)

WAMIS OpenAPI(인증키 불필요, 8080 포트)로 낙동강 하천 관측소 12계열(유량 5 + 수위 7)을 받는다.
대상 관측소·녹조 지점 연결은 `configs/wamis_stations.yaml`, 결과 점검표는 `reports/wamis_qc.csv`.

| 녹조 지점 | 유량 | 수위 |
|---|---|---|
| 해평(HP) | 구미대교 | 구미보하, 칠곡보상 |
| 강정·고령(GJGR) | 성주대교 | 강정고령보하, 칠곡보상 |
| 칠서(CS) | 적포교 | 창녕함안보상 |
| 물금·매리(MGMR) | 삼랑진교 (호포대교는 하구 영향으로 참고용) | 삼랑진교 |
| 회남(DCHN) | 기존 대청댐 자료 사용 | |

- `wamis_daily.csv`: `date, kind(wl=수위 m / fw=유량 m³/s), obscd, obsnm, station, bloom_sites, value` long 형식.
- 주의: 칠곡보상 수위 0 값은 오류이므로 제외하고 쓴다. 2026년 값은 실시간 자료라 뒤에 보정될 수 있다.
- 유량(fw)은 API 가 2026년분만 반환해 결합에서 제외한다(수위만 사용). 검증 결과는 `docs/modeling_notes.md`.
- 회사·학교 네트워크에서 8080 포트가 막혀 있으면 다른 네트워크에서 실행한다.
