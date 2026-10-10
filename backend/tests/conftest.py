import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


class FakeSentimentService:
    """
    Stands in for the real HF model in tests so we don't need actual
    weights on disk. Deterministic output based on simple keyword rules.
    """

    def is_ready(self) -> bool:
        return True

    def predict_batch(self, texts):
        results = []
        for text in texts:
            lower = text.lower()
            if "bad" in lower or "hate" in lower or "terrible" in lower:
                scores = {"negative": 0.9, "neutral": 0.07, "positive": 0.03}
            elif "great" in lower or "love" in lower or "good" in lower:
                scores = {"positive": 0.88, "neutral": 0.08, "negative": 0.04}
            else:
                scores = {"neutral": 0.7, "positive": 0.15, "negative": 0.15}
            results.append(scores)
        return results

    def predict_single(self, text):
        return self.predict_batch([text])[0]


@pytest.fixture()
def client(tmp_path):
    test_db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.ml_service = FakeSentimentService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def authed_client(client):
    """A TestClient that has already registered + logged in a user
    (cookie is retained automatically by the client's session)."""
    client.post(
        "/api/auth/register",
        json={"email": "testuser@example.com", "password": "strongpassword123"},
    )
    return client
