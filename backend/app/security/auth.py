from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from typing import Optional, Dict, Any
import httpx
import structlog

from app.config import settings


security = HTTPBearer(auto_error=False)
logger = structlog.get_logger()

JWKS_CACHE: Optional[Dict] = None
_role_cache: Dict[str, str] = {}

# Demo user IDs mapped to roles
DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "demo-auth-citizen": {"role": "citizen", "name": "Rahul Kumar", "id": "demo-citizen-001"},
    "demo-auth-merchant": {"role": "merchant", "name": "Priya Shops", "id": "demo-merchant-001"},
    "demo-auth-admin": {"role": "admin", "name": "Admin User", "id": "demo-admin-001"},
}


async def get_jwks() -> Dict:
    global JWKS_CACHE
    if JWKS_CACHE is not None:
        return JWKS_CACHE
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")
            response.raise_for_status()
            JWKS_CACHE = response.json()
            return JWKS_CACHE
    except Exception:
        # In demo/placeholder mode, return a minimal placeholder
        return {"keys": []}


def _decode_token_unverified(token: str) -> Dict[str, Any]:
    """Decode without verification for demo mode with placeholder keys."""
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True, "verify_aud": True},
        )
    except Exception:
        # Try RS256 fallback via JWKS
        raise


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # ── Demo mode bypass ──────────────────────────────────────────────────────
    # Tokens like "demo.citizen.1234567890" are accepted in DEMO_MODE=true
    if settings.DEMO_MODE and token.startswith("demo."):
        parts = token.split(".")
        role = parts[1] if len(parts) > 1 else "citizen"
        user_map = {
            "citizen": "demo-auth-citizen",
            "merchant": "demo-auth-merchant",
            "admin": "demo-auth-admin",
        }
        sub = user_map.get(role, "demo-auth-citizen")
        return {"sub": sub, "role": role, "demo": True}
    # ─────────────────────────────────────────────────────────────────────────

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
        return payload
    except JWTError:
        pass

    # Fallback: RS256 via JWKS
    try:
        jwks = await get_jwks()
        if jwks.get("keys"):
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
            if key:
                from jose.backends import RSAKey
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    audience="authenticated",
                )
                return payload
    except Exception as e:
        logger.warning("JWT RS256 verification failed", error=str(e))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_id(payload: Dict = Depends(verify_token)) -> str:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")
    return user_id


async def get_current_user_role(
    user_id: str = Depends(get_current_user_id),
) -> str:
    """Look up role from users table — not from JWT which doesn't carry it reliably."""
    if user_id in _role_cache:
        return _role_cache[user_id]

    try:
        from app.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        resp = supabase.table("users").select("role").eq("auth_user_id", user_id).maybe_single().execute()
        if resp.data:
            role = resp.data.get("role", "citizen")
            _role_cache[user_id] = role
            return role
    except Exception as e:
        logger.warning("Role lookup failed", error=str(e))

    return "citizen"