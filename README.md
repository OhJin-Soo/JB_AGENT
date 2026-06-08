JB Agent
========

AI 기반 개인 현금흐름/순자산 분석 서비스의 FastAPI 구현입니다.

## 구현된 범위

- FastAPI 프로젝트 구조
- 현금흐름 입력 검증
- 규칙 기반 월별 현금흐름 예측
- 분석 결과 저장 및 히스토리 조회
- 그래프용 응답 데이터
- 자연어 요약
- PDF 리포트 다운로드
- 기상청/부동산/Tavily 외부 API 클라이언트
- OpenAI 기반 답변 생성 클라이언트
- 분석 결과와 검색 컨텍스트를 사용하는 1차 Agent API
- SARIMAX/XGBoost 예측기 placeholder

## 실행

```bash
uv sync
uv run uvicorn app.main:app --reload
```

프론트엔드:

```bash
cd frontend
npm install
npm run dev
```

기본 접속 주소는 `http://127.0.0.1:5173`입니다.

## 환경 변수

```bash
DATABASE_URL=sqlite:///./jb_agent.db
WEATHER_API_KEY=
REAL_ESTATE_API_KEY=
OPENAI_API_KEY=
TAVILY_API_KEY=
```

## 주요 API

- `POST /analyses`
- `GET /analyses/{analysis_id}`
- `GET /history`
- `GET /reports/analyses/{analysis_id}.pdf`
- `POST /chat`
