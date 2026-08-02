import pytest
from unittest.mock import AsyncMock

@pytest.fixture(autouse=True)
def mock_redis_cache(mocker):
    """
    Automatically mock Redis cache GET, SET, and DELETE methods 
    so tests do not depend on a running Redis instance.
    """
    mocker.patch("app.cache.get", new_callable=AsyncMock, return_value=None)
    mocker.patch("app.cache.set", new_callable=AsyncMock, return_value=True)
    mocker.patch("app.cache.delete", new_callable=AsyncMock, return_value=True)
    mocker.patch("app.cache.redis_client", None)
