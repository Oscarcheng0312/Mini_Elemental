import os
os.environ.setdefault("OPENAI_API_KEY", "test_dummy_key")
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport = ASGITransport(app=app),
        base_url = "http://test",
    ) as ac:
        yield ac   