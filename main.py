import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.config import settings
from app.db import verify_database_startup
from app.graph_engine import graph_manager
from app.routes import router

app = FastAPI(
    title="NexusTrace — Criminal Network Analysis System",
    description="AI-Powered Criminal Network Analysis Prototype (SIH26189)",
    version="1.0.0"
)

# Enable CORS for local flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routes
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("  NexusTrace: AI-Powered Criminal Network Analysis (SIH26189)")
    print("=" * 60)
    try:
        status = verify_database_startup()
        print(f"[OK] Connected to MySQL database '{settings.MYSQL_DATABASE}'")
        for table, count in status["tables"].items():
            print(f"     - Table `{table}`: {count} rows")
        
        # Build initial graph
        g = graph_manager.build_graph()
        print(f"[OK] NetworkX graph initialized: {len(g.nodes)} nodes, {len(g.edges)} edges")
    except Exception as e:
        print(f"[WARN] Database startup check failed: {e}")
        print("Please verify MySQL is running and `schema_and_seed_data.sql` is imported.")
    print("=" * 60)

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
