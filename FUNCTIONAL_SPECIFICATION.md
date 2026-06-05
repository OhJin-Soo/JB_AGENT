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