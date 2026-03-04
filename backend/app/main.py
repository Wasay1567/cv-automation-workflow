from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from app.routes.cv_routes import router as cv_router

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

app.include_router(cv_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)