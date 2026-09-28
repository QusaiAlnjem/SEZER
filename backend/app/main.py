from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, creditors, suppliers, storage, dashboard, expenses, fx

app = FastAPI(title="SEZER API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(creditors.router)
app.include_router(suppliers.router)
app.include_router(storage.router)
app.include_router(expenses.router)
app.include_router(fx.router)


@app.get("/api/health")
def health():
    return {"ok": True, "app": "SEZER", "version": "1.0.0"}
