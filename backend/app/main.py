from fastapi import FastAPI

app = FastAPI(
    title="Intelligent Cattle Management System API",
    description="Backend API for the ICMS mobile and web application.",
    version="0.1.0",
)


@app.get("/", tags=["General"])
def root():
    return {
        "message": "Welcome to the ICMS API",
        "version": "0.1.0",
    }


@app.get("/api/v1/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "ICMS Backend",
    }