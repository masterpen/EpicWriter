from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import books, workflow, auth, config, styles
from app.core.config import settings


app = FastAPI(
    title="EpicWriter OS API",
    description="Backend for EpicWriter - AI Novel Writing System",
    version="1.0.0"
)

# CORS - restrict in production
if settings.APP_ENV == "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routes
print("Registering routes...")
app.include_router(auth.router)
app.include_router(books.router, prefix="/api/books", tags=["Books"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["Workflow"])
app.include_router(config.router, tags=["Config"])
app.include_router(styles.router, prefix="/api/styles", tags=["Styles"])
print("Routes registered")

@app.get("/")
async def root():
    return {"message": "EpicWriter API is running 🚀"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
