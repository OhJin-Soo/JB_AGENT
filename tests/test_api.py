from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_create_get_history_and_chat() -> None:
    client = TestClient(app)
    payload = {
        "title": "MVP analysis",
        "forecast_months": 2,
        "save": True,
        "cashflows": [
            {"date": "2026-01-01", "amount": 3000000, "type": "income", "category": "월급"},
            {"date": "2026-02-01", "amount": 3000000, "type": "income", "category": "월급"},
            {"date": "2026-03-01", "amount": 3000000, "type": "income", "category": "월급"},
            {"date": "2026-01-05", "amount": 1000000, "type": "expense", "category": "생활비"},
            {"date": "2026-02-05", "amount": 1000000, "type": "expense", "category": "생활비"},
            {"date": "2026-03-05", "amount": 1000000, "type": "expense", "category": "생활비"},
        ],
    }

    created = client.post("/analyses", json=payload)
    assert created.status_code == 200
    analysis_id = created.json()["id"]

    fetched = client.get(f"/analyses/{analysis_id}")
    assert fetched.status_code == 200
    assert fetched.json()["result"]["forecast"][0]["month"] == "2026-04"

    history = client.get("/history")
    assert history.status_code == 200
    assert len(history.json()) == 1

    report = client.get(f"/reports/analyses/{analysis_id}.pdf")
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"

    chat = client.post("/chat", json={"question": "내 순현금흐름은?", "analysis_id": analysis_id})
    assert chat.status_code == 200
    assert "answer" in chat.json()
