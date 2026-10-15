import hashlib
import json

from app.main import app


STEP_18_OPENAPI_SHA256 = (
    "6199c4095b695675714e06923a73e68d82d28889be79ed6025dd853252842014"
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def test_step_18_openapi_contract_is_unchanged():
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

    assert len(specification["paths"]) == 63
    assert operation_count == 87
    assert hashlib.sha256(canonical).hexdigest() == STEP_18_OPENAPI_SHA256
