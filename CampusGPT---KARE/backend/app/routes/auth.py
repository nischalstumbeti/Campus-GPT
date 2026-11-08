"""Authentication routes."""
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import secrets
import httpx

from app.config import get_settings
from app.utils.database import get_db
from app.utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    get_current_user,
)
from app.utils.rate_limit import check_rate_limit, client_key
from app.models.user import User, Role
from app.services import email_service as mail
from app.services import uis_client

router = APIRouter()


def _settings():
    return get_settings()


def _gpt_role(uis_role: str) -> Role:
    if uis_role in ("university_admin", "admin", "super_admin"):
        return Role.ADMIN
    if uis_role == "hostel_admin":
        return Role.HOSTEL_ADMIN
    if uis_role in ("faculty", "hod", "department_admin", "exam_admin", "staff"):
        return Role.FACULTY
    return Role.STUDENT


async def _upsert_from_uis(db: AsyncSession, ident: dict, password: str | None = None) -> User:
    email = (ident.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="UIS account has no email")
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    role = _gpt_role(str(ident.get("role") or "student"))
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash(password or secrets.token_urlsafe(24)),
            full_name=ident.get("full_name") or email.split("@")[0],
            role=role,
            uis_username=ident.get("username"),
        )
        db.add(user)
        await db.flush()
    else:
        user.uis_username = ident.get("username") or user.uis_username
        if ident.get("full_name"):
            user.full_name = ident["full_name"]
        if password:
            user.hashed_password = get_password_hash(password)
        user.role = role
        await db.flush()
    return user


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "student"
    full_name: str = ""
    email: str = ""


def _reset_token(user_id: int) -> str:
    return create_access_token(
        {"sub": str(user_id), "purpose": "password_reset"},
        expires_delta=timedelta(hours=1),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    check_rate_limit(client_key(request, "login"), limit=20, window_seconds=60)
    identifier = (data.email or "").strip()
    ident = None
    uis_auth_failed = False

    # Resolve local account first so we can authenticate with linked UIS username
    # (Campus-GPT email is often not a valid UIS login id).
    local_user = (
        await db.execute(select(User).where(User.email == identifier))
    ).scalar_one_or_none()

    if uis_client.uis_enabled():
        uis_login_id = None
        if local_user and local_user.uis_username:
            uis_login_id = local_user.uis_username
        elif "@" not in identifier:
            # Allow direct UIS username login from the email field
            uis_login_id = identifier
        else:
            # Try email → UIS identity map, then credentials
            try:
                linked = await uis_client.resolve_identity_by_email(identifier)
                if linked and linked.get("username"):
                    uis_login_id = linked["username"]
            except Exception:
                uis_login_id = None

        if uis_login_id:
            try:
                ident = await uis_client.verify_credentials(uis_login_id, data.password)
            except uis_client.UisClientError as exc:
                if exc.status_code == 401:
                    # Known UIS identity rejected password — fail closed (no stale local hash)
                    uis_auth_failed = True
                ident = None

    # When UIS explicitly rejects credentials for a known identity, do not fall back
    if uis_auth_failed:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = None
    if ident:
        user = await _upsert_from_uis(db, ident, data.password)
    else:
        user = local_user
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.uis_username and uis_client.uis_enabled():
            try:
                linked = await uis_client.resolve_identity_by_email(user.email)
                if linked and linked.get("username"):
                    user.uis_username = linked["username"]
                    await db.flush()
            except Exception:
                pass

    from app.services.consent import log_audit
    await log_audit(db, user.id, "login", user.email)
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "full_name": user.full_name or "",
            "email": user.email,
        }
    )
    background_tasks.add_task(mail.send_login_activity_email, user.email, user.full_name or "")
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name or "",
        email=user.email,
    )


@router.post("/register", response_model=TokenResponse)
async def register(
    data: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name or data.email.split("@")[0],
        role=Role.STUDENT,
    )
    db.add(user)
    await db.flush()
    ident = await uis_client.resolve_identity_by_email(user.email)
    if ident and ident.get("username"):
        user.uis_username = ident["username"]
        if ident.get("full_name"):
            user.full_name = ident["full_name"]
        user.role = _gpt_role(str(ident.get("role") or "student"))
        await db.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "full_name": user.full_name or "",
            "email": user.email,
        }
    )
    background_tasks.add_task(
        mail.send_welcome_email, user.email, user.full_name or "", user.role.value
    )
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name or "",
        email=user.email,
    )


