import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings


@pytest.fixture()
def client(tmp_path):
    test_settings = Settings(
        database_url=str(tmp_path / "test.db"),
        chroma_persist_dir=str(tmp_path / "chroma"),
        chroma_collection_name="test_items",
    )
    with patch("app.config.settings", test_settings), \
         patch("app.database.settings", test_settings), \
         patch("app.services.vector_store.settings", test_settings), \
         patch("app.services.ask_service.settings", test_settings), \
         patch("app.services.ingest_service.settings", test_settings):
        from app.main import app
        with TestClient(app) as c:
            yield c
