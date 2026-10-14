import hashlib
import json

from app.main import app


STEP_16_OPENAPI_SHA256 = (
    "d8eed575e1b1f1263597b61a5456434c6631025ee494f5f8a2dfea36d79631ac"
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def test_step_16_openapi_contract_is_unchanged():
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

    assert len(specification["paths"]) == 32
    assert operation_count == 45
    assert hashlib.sha256(canonical).hexdigest() == STEP_16_OPENAPI_SHA256