async def _resolve_residence(db: AsyncSession, u: User) -> tuple[str, bool]:
    """Return (residence_type, is_hosteller). Types: hostel | day_scholar | bus."""
    # Prefer UIS allocation (source of truth)
    if u.uis_username and uis_client.uis_enabled():
        try:
            payload = await uis_client.get_residence(u.uis_username)
            residence = str(payload.get("residence") or "day_scholar").lower()
            if residence not in ("hostel", "day_scholar", "bus"):
                residence = "day_scholar"
            is_hosteller = bool(payload.get("is_hosteller")) or residence == "hostel"
            return residence, is_hosteller
        except Exception:
            pass

    # Optional local SIS fallback (disabled by default — residence comes from UIS DB)
    from app.config import get_settings

    if get_settings().ALLOW_LOCAL_SIS_FALLBACK:
        try:
            from app.models.academic import StudentProfile
            from app.models.privacy import HostelProfile
            from app.models.fees import StudentFee

            profile = (
                await db.execute(select(StudentProfile).where(StudentProfile.user_id == u.id))
            ).scalar_one_or_none()
            if profile:
                hp = (
                    await db.execute(select(HostelProfile).where(HostelProfile.student_id == profile.id))
                ).scalar_one_or_none()
                if hp:
                    return "hostel", True
            bus = (
                await db.execute(
                    select(StudentFee.id).where(StudentFee.user_id == u.id, StudentFee.category == "bus").limit(1)
                )
            ).scalar_one_or_none()
            if bus:
                return "bus", False
        except Exception:
            pass
    return "day_scholar", False


@router.get("/me")
async def me(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    if not str(user.get("sub", "")).isdigit():
        raise HTTPException(status_code=401, detail="Invalid session")
    result = await db.execute(select(User).where(User.id == int(user["sub"])))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=401, detail="User not found")
    # Best-effort UIS auto-link
    if not u.uis_username:
        ident = await uis_client.resolve_identity_by_email(u.email)
        if ident and ident.get("username"):
            u.uis_username = ident["username"]
            await db.flush()
    residence, is_hosteller = "day_scholar", False
    if u.role == Role.STUDENT:
        residence, is_hosteller = await _resolve_residence(db, u)
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name or "",
        "role": u.role.value,
        "uis_username": u.uis_username,
        "uis_linked": bool(u.uis_username),
        "residence_type": residence,
        "is_hosteller": is_hosteller,
    }


class LinkUisRequest(BaseModel):
    uis_username: str


class UisExchangeRequest(BaseModel):
    uis_token: str


@router.post("/uis-exchange", response_model=TokenResponse)
async def uis_exchange(
    data: UisExchangeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Turn a UIS JWT into a Campus-GPT session (SSO)."""
    ident = await uis_client.verify_session(data.uis_token)
    if not ident:
        raise HTTPException(status_code=401, detail="Invalid or expired UIS session")
    user = await _upsert_from_uis(db, ident)
    from app.services.consent import log_audit
    await log_audit(db, user.id, "login", user.email)
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "full_name": user.full_name or "",
            "email": user.email,
        }
    )
    background_tasks.add_task(mail.send_login_activity_email, user.email, user.full_name or "")
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name or "",
        email=user.email,
    )


@router.post("/link-uis")
async def link_uis(
    data: LinkUisRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Link Campus-GPT login to a UIS username — only when email identity matches."""
    if not str(user.get("sub", "")).isdigit():
        raise HTTPException(status_code=401, detail="Invalid session")
    u = (await db.execute(select(User).where(User.id == int(user["sub"])))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=401, detail="User not found")
    username = data.uis_username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="Invalid UIS username")
    from app.services import uis_client

    ident = await uis_client.resolve_identity_by_email(u.email)
    if not ident or not ident.get("username"):
        raise HTTPException(
            status_code=400,
            detail="No UIS account found for your email. Create the student in UIS with the same email first.",
        )
    if ident["username"].lower() != username.lower():
        raise HTTPException(
            status_code=403,
            detail=f"UIS username must match your email-linked account ({ident['username']}).",
        )
    u.uis_username = ident["username"]
    if ident.get("full_name"):
        u.full_name = ident["full_name"]
    await db.flush()
    return {"ok": True, "uis_username": u.uis_username, "uis_linked": True}


