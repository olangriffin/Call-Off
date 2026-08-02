import httpx
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.backend.core.config import get_settings
from app.backend.core.csrf import verified_form
from app.backend.core.auth import (
    CALL_OFF_SESSION_COOKIE,
    CALL_OFF_SESSION_NAME_COOKIE,
    CurrentOrganisationAccess,
    get_app_base_url,
    get_calloff_session,
    get_neon_auth_base_url,
)
from app.backend.frontend_templates import build_frontend_templates

templates = build_frontend_templates()

router = APIRouter(
    include_in_schema=False,
)

MAX_AUTH_EMAIL_LENGTH = 320
MAX_AUTH_NAME_LENGTH = 200
MAX_AUTH_PASSWORD_LENGTH = 1024


def auth_cookie_secure() -> bool:
    return get_settings().auth_cookie_secure


def public_registration_enabled() -> bool:
    return get_settings().allow_public_registration


def normalise_auth_email(value: object) -> str | None:
    email = str(value or "").strip()
    if not email or len(email) > MAX_AUTH_EMAIL_LENGTH:
        return None

    try:
        return validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def authentication_error_message(
    response: httpx.Response,
) -> str:
    if response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        return "The email address or password was not accepted."
    return "Authentication could not be completed. Please try again."


def extract_neon_session_cookie(
    response: httpx.Response,
) -> tuple[str, str] | None:
    for header in response.headers.get_list("set-cookie"):
        cookie_pair = header.split(";", 1)[0].strip()

        if "=" not in cookie_pair:
            continue

        cookie_name, cookie_value = cookie_pair.split(
            "=",
            1,
        )

        cookie_name = cookie_name.strip()
        cookie_value = cookie_value.strip()

        if "session_token" in cookie_name.lower() and cookie_value:
            if (
                len(cookie_value) >= 2
                and cookie_value.startswith('"')
                and cookie_value.endswith('"')
            ):
                cookie_value = cookie_value[1:-1]

            return cookie_name, cookie_value

    return None


@router.get(
    "/login",
    response_class=HTMLResponse,
)
def login_page(request: Request) -> HTMLResponse:
    registered = request.query_params.get("registered") == "1"

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "page_title": "Login",
            "company_name": "Call-Off",
            "form_values": {},
            "registration_enabled": public_registration_enabled(),
            "success_message": (
                "Account created. Verify your email if required, then sign in."
                if registered
                else None
            ),
        },
    )


@router.get(
    "/register",
    response_class=HTMLResponse,
)
def register_page(request: Request) -> HTMLResponse:
    if not public_registration_enabled():
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Registration unavailable",
                "company_name": "Call-Off",
                "registration_enabled": False,
                "form_values": {},
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={
            "page_title": "Create account",
            "company_name": "Call-Off",
            "registration_enabled": True,
            "form_values": {},
        },
    )


