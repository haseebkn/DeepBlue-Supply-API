import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import main module
import main

# Setup an isolated, in-memory SQLite database connection
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override main's SessionLocal globally so background tasks use the test database
main.SessionLocal = TestingSessionLocal


@pytest.fixture(name="db_session")
def fixture_db_session():
    """
    Creates an isolated test database session.
    Automatically generates all schema tables before the test runs,
    and drops them immediately afterwards.
    """
    main.Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        main.Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def fixture_client(db_session):
    """
    Creates a FastAPI TestClient configured to use the isolated test database session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Apply database override to the app
    main.app.dependency_overrides[main.get_db] = override_get_db
    with TestClient(main.app) as test_client:
        yield test_client
    # Clear overrides to prevent cross-test leakage
    main.app.dependency_overrides.clear()
