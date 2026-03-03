from fastapi import FastAPI
import uvicorn
from app.routes.cv_routes import router as cv_router
from app.routes.health_routes import router as health_router

app = FastAPI(
    title="CV Automation Workflow API",
    description="Backend API for automating CV generation and management",
    version="1.0.0",
)

app.include_router(health_router)
app.include_router(cv_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)