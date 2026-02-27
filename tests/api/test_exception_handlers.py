from pydantic import BaseModel

from main import app


# 422 테스트용 임시 엔드포인트
class _DummyBody(BaseModel):
    name: str
    age: int


@app.post("/test/validation")
async def _validation_endpoint(body: _DummyBody):
    return {"ok": True}


def test_validation_error_returns_basic_error_response(client):
    """잘못된 요청 body → 422 BasicErrorResponse 형식 반환"""
    response = client.post(
        "/test/validation",
        json={"name": "test", "age": "not_a_number"},
    )
    assert response.status_code == 422

    body = response.json()
    assert body["result"] == "FAIL"
    assert body["errorCode"] == "VALIDATION_ERROR"
    assert body["message"] == "입력값 검증에 실패했습니다"
    assert "errors" in body["data"]
    assert isinstance(body["data"]["errors"], list)
    assert len(body["data"]["errors"]) > 0

    error = body["data"]["errors"][0]
    assert "field" in error
    assert "message" in error
    assert "type" in error


def test_not_found_returns_basic_error_response(client):
    """존재하지 않는 경로 → 404 BasicErrorResponse 형식 반환"""
    response = client.get("/api/v1/nonexistent-path")
    assert response.status_code == 404

    body = response.json()
    assert body["result"] == "FAIL"
    assert body["errorCode"] == "NOT_FOUND"
    assert body["path"] == "/api/v1/nonexistent-path"


def test_method_not_allowed_returns_basic_error_response(client):
    """잘못된 HTTP 메서드 → 405 BasicErrorResponse 형식 반환"""
    response = client.delete("/api/v1/health")
    assert response.status_code == 405

    body = response.json()
    assert body["result"] == "FAIL"
    assert body["errorCode"] == "METHOD_NOT_ALLOWED"
    assert body["path"] == "/api/v1/health"
