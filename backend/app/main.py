from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from routes.cv_routes import router as cv_router
from routes.users import router as users_router
from routes.admin import router as admin_router
from routes.webhook import router as webhook_router
from database import init_db

app = FastAPI(
    title="CV Automation Workflow API",
    description="Backend API for automating CV generation and management",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.include_router(cv_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(webhook_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)