기능 명세서

- 서비스 개요(Service)
    - 사용자의 현금흐름을 분석해 미래의 자신의 자산을 알려주는 서비스
- 시스템 구성도(Architecture)
    
    ```jsx
    Frontend
     ├─ Dashboard Panel
     └─ Chat Panel
    
    Backend: FastAPI
     ├─ Analysis Pipeline
     │   ├─ Data Preprocessor
     │   ├─External Data Collector
     │      ├─ Weather API
     │      └─ Real Estate API
     │   ├─ Category Classifier
     │   ├─ Policy Router
     │   ├─ Forecast Tools
     │   │   ├─ Rule-based Tool
     │   │   ├─ SARIMAX Tool
     │   │   ├─ XGBoost Tool
     │   │   └─ Property Valuation Tool
     │   └─ Result Aggregator
     │
     ├─ Conversational Agent
     │   ├─ Planner
     │   ├─ Tool Executor
     │   ├─ Context Retriever
     │   ├─ Web Search(Tavily)
     │   ├─ Validator
     │   └─ Response Generator
     │
     └─ PostgreSQL
         ├─ User Cashflow Data
         ├─ Analysis Results
         └─ Chat History
    ```
    
- 핵심 기능 명세(Feature Specification)
- 분석 기능
    - 사용자는 현금흐름 데이터를 입력할 수 있다.
    - 사용자는 예측 기간을 선택할 수 있다.
    - 시스템은 미래 현금흐름을 예측한다.
    - 시스템은 그래프를 제공한다.
    - 시스템은 자연어 해석을 제공한다.
- 저장 기능
    - 사용자는 분석 결과를 저장할 수 있다.
    - 저장된 결과는 히스토리 탭에서 조회할 수 있다.
- 리포트 기능
    - PDF 다운로드를 제공한다.
- 대화형 기능
    - 사용자는 자연어 질문을 입력할 수 있다.
    - Agent는 질문에 필요한 Tool을 계획하고 호출한다.
    - 시스템은 사용자의 질문을 돕기 위해 예시 질문 버튼(Helper Button)을 제공한다.
    - 사용자가 예시 질문 버튼을 선택하면 해당 문장이 자동으로 질문으로 입력되어 Agent가 답변을 생성한다.
    - Agent는 생성된 답변의 근거와 데이터 충분성을 검증한다.
    - 데이터가 부족하거나 결과의 신뢰도가 낮은 경우 추가 정보를 요청하거나 추가 Tool을 호출한다.
- 주요 기능 흐름도(Flow)
    - 대시보드 생성 기능 흐름도
        
        ```jsx
        사용자 데이터 입력
        ↓
        예측 기간 선택
        ↓
        외부 데이터 조회
        (기상 데이터, 부동산 데이터)
        ↓
        카테고리 분류
        ↓
        Policy Router
        ↓
        Rule-based Tool
        SARIMAX Tool
        XGBoost Tool
        ↓
        결과 통합
        ↓
        그래프 생성
        ↓
        자연어 설명 생성
        ↓
        대시보드 출력
        ↓
        (선택)
        저장 버튼
        ↓
        PostgreSQL 저장
        ```
        
    - 대화형 기능
        
        ```jsx
        사용자 질문
        ↓
        Planner
        ↓
        Tool 선택
        ↓
        Context Retrieval
        ↓
        (필요 시) Web Search
        ↓
        Response Generator
        ↓
        충분한 근거 존재?
         ├─ Yes → 채팅 답변
         └─ No
              ↓
        추가 Tool 호출 또는
        추가 질문 수행
        ```
        
- 향후 발전 방향(Future Work)
    - 기능 확장
        - 대시보드에 사용자가 대화형 기능을 통해 답변 받은 AI의 분석 결과에 “대시보드에 추가” 버튼을 만들어 대시보드에 추가할 수 있게 하는 기능 추가.
        - What-if 시뮬레이션 기능 추가.
            - 이 기능을 통해 질문에 따라 대시보드 내용이 실시간 갱신됨.
            - 질문 예시
                - "내년 소비를 10% 줄이면?"
                - "월급이 20만원 오른다면?"
    - 기술 고도화
        - Transformer 기반 시계열 모델(PatchTST, Chronos 등)을 비교 적용하여 예측 성능 향상
        - Reflexion, Self-Refine 등 검증 기반 Agent 구조를 적용하여 답변 신뢰도 향상
        - SHAP 기반 설명 가능성을 강화하여 주요 지출 요인 분석 기능 제공
        - 단일 Agent 구조에서 Multi-Agent 구조로 확장하여 복합 재무 의사결정 지원
- 부록(Appendix)
    - 부록 A. 용어 정의
        - 현금흐름
        - 순자산
        - SARIMAX
        - XGBoost
        - Agent
    - 부록 B. ERD
        - users
        - cashflow_records
        - analysis_results
        - chat_messages
        - reports
    - 부록 B. 입력 CSV 데이터 형식
        - date,description,amount,type,category
        - 2025-01-25,월급,3000000,income,salary
        - 2025-01-28,전기요금,-85000,expense,utility
    - 부록 C. API 입출력
        - POST /cashflows/upload
        - POST /analysis/run
        - GET /analysis/{analysis_id}
        - POST /chat
        - POST /reports/{analysis_id}/download
    - 부록 D. 보안 및 리스크 관리
        - 개인정보 보호
            - 사용자 금융 데이터는 암호화하여 저장한다.
            - 사용자별 접근 권한을 관리한다.
        - 설명 가능성
            - 분석 결과는 그래프와 자연어 설명을 함께 제공한다.
            - Agent는 사용자의 입력 데이터, 분석 결과 및 검색된 외부 정보에 기반하여 답변을 생성한다.
            - 근거가 부족하거나 신뢰도가 낮은 경우 추가 정보를 요청하거나 답변 생성을 중단한다.
            - Agent는 답변 생성에 사용된 근거 데이터 및 외부 정보의 출처를 명시한다.
        - 환각 최소화
            - Agent는 사용자의 입력 데이터, 분석 결과, 검색된 외부 정보에 근거하여 답변을 생성한다.
            - 충분한 근거가 확보되지 않은 경우 Agent는 답변 생성을 중단하거나 추가 정보를 요청한다.
        - 책임 범위
            - 서비스는 재무 의사결정을 지원하기 위한 참고 정보를 제공하며 투자 권유를 목적으로 하지 않는다.
    - 부록 E. 외부 API 명세
        - 기상 데이터
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