const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/root/.claude/skills/synced/410a83fa-f57a-4702-8d9e-3e515921ddac_e2529432-337c-47ef-b82a-2b87e2933d9b/pptx/scripts/apply_theme.js");

const THEME = {
  name: "Bloom", headFontFace: "Malgun Gothic", bodyFontFace: "Malgun Gothic",
  colors: { dk1: "0E2A2F", lt1: "FFFFFF", dk2: "1C7293", lt2: "EEF4F5",
            accent1: "1C7293", accent2: "5E9E3A", accent3: "EB6834", accent4: "D03B3B", accent5: "898781", accent6: "CADCFC",
            hlink: "1C7293", folHlink: "5E9E3A" },
};
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";            // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const FIG = "/home/user/data.AI/reports/figures/";

// ---- layouts ----
pres.defineSlideMaster({
  title: "DARK", background: { color: THEME.colors.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.7, w: 8.8, h: 1.3, fontSize: 36, bold: true, color: C.background1, margin: 0, align: "left" } } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.1, w: 8.8, h: 1.5, fontSize: 16, color: C.accent6, margin: 0 } } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: THEME.colors.lt1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.35, w: 9.0, h: 0.7, fontSize: 24, bold: true, color: C.text1, margin: 0 } } },
    { text: { text: "2026 DATA·AI 분석 경진대회 · 녹조 7일 예측", options: { x: 0.5, y: 5.2, w: 6, h: 0.3, fontSize: 9, color: C.accent5, margin: 0, isTextBox: true } } },
  ],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 9, color: THEME.colors.accent5 },
});

const card = (slide, x, y, w, h, head, lines, fill = C.background2) => {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: "card " + head });
  slide.addText(head, { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: 0.35, fontSize: 14, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  slide.addText(lines.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < lines.length - 1 } })),
    { x: x + 0.15, y: y + 0.5, w: w - 0.3, h: h - 0.6, fontSize: 11.5, color: C.text1, margin: 0, isTextBox: true, paraSpaceAfter: 4, valign: "top" });
};
const stat = (slide, x, y, w, value, label, color = C.accent1) => {
  slide.addText(value, { x, y, w, h: 0.75, fontSize: 34, bold: true, color, align: "center", margin: 0, isTextBox: true });
  slide.addText(label, { x, y: y + 0.75, w, h: 0.4, fontSize: 11, color: C.accent5, align: "center", margin: 0, isTextBox: true });
};
const chartStyle = (title) => ({
  showTitle: true, title, titleFontSize: 12, titleColor: THEME.colors.dk1, titleFontFace: "+mn-lt",
  showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", dataLabelFontSize: 10, dataLabelFontFace: "+mn-lt", dataLabelColor: THEME.colors.dk1,
  catAxisLabelFontSize: 10, valAxisLabelFontSize: 9, catAxisLabelColor: THEME.colors.dk1, valAxisLabelColor: THEME.colors.accent5,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  valGridLine: { color: "E1E0D9", size: 0.5 }, catGridLine: { style: "none" },
});

// 1. Title
pres.addSection({ title: "도입" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "도입" });
s.addText("수질·수문·기상 융합 기반\n유해남조류 7일 예측 모델", { placeholder: "title" });
s.addText("2026 DATA·AI 분석 경진대회 문제해결 부문 · 과제 7\n팀명: (기입)  ·  팀원: (기입)  ·  2026. 11.", { placeholder: "body" });
s.addNotes("발표 2분 안에 문제·접근·결과 한 줄씩 말하고 들어간다.");

