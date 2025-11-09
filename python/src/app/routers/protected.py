from fastapi import APIRouter, Depends

from ..deps import require_permission, require_rate_limit

router = APIRouter(prefix="/api/v1/protected", tags=["protected"])


@router.get(
    "/secret",
    dependencies=[
        Depends(require_permission("view_secret")),
        Depends(require_rate_limit),
    ],
)
async def secret(_: bool = Depends(require_permission("view_secret"))):
    return {"secret": "42"}
