import hashlib
import json

from app.main import app


STEP_17_OPENAPI_SHA256 = (
    "8cc081366b42147d5f3961828fe8e2796fcafe5fd2e240f318a32c204cbb942b"
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def test_step_17_openapi_contract_is_unchanged():
    """Require an explicit review before changing the published API contract."""
    specification = app.openapi()
    canonical = json.dumps(
        specification,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    operation_count = sum(
        1
        for path_item in specification["paths"].values()
        for method in path_item
        if method in HTTP_METHODS
    )

    assert len(specification["paths"]) == 50
    assert operation_count == 70
    assert hashlib.sha256(canonical).hexdigest() == STEP_17_OPENAPI_SHA256
