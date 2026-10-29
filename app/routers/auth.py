from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies import decode_access_token
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()


@router.get("/token-check", response_model=MessageResponse)
def token_check(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> MessageResponse:
    """Validate an access token."""
    decode_access_token(credentials.credentials)
    return MessageResponse(message="Access token is valid")