// 2. 문제 정의
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "도입" });
s.addText("무엇을 맞히는가: 기준일 +7일 유해남조류 세포수", { placeholder: "title" });
stat(s, 0.5, 1.3, 2.1, "5", "경보제 지점 (낙동강 4, 대청호 1)");
stat(s, 2.7, 1.3, 2.1, "7일", "선행 예측 (정답 ±3일 최근접 측정)");
stat(s, 4.9, 1.3, 2.1, "124", "'26년 5~10월 평가 조합", C.accent3);
stat(s, 7.1, 1.3, 2.3, "log10", "RMSE·MAE + 원 단위 R²·NSE");
card(s, 0.5, 2.8, 4.4, 2.2, "채점 규칙 (주최 측 eval_pairs.csv)", [
  "기준일은 실측이 있는 날, 정답은 +7일에 가장 가까운 측정(±3일)",
  "학습 ~'24 (2,310) / 검증 '25 (256) / 평가 '26 5~10월 (124)",
  "기준일 이후 관측값 사용 금지 · 하드코딩·룩업 금지 · 재현 불일치 시 실격",
]);
card(s, 5.1, 2.8, 4.4, 2.2, "왜 어려운가", [
  "채수는 주 1회(경계 이상 주 2회), 강우·유량 증가 시 미채수",
  "세포수는 0 ~ 수십만 cells/mL, 겨울엔 0이 1/4",
  "'26년은 심한 녹조 해: 기준일 10,000 초과 비율 학습 10% vs 평가 58%",
]);

// 3. 데이터 융합
pres.addSection({ title: "데이터" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "데이터" });
s.addText("세 도메인을 기준일 기준 과거 창으로 묶는다", { placeholder: "title" });
card(s, 0.5, 1.3, 2.9, 2.3, "수질·조류 (환경과학원)", ["조류경보제 2,939건, 2012~2026", "세포수(4속 합계·속별), 수온, pH, DO, 투명도, 탁도, 클로로필-a", "이전 1~3회 측정값 lag, 측정 간격"], "E8F1F3");
card(s, 3.55, 1.3, 2.9, 2.3, "기상 (기상청 ASOS)", ["지점별 최근접 관측소 6곳, 일 자료", "기온·강수·풍속·습도·일조·일사·지면온도", "과거 7·14·28일 평균/합/최대/최소"], "EDF4E6");
card(s, 6.6, 1.3, 2.9, 2.3, "수문 (K-water WAMIS)", ["다목적댐 15개 일 자료", "상류 댐 집합의 유입·방류·취수·강우 합산", "대표 댐 저수위 + 월별 평년 편차, 체류시간 대리변수"], "FBEDE6");
s.addShape(pres.ShapeType.roundRect, { x: 0.5, y: 3.85, w: 9.0, h: 1.2, fill: { color: THEME.colors.dk1 }, line: { color: THEME.colors.dk1 }, rectRadius: 0.08, objectName: "merge box" });
s.addText([
  { text: "결합 결과  ", options: { bold: true, color: C.accent6 } },
  { text: "2,939행 × 126열 · 기준일 포함 과거만 사용(rolling + 과거 방향 asof) · 평년값·중앙값은 학습 구간에서만 계산 · 입력 열은 허용 목록으로 선택해 정답·날짜 열이 섞이면 실행 중단", options: { color: C.background1 } },
], { x: 0.7, y: 3.95, w: 8.6, h: 1.0, fontSize: 12, margin: 0, isTextBox: true, valign: "middle" });

// 4. 데이터 특성 (figure)
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "데이터" });
s.addText("지점별 세포수: 여름마다 봉우리, 높이는 해마다 다름", { placeholder: "title" });
s.addImage({ path: FIG + "eda_timeseries.png", x: 0.5, y: 1.15, w: 5.6, h: 3.95, objectName: "지점별 세포수 시계열" });
card(s, 6.3, 1.15, 3.2, 3.95, "데이터에서 확인한 것", [
  "측정 간격 중앙값 7일, 정답 간격이 정확히 7일인 비율 80%",
  "결측: 수질 항목 13.7%, 세포수 5.4%, 독소 90%+ (미사용)",
  "회남 2012~2015년 수온 전부 결측",
  "7일 뒤 세포수와 상관: 기준일 세포수 0.82, 수온 0.71, 4주 기온 0.69",
  "경계(10,000) 초과 비율이 분할마다 달라 분포 이동 존재",
]);

