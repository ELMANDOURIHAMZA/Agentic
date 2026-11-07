from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.admin_applications import router as admin_applications_router
from app.api.admin_dashboard import router as admin_dashboard_router
from app.api.admin_jobs import router as admin_jobs_router
from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.candidate import router as candidate_router
from app.api.public_jobs import router as public_jobs_router
from app.security.dependencies import is_html_request, safe_next_path
from app.services.presentation import criterion_label, format_score, severity_label

app = FastAPI(title="Agentic AI Recruitment Platform", version="0.1.0")
app.state.templates = Jinja2Templates(directory="app/templates")
app.state.templates.env.filters["criterion_label"] = criterion_label
app.state.templates.env.filters["score"] = format_score
app.state.templates.env.filters["severity"] = severity_label


@app.exception_handler(401)
async def unauthorized_handler(
    request: Request, _exception: Exception
) -> RedirectResponse | HTMLResponse:
    if is_html_request(request):
        next_path = safe_next_path(request.url.path)
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        return RedirectResponse(
            f"/login?next={next_path}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return JSONResponse(
        {"detail": "Authentication required"}, status_code=status.HTTP_401_UNAUTHORIZED
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(admin_jobs_router)
app.include_router(admin_applications_router)
app.include_router(admin_dashboard_router)
app.include_router(public_jobs_router)
app.include_router(applications_router)
app.include_router(candidate_router)
