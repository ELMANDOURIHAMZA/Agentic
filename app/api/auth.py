from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole
from app.security.auth import (
    cookie_secure,
    create_auth_token,
    csrf_token_for,
    hash_password,
    is_login_allowed,
    new_csrf_token,
    read_auth_token,
    record_login_attempt,
    session_max_age,
    set_csrf_cookie,
    validate_email,
    validate_password_strength,
    verify_password,
)
from app.security.dependencies import safe_next_path

router = APIRouter()


def _template(request: Request, name: str, **context: object) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(request, name, context)


def _csrf_is_valid(request: Request, csrf_token: str) -> bool:
    cookie_token = request.cookies.get("csrf_token")
    return bool(cookie_token and csrf_token and cookie_token == csrf_token)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    csrf_token = csrf_token_for(request)
    response = _template(request, "register.html", csrf_token=csrf_token, error=None)
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not _csrf_is_valid(request, csrf_token):
        return HTMLResponse("CSRF validation failed", status_code=status.HTTP_403_FORBIDDEN)
    if not validate_email(email) or not validate_password_strength(password):
        return _template(
            request,
            "register.html",
            csrf_token=csrf_token,
            error="Informations d'inscription invalides.",
        )
    user = User(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=UserRole.CANDIDATE,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _template(
            request,
            "register.html",
            csrf_token=csrf_token,
            error="Impossible de créer ce compte.",
        )
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/") -> HTMLResponse:
    csrf_token = csrf_token_for(request)
    response = _template(
        request, "login.html", csrf_token=csrf_token, error=None, next=safe_next_path(next)
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
    next: str = Form("/"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not _csrf_is_valid(request, csrf_token):
        return HTMLResponse("CSRF validation failed", status_code=status.HTTP_403_FORBIDDEN)
    client_host = request.client.host if request.client else "unknown"
    client_key = f"{client_host}:{email.strip().lower()}"
    if not is_login_allowed(client_key):
        return _template(
            request,
            "login.html",
            csrf_token=csrf_token,
            error="Identifiants invalides.",
            next=safe_next_path(next),
        )
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    valid = user is not None and verify_password(user.password_hash, password)
    record_login_attempt(client_key)
    if not valid:
        return _template(
            request,
            "login.html",
            csrf_token=csrf_token,
            error="Identifiants invalides.",
            next=safe_next_path(next),
        )
    auth_csrf = new_csrf_token()
    response = RedirectResponse(safe_next_path(next), status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        "auth_token",
        create_auth_token(user.id, auth_csrf, user.session_version),
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        max_age=session_max_age(),
    )
    set_csrf_cookie(response, auth_csrf)
    return response


@router.post("/logout")
def logout(
    request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    # Double-submit : le jeton du formulaire doit égaler le cookie ``csrf_token``,
    # que chaque page renouvelle ; on ne le compare pas au jeton signé de session.
    cookie_token = request.cookies.get("csrf_token")
    if not csrf_token or csrf_token != cookie_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    token = request.cookies.get("auth_token")
    payload = read_auth_token(token) if token else None
    if payload is not None:
        user = db.get(User, int(payload["user_id"]))
        if user is not None:  # révocation serveur : tout jeton déjà émis devient invalide
            user.session_version += 1
            db.commit()
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("auth_token")
    response.delete_cookie("csrf_token")
    return response
