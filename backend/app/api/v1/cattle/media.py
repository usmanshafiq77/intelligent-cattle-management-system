import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.cattle.dependencies import (
    CATTLE_PREFIX,
    animal_or_404,
    validation_error,
)
from app.core.config import get_settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import CattleMedia, MediaPurpose
from app.models.user import User
from app.schemas.cattle import MediaResponse
from app.services.media_storage import (
    ALLOWED_IMAGE_TYPES,
    MediaStorage,
    detect_image_content_type,
    get_media_storage,
    validate_original_filename,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix=CATTLE_PREFIX)


def _media_or_404(
    db: Session, *, farm_id: UUID, cattle_id: UUID, media_id: UUID
) -> CattleMedia:
    media = db.scalar(
        select(CattleMedia).where(
            CattleMedia.id == media_id,
            CattleMedia.farm_id == farm_id,
            CattleMedia.cattle_id == cattle_id,
            CattleMedia.removed_at.is_(None),
        )
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Cattle media not found")
    return media


async def _read_limited_body(request: Request, maximum: int) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > maximum:
            raise HTTPException(status_code=413, detail="Image is too large")
        content.extend(chunk)
    return bytes(content)


@router.post(
    "/{cattle_id}/media",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
    purpose: MediaPurpose = MediaPurpose.PROFILE,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
):
    animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    maximum = get_settings().CATTLE_MEDIA_MAX_BYTES
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
            if declared_length < 0:
                raise ValueError
            if declared_length > maximum:
                raise HTTPException(
                    status_code=413, detail="Image is too large"
                )
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid Content-Length"
            ) from None
    content = await _read_limited_body(request, maximum)
    if not content:
        raise HTTPException(status_code=422, detail="Image content is required")
    try:
        original_filename = validate_original_filename(filename)
        detected_type = detect_image_content_type(content)
    except ValueError as error:
        raise validation_error(error) from None
    declared_type = (
        request.headers.get("content-type", "").split(";", 1)[0].lower()
    )
    if declared_type not in {detected_type, "application/octet-stream"}:
        raise HTTPException(
            status_code=422,
            detail="Declared content type does not match image content",
        )

    media_id = uuid.uuid4()
    extension = ALLOWED_IMAGE_TYPES[detected_type]
    storage_key = f"cattle/{farm_id}/{cattle_id}/{media_id}{extension}"
    media = CattleMedia(
        id=media_id,
        cattle_id=cattle_id,
        farm_id=farm_id,
        storage_key=storage_key,
        original_filename=original_filename,
        content_type=detected_type,
        size_bytes=len(content),
        purpose=purpose,
        uploaded_by_id=current_user.id,
    )
    try:
        storage.save(storage_key, content)
        db.add(media)
        db.commit()
        db.refresh(media)
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        logger.exception("Cattle media upload failed")
        raise HTTPException(
            status_code=500, detail="Could not store cattle media"
        ) from None
    return media


@router.get(
    "/{cattle_id}/media", response_model=list[MediaResponse]
)
def list_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    return db.scalars(
        select(CattleMedia)
        .where(
            CattleMedia.farm_id == farm_id,
            CattleMedia.cattle_id == cattle_id,
            CattleMedia.removed_at.is_(None),
        )
        .order_by(CattleMedia.uploaded_at.desc(), CattleMedia.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@router.get(
    "/{cattle_id}/media/{media_id}", response_model=MediaResponse
)
def get_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    media_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    return _media_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, media_id=media_id
    )


@router.get("/{cattle_id}/media/{media_id}/content")
def get_cattle_media_content(
    farm_id: UUID,
    cattle_id: UUID,
    media_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
):
    animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    media = _media_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, media_id=media_id
    )
    try:
        path = storage.resolve(media.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Media content not found"
        ) from None
    return FileResponse(
        path=path,
        media_type=media.content_type,
        filename=media.original_filename,
    )


@router.delete(
    "/{cattle_id}/media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    media_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
):
    animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    media = _media_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, media_id=media_id
    )
    media.removed_at = datetime.now(timezone.utc)
    media.removed_by_id = current_user.id
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Cattle media removal failed")
        raise HTTPException(
            status_code=500, detail="Could not remove cattle media"
        ) from None
    try:
        storage.delete(media.storage_key)
    except OSError:
        logger.exception("Removed cattle media file cleanup failed")
    return None
