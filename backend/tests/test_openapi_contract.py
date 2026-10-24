import hashlib
import json

from app.main import app


STABILIZED_OPENAPI_SHA256 = (
    "4fff2d3b792e64e6a526681affbd64a0b36c3acba57a3b967f43bbee515dd784"
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def test_stabilized_openapi_contract_is_reviewed():
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

    assert len(specification["paths"]) == 143
    assert operation_count == 190
    assert hashlib.sha256(canonical).hexdigest() == STABILIZED_OPENAPI_SHA256