// 5. 피처·누수 차단
pres.addSection({ title: "방법" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "방법" });
s.addText("피처 설계: 요구된 융합 특징을 그대로 구현", { placeholder: "title" });
card(s, 0.5, 1.3, 4.4, 1.75, "누적 강우 · 이동평균 수온·기온", ["기준일 포함 과거 7·14·28일 창 집계(강수 합, 기온 평균, 최고·최저)", "강수 결측(NaN)은 무강수로 간주해 0 처리"]);
card(s, 5.1, 1.3, 4.4, 1.75, "체류시간 대리변수 (저수량 없음)", ["방류 7일 평균 / 유입 7일 평균", "방류 7일 평균 / 방류 28일 평균", "대표 댐 저수위의 월별 평년(≤'24) 대비 편차"]);
card(s, 0.5, 3.2, 4.4, 1.85, "지점 ↔ 상류 댐 (수계 지리로 검증)", ["해평·강정고령: 안동·임하·영주·성덕·군위·김천부항", "칠서: + 합천·남강 / 물금·매리: + 밀양 / 회남: 용담·대청", "조정지댐은 본댐과 중복이라 제외"]);
card(s, 5.1, 3.2, 4.4, 1.85, "규정 준수 장치", ["입력 열 허용 목록(allowlist) + 정답 열 혼입 시 assert 중단", "평가 행 정답은 결합 단계에서 비움", "시드 고정, 명령 두 줄로 재현"], "FBEDE6");

// 6. 결측 전략 (native chart)
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "방법" });
s.addText("결측 대체 전략 3안: 차이는 잡음 수준", { placeholder: "title" });
s.addChart(pres.ChartType.bar, [{ name: "rmse_log10", labels: ["native (모델 기본)", "직전값 + 결측표시", "지점·월 중앙값 + 표시"], values: [0.707, 0.704, 0.710] }],
  { x: 0.5, y: 1.2, w: 5.3, h: 3.9, barDir: "col", chartColors: [THEME.colors.accent1], valAxisMinVal: 0.6, valAxisMaxVal: 0.75, ...chartStyle("검증 2025 rmse_log10 (낮을수록 좋음)") });
card(s, 6.1, 1.3, 3.4, 3.7, "해석", ["세 전략 모두 0.70~0.71, 유의한 차이 없음", "결측 자체보다 7일 뒤 봉우리 예측이 병목", "제출 모델은 검증 최저 전략 자동 선택(직전값 + 결측표시)", "결측 표시 열(_isna)을 넣어 '미채수 상황' 자체를 신호로 활용"]);

// 7. 모델·검증 설계
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "방법" });
s.addText("모델과 검증: LightGBM, 공식 분할 + 롤링 검증", { placeholder: "title" });
card(s, 0.5, 1.3, 4.4, 3.75, "LightGBM 회귀", ["목표 log10(세포수+1), 손실 L2 → 공식 지표 rmse_log10와 일치", "learning_rate 0.03, num_leaves 15, min_child 20, feature/bagging 0.8, λ2 1.0", "반복 수는 공식 검증 early stopping(131)", "5개 지점 통합 모델(지점·우점종은 범주형), 지점별 모델은 더 나빴음", "최종 제출: 학습+검증(≤'25) 재학습 → '26 예측, 0 이상 정수"]);
card(s, 5.1, 1.3, 4.4, 3.75, "검증 설계", ["공식: ~'24 학습 → '25 검증 (256)", "롤링: ~'21→'22 (271), ~'22→'23 (248) — 한 해 운 배제", "5~10월 부분집합 지표 별도 산출(평가 구간과 동일 조건)", "베이스라인: persistence(기준일 값), climatology(지점·월 중앙값)", "'26 실측은 모델 선택에 사용하지 않음(자체 채점 참고만)"], "EDF4E6");

