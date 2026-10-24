import hashlib
import json

from app.main import app


STABILIZED_OPENAPI_SHA256 = (
    "a0bdd2d6394159f430df8e78bc8f03aedd21807df1323b3ab7ebd9f2ad784382"
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

    assert len(specification["paths"]) == 178
    assert operation_count == 237
    assert hashlib.sha256(canonical).hexdigest() == STABILIZED_OPENAPI_SHA256
