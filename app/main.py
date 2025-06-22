import os
import asyncio
import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.v1 import animation_routes

# Load environment variables from .env file
load_dotenv()

# --- App Initialization ---
app = FastAPI(
    title="MathViz AI Backend",
    description="Backend for generating Manim animations from user questions.",
    version="1.0.0",
)

# --- Shared Resources ---
# Concurrency lock to allow only one video generation at a time
generation_lock = asyncio.Lock()

# Redis client for caching
try:
    redis_client = redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True
    )
    redis_client.ping()
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis: {e}. Caching will be disabled.")
    # A simple dictionary-based fallback cache if Redis is not available
    class FallbackCache:
        def __init__(self):
            self._cache = {}
        def get(self, key):
            return self._cache.get(key)
        def set(self, key, value, ex=None):
            self._cache[key] = value
    redis_client = FallbackCache()

# --- CORS Configuration ---
origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
origins = [origin.strip() for origin in origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# --- API Router ---
app.include_router(animation_routes.router, prefix="/api/v1", tags=["Animation"])

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the MathViz AI Backend"}