from __future__ import annotations

from fastapi.testclient import TestClient
from starlette import status


def test_write_endpoint_requires_auth_by_default(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/ingest/poll",
        json={"platform": "youtube", "max_new_videos": 1},
    )

    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }
