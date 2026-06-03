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
    - Agent는 질문에 필요한 Tool을 호출해 답변한다.
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
        채팅 답변
        ```
        
- 향후 발전 방향(Future Work)
    - 대시보드에 사용자가 대화형 기능을 통해 답변 받은 AI의 분석 결과에 “대시보드에 추가” 버튼을 만들어 대시보드에 추가할 수 있게 하는 기능 추가.
    - What-if 시뮬레이션 기능 추가.
        - 이 기능을 통해 질문에 따라 대시보드 내용이 실시간 갱신됨.
        - 질문 예시
            - "내년 소비를 10% 줄이면?"
            - "월급이 20만원 오른다면?"
- 부록(Appendix)
    - 부록 A. 용어 정의
        - 현금흐름
        - 순자산
        - SARIMAX
        - XGBoost
        - Agent
    - 부록 B. 입력 CSV 데이터 형식 예시
    - 부록 C. API 입출력 데이터 형식 예시