class DemoLoginIn(BaseModel):
    role: str = "student"


@router.post("/demo-login")
async def demo_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    body: DemoLoginIn | None = None,
):
    """Demo login — only when ALLOW_PUBLIC_DEMO is enabled; uses the seeded role account."""
    from app.config import get_settings

    check_rate_limit(client_key(request, "demo-login"), limit=10, window_seconds=60)
    settings = get_settings()
    if settings.ENVIRONMENT.lower() == "production" or not settings.ALLOW_PUBLIC_DEMO:
        raise HTTPException(status_code=403, detail="Demo login disabled")
    wanted = (body.role if body else "student").strip().lower()
    preferred = {
        "student": ("student.demo@klu.ac.in", "student@example.com"),
        "faculty": ("faculty.demo@klu.ac.in", "faculty@example.com"),
        "admin": ("admin.demo@klu.ac.in", "admin@example.com"),
        "super_admin": ("admin.demo@klu.ac.in", "admin@example.com"),
    }
    user = None
    for email in preferred.get(wanted, ("student@example.com",)):
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user:
            break
    if not user:
        raise HTTPException(status_code=404, detail="Demo account not seeded")
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "full_name": user.full_name or "",
            "email": user.email,
        }
    )
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name or "",
        email=user.email,
    )


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request password reset. Always returns success (prevents email enumeration)."""
    check_rate_limit(client_key(request, "forgot-password"), limit=10, window_seconds=300)
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    sent = False
    if user:
        token = _reset_token(user.id)
        settings = get_settings()
        if settings.EMAIL_ENABLED and settings.SMTP_USER and settings.SMTP_PASSWORD:
            background_tasks.add_task(
                mail.send_password_reset_email, user.email, user.full_name or "", token
            )
            sent = True
        elif settings.ENVIRONMENT.lower() != "production":
            # Local/dev only: return token so reset still works without SMTP
            return {
                "message": "Email is not configured. Use this reset token in the reset form.",
                "dev_reset_token": token,
            }
    return {
        "message": (
            "If an account exists, you will receive reset instructions."
            if sent or user is None
            else "If an account exists, you will receive reset instructions."
        )
    }


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(data.token)
    if not payload or payload.get("purpose") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    sub = payload.get("sub")
    if not sub or not str(sub).isdigit():
        raise HTTPException(status_code=400, detail="Invalid reset token")
    user = (await db.execute(select(User).where(User.id == int(sub)))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    user.hashed_password = get_password_hash(data.new_password)
    # Sync to UIS SoR so linked login (UIS-first) accepts the new password
    if user.uis_username and uis_client.uis_enabled():
        try:
            await uis_client.service_set_password(user.uis_username, data.new_password)
        except uis_client.UisClientError as exc:
            raise HTTPException(
                status_code=502,
                detail=exc.detail or "Password updated locally but UIS sync failed — try again or use UIS settings.",
            ) from exc
    await db.flush()
    background_tasks.add_task(mail.send_password_changed_email, user.email, user.full_name or "")
    return {"message": "Password updated. You can sign in with your new password."}


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Logged-in user changes password; syncs to UIS SoR when the account is linked."""
    from app.services.uis_link import linked_uis_username

    if not str(user.get("sub", "")).isdigit():
        raise HTTPException(status_code=401, detail="Invalid session")
    uid = int(user["sub"])
    row = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")

    uis_user = await linked_uis_username(db, user)
    synced = False
    if uis_user and uis_client.uis_enabled():
        try:
            await uis_client.change_password(
                uis_user,
                current_password=data.current_password,
                new_password=data.new_password,
            )
            synced = True
        except uis_client.UisClientError as exc:
            # If UIS rejects current password, fail; otherwise keep local update path
            if exc.status_code in (400, 401, 403):
                raise HTTPException(
                    status_code=400,
                    detail=exc.detail or "Could not update password in UIS",
                ) from exc

    if not synced and not verify_password(data.current_password, row.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    row.hashed_password = get_password_hash(data.new_password)
    await db.flush()
    from app.services.audit_log import write_audit

    await write_audit(
        db,
        user=user,
        action="CHANGE_PASSWORD",
        resource="auth",
        detail=f"synced_to_uis={synced}",
    )
    if row.email:
        background_tasks.add_task(mail.send_password_changed_email, row.email, row.full_name or "")
    return {
        "ok": True,
        "message": (
            "Password updated and synced to KARE UIS (admin SoR)."
            if synced
            else "Password updated."
        ),
        "synced_to_uis": synced,
        "source": "UIS" if synced else "local",
    }


def _allowed_google_domain() -> str:
    return (getattr(_settings(), "GOOGLE_ALLOWED_DOMAIN", None) or "klu.ac.in").strip().lower()


def _is_allowed_institutional_email(email: str) -> bool:
    domain = _allowed_google_domain()
    email_norm = (email or "").strip().lower()
    return bool(email_norm) and email_norm.endswith(f"@{domain}")


@router.get("/google")
async def google_login():
    """Redirect to Google OAuth (hosted domain hint: @klu.ac.in)."""
    settings = _settings()
    frontend_url = settings.FRONTEND_URL
    if not settings.GOOGLE_CLIENT_ID:
        return RedirectResponse(f"{frontend_url}/login?error=google_not_configured")
    redirect_uri = f"{settings.API_BASE_URL.rstrip('/')}/api/auth/google/callback"
    state = create_access_token(
        {"purpose": "oauth_state", "nonce": secrets.token_urlsafe(16)},
        expires_delta=timedelta(minutes=15),
    )
    params = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
            # Google account chooser prefers this Workspace/school domain
            "hd": _allowed_google_domain(),
        }
    )
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(
    background_tasks: BackgroundTasks,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback, create/find user, redirect with token."""
    settings = _settings()
    frontend_url = settings.FRONTEND_URL or "http://localhost:3001"
    if error or not code:
        return RedirectResponse(f"{frontend_url}/login?error=access_denied")
    state_payload = decode_token(state or "")
    if not state_payload or state_payload.get("purpose") != "oauth_state":
        return RedirectResponse(f"{frontend_url}/login?error=invalid_state")
    if not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse(f"{frontend_url}/login?error=google_not_configured")
    redirect_uri = f"{settings.API_BASE_URL.rstrip('/')}/api/auth/google/callback"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code != 200:
        return RedirectResponse(f"{frontend_url}/login?error=token_exchange_failed")
    token_data = r.json()
    access = token_data.get("access_token")
    if not access:
        return RedirectResponse(f"{frontend_url}/login?error=no_token")
    async with httpx.AsyncClient() as client:
        u = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access}"},
        )
    if u.status_code != 200:
        return RedirectResponse(f"{frontend_url}/login?error=userinfo_failed")
    info = u.json()
    email = (info.get("email") or "").strip().lower()
    name = info.get("name", "") or info.get("given_name", "")
    if not email:
        return RedirectResponse(f"{frontend_url}/login?error=no_email")
    # Enforce institutional domain server-side (hd= is only a UI hint)
    if not _is_allowed_institutional_email(email):
        return RedirectResponse(f"{frontend_url}/login?error=domain_not_allowed")
    if info.get("verified_email") is False:
        return RedirectResponse(f"{frontend_url}/login?error=email_not_verified")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_new = False
    if not user:
        is_new = True
        user = User(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            full_name=name,
            role=Role.STUDENT,
        )
        db.add(user)
        await db.flush()
    if is_new:
        background_tasks.add_task(
            mail.send_welcome_email, user.email, user.full_name or "", user.role.value
        )
    else:
        background_tasks.add_task(mail.send_login_activity_email, user.email, user.full_name or "")
    if not user.uis_username:
        ident = await uis_client.resolve_identity_by_email(user.email)
        if ident and ident.get("username"):
            user.uis_username = ident["username"]
            await db.flush()
    jwt_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "full_name": user.full_name or "",
            "email": user.email,
        }
    )
    # Hash fragment avoids putting the bearer token in server/proxy query logs
    return RedirectResponse(f"{frontend_url}/login#token={jwt_token}")
