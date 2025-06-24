# MathViz AI Backend

A FastAPI backend for generating Manim animations from user questions.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (optional):
   - Create a `.env` file with:
     - `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)
     - `CORS_ORIGINS`: Allowed CORS origins (default: http://localhost:3000)

## Running the Application

### Method 1: Using uvicorn directly
```bash
uvicorn main:app --reload
```

### Method 2: Using Python
```bash
python main.py
```

The application will be available at `http://127.0.0.1:8000`

## API Endpoints

- `GET /`: Root endpoint
- `POST /api/v1/ask`: Submit a question to generate an animation
- `WebSocket /api/v1/ws`: WebSocket endpoint for real-time status updates

## Features

- Redis caching for generated videos
- Concurrency control (only one video generation at a time)
- WebSocket support for real-time progress updates
- CORS middleware for frontend integration 