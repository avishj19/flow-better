"""Optional Auth0 access-token gate for the recovery desk.

When AUTH0_DOMAIN, AUTH0_AUDIENCE and AUTH0_CLIENT_ID are all set, every
non-public /api route requires a validated access token. Desk isolation then
comes from the token (Organization slug, namespaced desk claim, or a
per-user workspace) rather than the spoofable X-IROP-Desk header.

Local demo mode is unchanged when those variables are unset.
"""
from __future__ import annotations

import hashlib
import os
import re
from contextvars import ContextVar
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from . import store

DESK_CLAIM = 'https://flowbetter.app/desk'
PUBLIC_API = {'/api/status', '/api/auth/config'}
DESK_SCOPES = (
    'read:scenarios',
    'write:scenarios',
    'approve:recovery',
    'fetch:observations',
)
_claims: ContextVar[dict | None] = ContextVar('auth_claims', default=None)
_auth0 = None
_verify = None


class AuthError(Exception):
    def __init__(self, status: int, detail: dict, headers: dict | None = None):
        self.status = status
        self.detail = detail
        self.headers = headers or {}
        super().__init__(detail.get('error_description') or detail.get('error') or 'auth error')


def enabled() -> bool:
    return bool(
        os.getenv('AUTH0_DOMAIN', '').strip()
        and os.getenv('AUTH0_AUDIENCE', '').strip()
        and os.getenv('AUTH0_CLIENT_ID', '').strip()
    )


def reset() -> None:
    global _auth0
    _auth0 = None
    _claims.set(None)


def set_claims(claims: dict | None) -> None:
    _claims.set(claims)


def current_claims() -> dict | None:
    return _claims.get()


def actor(claims: dict | None = None) -> dict | None:
    claims = claims if claims is not None else current_claims()
    if not claims or not claims.get('sub'):
        return None
    return {
        'sub': claims.get('sub'),
        'org_id': claims.get('org_id'),
        'org_name': claims.get('org_name'),
    }


def public_identity(claims: dict) -> dict:
    return {
        'sub': claims.get('sub'),
        'org_id': claims.get('org_id'),
        'org_name': claims.get('org_name'),
    }


def public_config() -> dict:
    if not enabled():
        return {'enabled': False}
    domain = os.environ['AUTH0_DOMAIN'].replace('https://', '').rstrip('/')
    return {
        'enabled': True,
        'domain': domain,
        'audience': os.environ['AUTH0_AUDIENCE'],
        'client_id': os.environ['AUTH0_CLIENT_ID'],
        'organization': os.getenv('AUTH0_ORGANIZATION', '').strip() or None,
        'scopes': list(DESK_SCOPES),
    }


def permissions(claims: dict) -> set[str]:
    scopes = set((claims.get('scope') or '').split())
    extra = claims.get('permissions') or []
    if isinstance(extra, str):
        extra = extra.split()
    scopes.update(extra)
    return scopes


def desk_for(claims: dict) -> str:
    org = claims.get('org_name') or claims.get('org_id')
    if org:
        slug = re.sub(r'[^a-z0-9_-]+', '-', str(org).lower()).strip('-')[:64]
        if store.DESK_RE.match(slug):
            return slug
    custom = claims.get(DESK_CLAIM)
    if custom:
        return store.normalize_desk(str(custom))
    digest = hashlib.sha256(str(claims.get('sub') or 'anonymous').encode()).hexdigest()[:12]
    return f'u-{digest}'


def is_public(path: str) -> bool:
    return path in PUBLIC_API or not path.startswith('/api/')


def required_scopes(path: str, method: str) -> tuple[str, ...]:
    method = method.upper()
    if is_public(path) or path == '/api/auth/me':
        return ()
    if path == '/api/observations' and method == 'POST':
        return ('fetch:observations',)
    if path.endswith('/approve') and method == 'POST':
        return ('approve:recovery',)
    if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return ('write:scenarios',)
    return ('read:scenarios',)


def require_scopes(claims: dict, needed: tuple[str, ...]) -> None:
    if not needed:
        return
    have = permissions(claims)
    missing = [scope for scope in needed if scope not in have]
    if missing:
        raise AuthError(
            403,
            {
                'error': 'insufficient_scope',
                'error_description': 'Missing permission: ' + ', '.join(missing),
            },
        )


def get_auth0():
    global _auth0
    if _auth0 is None:
        from fastapi_plugin import Auth0FastAPI

        domain = os.environ['AUTH0_DOMAIN'].replace('https://', '').rstrip('/')
        _auth0 = Auth0FastAPI(
            domain=domain,
            audience=os.environ['AUTH0_AUDIENCE'],
            dpop_enabled=False,
        )
    return _auth0


async def verify_access_token(request: Request) -> dict:
    if _verify is not None:
        return await _verify(request)
    try:
        return await get_auth0().require_auth()(request)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {'error': 'invalid_token', 'error_description': str(exc.detail)}
        raise AuthError(exc.status_code, detail, exc.headers)


async def authenticate(request: Request) -> dict:
    claims = await verify_access_token(request)
    if not isinstance(claims, dict) or not claims.get('sub'):
        raise AuthError(401, {'error': 'invalid_token', 'error_description': 'Access token is missing a subject'})
    require_scopes(claims, required_scopes(request.url.path, request.method))
    return claims


def error_response(exc: AuthError) -> JSONResponse:
    headers = dict(exc.headers or {})
    if exc.status in (400, 401) and 'www-authenticate' not in {k.lower() for k in headers}:
        headers['WWW-Authenticate'] = 'Bearer'
    return JSONResponse(status_code=exc.status, content={'detail': exc.detail}, headers=headers)


def attach_actor(data: dict[str, Any] | None = None) -> dict:
    payload = dict(data or {})
    who = actor()
    if who:
        payload['actor'] = who
    return payload
