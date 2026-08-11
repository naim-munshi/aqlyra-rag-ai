import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    (
        "postgresql+psycopg://postgres:postgres"
        "@localhost:5432/aqlyra_rag_ai_test"
    ),
)

TEST_UPLOAD_DIR = Path(
    tempfile.mkdtemp(
        prefix="aqlyra-rag-test-uploads-"
    )
)

os.environ["SECRET_KEY"] = (
    "test-only-secret-key-do-not-use-in-production"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["UPLOAD_DIR"] = str(TEST_UPLOAD_DIR)
os.environ["DEBUG"] = "false"
os.environ["EMBEDDING_PROVIDER"] = "deterministic"
os.environ["LLM_PROVIDER"] = "deterministic"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models import (
    Document,
    DocumentChunk,
    DocumentUnit,
    EmbeddingRecord,
    User,
)

_REGISTERED_MODELS = (
    User,
    Document,
    DocumentUnit,
    DocumentChunk,
    EmbeddingRecord,
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def clear_test_uploads() -> None:
    shutil.rmtree(
        TEST_UPLOAD_DIR,
        ignore_errors=True,
    )

    TEST_UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


@pytest.fixture(
    scope="session",
    autouse=True,
)
def prepare_test_database() -> Generator[
    None,
    None,
    None,
]:
    Base.metadata.drop_all(
        bind=test_engine
    )

    Base.metadata.create_all(
        bind=test_engine
    )

    clear_test_uploads()

    yield

    Base.metadata.drop_all(
        bind=test_engine
    )

    test_engine.dispose()

    shutil.rmtree(
        TEST_UPLOAD_DIR,
        ignore_errors=True,
    )


@pytest.fixture
def db_session() -> Generator[
    Session,
    None,
    None,
]:
    session = TestingSessionLocal()

    try:
        yield session

    finally:
        session.close()

        with test_engine.begin() as connection:
            for table in reversed(
                Base.metadata.sorted_tables
            ):
                connection.execute(
                    table.delete()
                )

        clear_test_uploads()


@pytest.fixture
def client(
    db_session: Session,
) -> Generator[
    TestClient,
    None,
    None,
]:
    def override_get_db() -> Generator[
        Session,
        None,
        None,
    ]:
        yield db_session

    app.dependency_overrides[
        get_db
    ] = override_get_db

    try:
        with TestClient(
            app
        ) as test_client:
            yield test_client

    finally:
        app.dependency_overrides.clear()
