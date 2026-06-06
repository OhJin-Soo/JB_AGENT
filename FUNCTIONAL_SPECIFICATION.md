- 부록 E. 외부 API 명세
    - 기상청 API
        - 데이터 출처: 기상청
        - 데이터 이용 방안: 현재 날짜 기준 -5년 기간을 인자로 넣어 조회한다. (tm1 = sysdate() - 5, tm2 = sysdate()) 출력 결과를 지출 예측의 외생 변수로써 사용한다.
        - 요청 URL: https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php?tm1=20151211&tm2=20151214&stn=108&help=1&authKey={인증키}
        - 기상 데이터 인증키 명은 WEATHER_API_KEY
        - 입력 인자
            
            
            | **인자명** | **의미** | **설명** |
            | --- | --- | --- |
            | tm | 년월일시분(KST)년월일(KST) | 해당 시간 (없으면 현재시간) |
            | tm1 | 년월일시분(KST)년월일(KST) | 기간: 시작시간 또는 시작일 (없으면 현재시간) |
            | tm2 | 년월일시분(KST)년월일(KST) | 기간: 종료시간 또는 종료일 (없으면 현재시간) |
            | obs | 관측종류 | TA(기온), TD(이슬점온도), HM(습도), PV(증기압), PA(현지기압), PS(해면기압), CA_TOT(전운량), CA_MID(중하층운량), CH_MIN(최저온고(100m)),CT(운형(통계표)), VS(시정(10m)), TS(지면온도) |
            | stn | 지점번호 | 해당 지점들(:로 구분)의 정보 표출 (0 이거나 없으면 전체지점) |
            | help | 도움말추가 | 1 이면 필드에 대한 약간의 도움말 추가 (0 이거나 없으면 없음) |
            | mode | 기타 | 0:해독결과만 표출, 1:기사도 표출, 2:기사만 표출 |
            | authKey | 인증키 | 발급된 API 인증키 |
        - 출력 결과
            
            
            | **변수명** | **의미(단위)** | **변수명** | **의미(단위)** |
            | --- | --- | --- | --- |
            | TM | 관측시각 (KST) | STN | 국내 지점번호 |
            | WS_AVG | 일 평균 풍속 (m/s) | WR_DAY | 일 풍정 (m) |
            | WD_MAX | 최대풍향 | WS_MAX | 최대풍속 (m/s) |
            | WS_MAX_TM | 최대풍속 시각 (시분) | WD_INS | 최대순간풍향 |
            | WS_INS | 최대순간풍속 (m/s) | WS_INS_TM | 최대순간풍속 시각 (시분) |
            | TA_AVG | 일 평균기온 (C) | TA_MAX | 최고기온 (C) |
            | TA_MAX_TM | 최고기온 시가 (시분) | TA_MIN | 최저기온 (C) |
            | TA_MIN_TM | 최저기온 시각 (시분) | TD_AVG | 일 평균 이슬점온도 (C) |
            | TS_AVG | 일 평균 지면온도 (C) | TG_MIN | 일 최저 초상온도 (C) |
            | HM_AVG | 일 평균 상대습도 (%) | HM_MIN | 최저습도 (%) |
            | HM_MIN_TM | 최저습도 시각 (시분) | PV_AVG | 일 평균 수증기압 (hPa) |
            | EV_S | 소형 증발량 (mm) | EV_L | 대형 증발량 (mm) |
            | FG_DUR | 안개계속시간 (hr) | PA_AVG | 일 평균 현지기압 (hPa) |
            | PS_AVG | 일 평균 해면기압 (hPa) | PS_MAX | 최고 해면기압 (hPa) |
            | PS_MAX_TM | 최고 해면기압 시각 (시분) | PS_MIN | 최저 해면기압 (hPa) |
            | PS_MIN_TM | 최저 해면기압 시각 (시분) | CA_TOT | 전운량 (1/10) |
            | SS_DAY | 일조합 (hr) | SS_DUR | 가조시간 (hr) |
            | SS_CMB | 캄벨 일조 (hr) | SI_DAY | 일사합 (MJ/m2) |
            | SI_60M_MAX | 최대 1시간일사 (MJ/m2) | SI_60M_MAX_TM | 최대 1시간일사 시각 (시분) |
            | RN_DAY | 일 강수량 (mm) | RN_D99 | 9-9 강수량 (mm) |
            | RN_DUR | 강수계속시간 (hr) | RN_60M_MAX | 1시간 최다강수량 (mm) |
            | RN_60M_MAX_TM | 1시간 최다강수량 시각 (시분) | RN_10M_MAX | 10분간 최다강수량 (mm) |
            | RN_10M_MAX_TM | 10분간 최다강수량 시각 (시분) | RN_POW_MAX | 최대 강우강도 (mm/h) |
            | RN_POW_MAX_TM | 최대 강우강도 시각 (시분) | SD_NEW | 최심 신적설 (cm) |
            | SD_NEW_TM | 최심 신적설 시각 (시분) | SD_MAX | 최심 적설 (cm) |
            | SD_MAX_TM | 최심 적설 시각 (시분) | TE_05 | 0.5m 지중온도 (C) |
            | TE_10 | 1.0m 지중온도 (C) | TE_15 | 1.5m 지중온도 (C) |
            | TE_30 | 3.0m 지중온도 (C) | TE_50 | 5.0m 지중온도 (C) |
    - 부동산 API
        - 부동산 데이터는 부동산통계정보의 “월단위 지가변동률” 데이터를 이용한다.
        - 데이터 출처: https://www.reb.or.kr/r-one/portal/main/indexPage.do
        - 데이터 이용 방안: 데이터 파라미터는 CLS_ID=50025로 “전북”으로 한정한다. 주기코드 파라미터는 MM를 사용해 월 단위로 조회한다. 현재 날짜 기준 -5년부터 최신 데이터까지의 지가변동률을 조회한다. (START_WRTTIME = sysdate()-5에서 YYYYMM 까지를 인자로, END_WRTTIME= sysdate()에서 YYYYMM 까지를 인자로 사용.) 사용자가 보유한 부동산 자산의 현재 가치 및 미래 가치 변동을 추정하여 순자산 계산에 활용한다.
        - 요청 URL: https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do?KEY={인증키}&pIndex=1&pSize=50&STATBL_ID=A_2024_00903&DTACYCLE_CD=QY&CLS_ID=500025
        - 부동산 데이터는 인증키 명은 REAL_ESTATE_API_KEY
        - 입력 인자
            
            ### **기본인자**
            
            | 변수명 | 타입 | 필수여부 | 값설명 |
            | --- | --- | --- | --- |
            | KEY | STRING (필수) | 인증키 | 기본값 : sample key |
            | Type | STRING (필수) | 호출 문서 (xml, json) | 기본값 : xml |
            | pIndex | INTEGER (필수) | 페이지 위치 | 기본값 : 1(sample key는 1 고정) |
            | pSize | INTEGER (필수) | 페이지 당 요청 숫자 | 기본값 : 100(sample key는 5 고정) |
            
            ### **요청인자**
            
            | 변수명 | 타입 | 변수 설명 |
            | --- | --- | --- |
            | STATBL_ID | STRING(필수) | 통계표 ID |
            | DTACYCLE_CD | STRING(필수) | 주기코드 |
            | WRTTIME_IDTFR_ID | STRING(선택) | 자료작성 시점 |
            | GRP_ID | STRING(선택) | 그룹ID |
            | CLS_ID | STRING(선택) | 분류ID |
            | ITM_ID | STRING(선택) | 항목ID |
            | START_WRTTIME | STRING(선택) | 자료작성 시점 시작일 |
            | END_WRTTIME | STRING(선택) | 자료작성 시점 종료일 |
        - 출력 인자
            
            ### **출력값(Out Result)**
            
            | 순번 | 출력명 | 출력설명 | 컬럼타입 | 컬럼길이 |
            | --- | --- | --- | --- | --- |
            | 1 | STATBL_ID | 통계표 ID | CHAR | 50 |
            | 2 | DTACYCLE_CD | 주기코드 | CHAR | 50 |
            | 3 | WRTTIME_IDTFR_ID | 자료작성 시점 | CHAR | 8 |
            | 4 | GRP_ID | 그룹ID | NUMBER | 8 |
            | 5 | GRP_NM | 그룹명 | VARCHAR2 | 300 |
            | 6 | CLS_ID | 분류ID | NUMBER | 8 |
            | 7 | CLS_NM | 분류명 | VARCHAR2 | 300 |
            | 8 | ITM_ID | 항목ID | NUMBER | 8 |
            | 9 | ITM_NM | 항목명 | VARCHAR2 | 300 |
            | 10 | DTA_VAL | 통계 자료값 | NUMBER | 22 |
            | 11 | UI_NM | 단위명 | VARCHAR | 100 |
            | 12 | GRP_FULLNM | 그룹전체명 | VARCHAR2 | 1000 |
            | 13 | CLS_FULLNM | 분류전체명 | VARCHAR2 | 1000 |
            | 14 | ITM_FULLNM | 항목전체명 | VARCHAR2 | 1000 |
            | 15 | WRTTIME_DESC | 자료시점설명 | VARCHAR2 | 100 |
            - 요청 URL: https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do?KEY={인증키}&pIndex=1&pSize=50&STATBL_ID=A_2024_00903&DTACYCLE_CD=QY&CLS_ID=500025
    - LLM API
        - LLM 모델: gpt-4o-mini
        - LLM API KEY 명: OPENAI_API_KEY