@router.post(
    "/register",
    response_class=HTMLResponse,
)
async def register(request: Request):
    if not public_registration_enabled():
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Registration unavailable",
                "company_name": "Call-Off",
                "registration_enabled": False,
                "form_values": {},
                "error_message": ("Registration is currently disabled."),
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )

    form = await verified_form(request)

    form_values = {
        "name": str(form.get("name", "")).strip(),
        "email": str(form.get("email", "")).strip(),
    }

    password = str(form.get("password", ""))
    confirm_password = str(form.get("confirm_password", ""))

    normalized_email = normalise_auth_email(form_values["email"])
    if normalized_email:
        form_values["email"] = normalized_email

    if not form_values["name"] or len(form_values["name"]) > MAX_AUTH_NAME_LENGTH:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Create account",
                "company_name": "Call-Off",
                "registration_enabled": True,
                "form_values": form_values,
                "error_message": "Enter a valid full name.",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if normalized_email is None:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Create account",
                "company_name": "Call-Off",
                "registration_enabled": True,
                "form_values": form_values,
                "error_message": "Enter a valid email address.",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Create account",
                "company_name": "Call-Off",
                "registration_enabled": True,
                "form_values": form_values,
                "error_message": ("The passwords do not match."),
            },
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
        )

    if not password or len(password) > MAX_AUTH_PASSWORD_LENGTH:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Create account",
                "company_name": "Call-Off",
                "registration_enabled": True,
                "form_values": form_values,
                "error_message": ("Enter a valid password."),
            },
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
        )

    app_base_url = get_app_base_url()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            auth_response = await client.post(
                (f"{get_neon_auth_base_url()}/sign-up/email"),
                headers={
                    "Origin": app_base_url,
                },
                json={
                    "name": form_values["name"],
                    "email": form_values["email"],
                    "password": password,
                    "callbackURL": (f"{app_base_url}/login?registered=1"),
                },
            )

    except httpx.RequestError:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Create account",
                "company_name": "Call-Off",
                "registration_enabled": True,
                "form_values": form_values,
                "error_message": ("The authentication service is unavailable."),
            },
            status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
        )

    if auth_response.status_code >= 400:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Create account",
                "company_name": "Call-Off",
                "registration_enabled": True,
                "form_values": form_values,
                "error_message": (authentication_error_message(auth_response)),
            },
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
        )

    return RedirectResponse(
        url="/login?registered=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/login",
    response_class=HTMLResponse,
)
async def login(request: Request):
    form = await verified_form(request)

    normalized_email = normalise_auth_email(form.get("email"))
    form_values = {
        "email": normalized_email or str(form.get("email", "")).strip(),
    }

    password = str(form.get("password", ""))

    if (
        normalized_email is None
        or not password
        or len(password) > MAX_AUTH_PASSWORD_LENGTH
    ):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "page_title": "Login",
                "company_name": "Call-Off",
                "registration_enabled": public_registration_enabled(),
                "form_values": form_values,
                "error_message": "Enter a valid email address and password.",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    app_base_url = get_app_base_url()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            auth_response = await client.post(
                (f"{get_neon_auth_base_url()}/sign-in/email"),
                headers={
                    "Origin": app_base_url,
                },
                json={
                    "email": form_values["email"],
                    "password": password,
                    "rememberMe": True,
                    "callbackURL": (f"{app_base_url}/app"),
                },
            )

    except httpx.RequestError:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "page_title": "Login",
                "company_name": "Call-Off",
                "registration_enabled": public_registration_enabled(),
                "form_values": form_values,
                "error_message": ("The authentication service is unavailable."),
            },
            status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
        )

    if auth_response.status_code >= 400:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "page_title": "Login",
                "company_name": "Call-Off",
                "registration_enabled": public_registration_enabled(),
                "form_values": form_values,
                "error_message": (authentication_error_message(auth_response)),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    session_cookie = extract_neon_session_cookie(auth_response)

    if session_cookie is None:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "page_title": "Login",
                "company_name": "Call-Off",
                "registration_enabled": public_registration_enabled(),
                "form_values": form_values,
                "error_message": (
                    "Authentication succeeded, but no session cookie was returned."
                ),
            },
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    neon_cookie_name, neon_cookie_value = session_cookie

    response = RedirectResponse(
        url="/app",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    response.set_cookie(
        key=CALL_OFF_SESSION_COOKIE,
        value=neon_cookie_value,
        httponly=True,
        secure=auth_cookie_secure(),
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )

    response.set_cookie(
        key=CALL_OFF_SESSION_NAME_COOKIE,
        value=neon_cookie_name,
        httponly=True,
        secure=auth_cookie_secure(),
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )

    return response


@router.post(
    "/logout",
)
async def logout(
    request: Request,
) -> RedirectResponse:
    await verified_form(request)
    try:
        cookie_name, cookie_value = get_calloff_session(request)

    except HTTPException:
        cookie_name = None
        cookie_value = None

    if cookie_name and cookie_value:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    (f"{get_neon_auth_base_url()}/sign-out"),
                    headers={
                        "Origin": get_app_base_url(),
                        "Cookie": (f"{cookie_name}={cookie_value}"),
                    },
                )

        except httpx.RequestError:
            pass

    response = RedirectResponse(
        url="/login",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    response.delete_cookie(
        key=CALL_OFF_SESSION_COOKIE,
        path="/",
        secure=auth_cookie_secure(),
        httponly=True,
        samesite="lax",
    )

    response.delete_cookie(
        key=CALL_OFF_SESSION_NAME_COOKIE,
        path="/",
        secure=auth_cookie_secure(),
        httponly=True,
        samesite="lax",
    )

    return response


@router.get(
    "/auth/context",
)
def auth_context(
    access: CurrentOrganisationAccess,
):
    return access
