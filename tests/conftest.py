import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app import models


@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    client.testing_session_local = TestingSessionLocal

    try:
        # Create a test account in the isolated test database.
        registration = client.post(
            "/api/auth/register",
            json={
                "full_name": "Test Administrator",
                "email": "fixture@example.com",
                "password": "FixturePassword123",
            },
        )
        assert registration.status_code == 201, registration.text

        login = client.post(
            "/api/auth/login",
            json={
                "email": "fixture@example.com",
                "password": "FixturePassword123",
            },
        )
        assert login.status_code == 200, login.text

        token = login.json()["access_token"]
        client.headers.update(
            {"Authorization": f"Bearer {token}"}
        )

        yield client

    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
