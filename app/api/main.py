from fastapi import FastAPI, Request
from app.api.routes.routes import router
from app.api.routes.teams import team_router
from app.api.routes.jobs import job_router
import uvicorn
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI(title="RunForge API", description="Workload Automation Platform", version="1.0.0")
app.include_router(router, prefix="/api", tags=["API Endpoints"])
app.include_router(team_router, prefix="/api", tags=["Teams"])
app.include_router(job_router, prefix="/api", tags=["Jobs"])


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom exception handler for request validation errors.

    Args:
        request (Request): The incoming request.
        exc (RequestValidationError): The validation error that occurred.
    """
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


# Run the app using Python directly
if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000, reload=True)