// 8. 결과
pres.addSection({ title: "결과" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("결과: 로그 오차 20% 개선, 원 단위 R²는 목표 미달", { placeholder: "title" });
s.addChart(pres.ChartType.bar, [{ name: "rmse_log10", labels: ["persistence", "climatology", "blend", "LightGBM"], values: [0.883, 0.907, 0.740, 0.704] }],
  { x: 0.5, y: 1.2, w: 4.4, h: 2.6, barDir: "col", chartColors: [THEME.colors.accent5, THEME.colors.accent5, THEME.colors.accent5, THEME.colors.accent1], valAxisMinVal: 0.6, valAxisMaxVal: 0.95, ...chartStyle("검증 2025 rmse_log10") });
s.addTable([
  [{ text: "구분", options: { bold: true, fill: { color: THEME.colors.lt2 } } }, { text: "n", options: { bold: true, fill: { color: THEME.colors.lt2 } } }, { text: "rmse_log10", options: { bold: true, fill: { color: THEME.colors.lt2 } } }, { text: "R² / NSE", options: { bold: true, fill: { color: THEME.colors.lt2 } } }, { text: "F1 (≥10,000)", options: { bold: true, fill: { color: THEME.colors.lt2 } } }],
  ["검증 '25", "256", "0.704", "0.185", "0.667"],
  ["롤링 '22", "271", "0.839", "0.011", "0.328"],
  ["롤링 '23", "248", "0.762", "0.045", "0.267"],
  ["'25 5~10월만", "151", "0.54", "–", "–"],
], { x: 5.1, y: 1.3, w: 4.4, colW: [1.2, 0.45, 1.0, 0.75, 1.0], fontSize: 9.5, fontFace: "Malgun Gothic", color: THEME.colors.dk1, border: { type: "solid", color: "E1E0D9", pt: 0.5 }, rowH: 0.32, objectName: "검증 결과 표" });
card(s, 0.5, 4.0, 9.0, 1.1, "읽는 법", ["persistence 대비 rmse_log10 0.88 → 0.70, 원 단위 R² −0.28 → 0.19. 과제 목표(R² 0.6, NSE 0.5)에는 미달 — 원 단위 지표는 수십만 cells/mL 봉우리 몇 개가 좌우하며 로그 모델은 봉우리를 과소예측"]);

// 9. 피처 중요도
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("예측을 끌고 가는 것: 현재 상태 > 수온 > 수문·기상", { placeholder: "title" });
s.addChart(pres.ChartType.bar, [{ name: "gain", labels: ["기준일 세포수", "log10 세포수", "Microcystis 비율", "직전 세포수(lag1)", "수온", "경보 단계", "댐 강우 28일 합", "Microcystis 세포수", "수온 lag3", "수온 lag1"].reverse(), values: [37501, 8941, 2118, 2036, 1449, 1384, 1155, 979, 725, 713].reverse() }],
  { x: 0.5, y: 1.2, w: 5.6, h: 3.9, barDir: "bar", chartColors: [THEME.colors.accent2], ...chartStyle("피처 중요도 (gain, 최종 모델 상위 10)"), showValue: false });
card(s, 6.3, 1.3, 3.2, 3.7, "선행연구와 비교", ["송찬영 외(2023): 수온 0.63 > 월 0.37 > 유입 0.19 ≈ 방류 0.19", "우리 데이터: 수온·기온·지면온도 28일 평균이 상위, 댐 강우 28일 합이 수문 변수 중 최상위", "융합 데이터가 설명력을 더하는 것은 확인, 7일 뒤 봉우리까지는 못 미침"]);

// 10. 변형 실험
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("12가지 변형 비교: 기준을 넘는 변형은 없었다", { placeholder: "title" });
const hdr = (t) => ({ text: t, options: { bold: true, fill: { color: THEME.colors.lt2 } } });
s.addTable([
  [hdr("변형"), hdr("검증 '25"), hdr("롤링 '22"), hdr("롤링 '23"), hdr("판단")],
  ["기준 (L2 log, 통합 모델)", "0.704", "0.839", "0.762", "채택"],
  ["Huber / Poisson / Tweedie 손실", "0.715 / 0.968 / 0.760", "0.833 / 1.139 / 0.874", "0.776 / 1.181 / 0.851", "열세"],
  ["로그→원 단위 편향 보정, 고농도 가중", "0.705 / 0.705", "0.827 / 0.861", "0.810 / 0.792", "동등"],
  ["persistence 블렌드, 분위수 혼합", "0.723 / 0.709", "0.810 / 0.831", "0.791 / 0.796", "동등"],
  ["동역학 피처(증가율·적산온도·평년 편차)", "0.708", "0.863", "0.749", "동등"],
  ["지점별 모델", "0.739", "0.866", "0.787", "열세"],
  ["회남 '12~'15 제외, 5시드 평균", "0.711 / 0.712", "0.819 / 0.840", "0.758 / 0.758", "동등"],
], { x: 0.5, y: 1.25, w: 9.0, colW: [2.9, 1.7, 1.7, 1.7, 1.0], fontSize: 9.5, fontFace: "Malgun Gothic", color: THEME.colors.dk1, border: { type: "solid", color: "E1E0D9", pt: 0.5 }, rowH: 0.36, objectName: "변형 실험 표" });
s.addText("값은 rmse_log10. 예측 구간(q10~q90) 포함률은 검증 73%로 명목 80%보다 낮아 보수적으로 해석 필요. 결론: 개선은 모델 구조가 아니라 새 정보(향후 기상, 하천 수위)에서 나와야 한다.",
  { x: 0.5, y: 4.35, w: 9.0, h: 0.7, fontSize: 11, color: C.text1, margin: 0, isTextBox: true, italic: true });

// 11. 한계·활용
pres.addSection({ title: "마무리" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "마무리" });
s.addText("정직한 평가와 현업 활용", { placeholder: "title" });
card(s, 0.5, 1.3, 4.4, 3.2, "한계", ["7일 선행에 필요한 정보(향후 기상, 하천 구간 수리 조건)가 입력에 없음", "'26 평가 구간은 5~10월·심한 녹조 해 → 학습 분포와 다름", "DataON 하천 수위는 '24년까지 → 평가 구간 사용 불가, 미사용", "롤링 '22·'23의 댐 수위 평년값에 소폭 사후 정보 포함(공식 분할은 해당 없음)"], "FBEDE6");
card(s, 5.1, 1.3, 4.4, 3.2, "활용 방안 (K-water 운영 관점)", ["경계(10,000) 초과 F1 0.67~0.74 → 제거설비 배치 우선순위의 보조 지표", "지점별 7일 예측 + 예측 구간을 주간 운영 회의 자료로 제공", "결측 표시가 '미채수 상황' 경고 역할", "국립환경과학원 예측정보(물모아)와 동일 기간 비교 예정"], "EDF4E6");

// 12. 재현·다음 단계
s = pres.addSlide({ masterName: "DARK", sectionTitle: "마무리" });
s.addText("재현: make data && make train", { placeholder: "title" });
s.addText("시드 고정 · 하드코딩 없음 · 입력은 기준일 이전 자료만\n다음 단계: 향후 7일 기상 예보 입력, 주 2회 측정 구간의 짧은 간격 활용, 하천 수위 보강\n저장소: github.com/Nautika01/data.AI", { placeholder: "body" });

(async () => {
  await pres.writeFile({ fileName: "bloom_deck.pptx" });
  await applyTheme("bloom_deck.pptx", THEME);
  console.log("deck written");
})();
