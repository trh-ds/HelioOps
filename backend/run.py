"""Launch the HelioOps backend server."""

from backend.config import settings

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=settings.WORKERS,
    )