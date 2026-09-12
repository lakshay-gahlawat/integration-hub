import os
import uuid

os.environ["DATABASE_URL"] = "postgresql+psycopg2://postgres:postgres@localhost:5432/integration_hub_test"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["GITHUB_WEBHOOK_SECRET"] = "github-test-secret"
os.environ["SLACK_SIGNING_SECRET"] = "slack-test-secret"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["INTEGRATION_ENCRYPTION_KEY"] = "PTkhGquV1pYumTvxHyVsfa6U83cfNNBiAwlycP0Htnc="
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"  # the rate limiter middleware is a per-process
# singleton and the test suite reuses one app instance across every test, so a
# realistic per-minute limit would otherwise make the suite trip its own rate
# limiting well before covering all the auth/webhook/oauth flows it needs to.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 ensure all models are registered on Base.metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
_engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="session")
def engine():
    """Exposes the raw SQLAlchemy engine for tests that need to open
    independent sessions/connections directly -- e.g. simulating two
    concurrent webhook deliveries racing against the same unique
    constraint, which the single shared per-test `db_session` transaction
    can't represent."""
    return _engine


@pytest.fixture()
def db_session():
    connection = _engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _get_db_override
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_provider_identity(monkeypatch):
    """Every test that connects an integration via the manual-token path
    triggers a real `fetch_account_identity` call to GitHub/Slack. Mock it
    so tests don't depend on network access or real credentials, while
    still deriving a distinct, deterministic external_account_id from
    whatever fake token the test supplies -- this lets webhook-linking
    tests control which integration a webhook should match purely by
    choosing matching tokens/account ids, the same way real accounts
    would naturally differ."""
    from app.integrations.github_provider import GitHubProvider
    from app.integrations.slack_provider import SlackProvider

    async def fake_identity(self, access_token: str):
        return access_token, f"name-{access_token}"

    monkeypatch.setattr(GitHubProvider, "fetch_account_identity", fake_identity)
    monkeypatch.setattr(SlackProvider, "fetch_account_identity", fake_identity)


@pytest.fixture()
def registered_user(client):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple", "full_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def auth_headers(registered_user):
    token = registered_user["access_token"]
    return {"Authorization": f"Bearer {token}"}
