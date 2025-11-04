"""
Tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


def test_index_page():
    """Test main page loads."""
    response = client.get("/")
    assert response.status_code == 200
    assert "TurboScribe" in response.text


def test_create_job_no_file():
    """Test job creation without file fails."""
    response = client.post("/v1/jobs")
    assert response.status_code == 400


def test_get_nonexistent_job():
    """Test getting non-existent job returns 404."""
    response = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_create_job_mock(monkeypatch, tmp_path):
    """Test job creation with mocked file."""
    import os
    from app.main import UPLOAD_DIR
    
    # Mock file upload
    test_file = tmp_path / "test.mp3"
    test_file.write_bytes(b"fake audio content")
    
    # Mock pipeline run
    def mock_run(*args, **kwargs):
        return []
    
    monkeypatch.setattr("videotext.pipeline.Pipeline.run", mock_run)
    
    with open(test_file, "rb") as f:
        response = client.post(
            "/v1/jobs",
            files={"source": ("test.mp3", f, "audio/mpeg")},
            data={"mode": "fast"}
        )
    
    # Should create job (may be async, so check status code)
    assert response.status_code in [200, 201]


def test_get_job_artifacts_nonexistent():
    """Test getting artifacts for non-existent job."""
    response = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000/artifacts")
    assert response.status_code == 404


def test_cancel_job_nonexistent():
    """Test cancelling non-existent job."""
    response = client.delete("/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
