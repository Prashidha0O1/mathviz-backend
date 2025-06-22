import asyncio
import hashlib
import os
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.schemas.schemas import QuestionRequest
from app.services.animation_service import generate_animation_video, send_status_update
from app.main import redis_client, generation_lock

router = APIRouter()

@router.post("/ask", response_class=FileResponse)
async def ask_question(request: QuestionRequest):
    question = request.question.strip().lower()
    cache_key = f"mathviz:{hashlib.md5(question.encode()).hexdigest()}"

    # Check cache first
    cached_path = redis_client.get(cache_key)
    if cached_path and os.path.exists(cached_path):
        return FileResponse(cached_path, media_type="video/mp4", filename="animation.mp4")

    if generation_lock.locked():
        raise HTTPException(status_code=429, detail="Server is busy. Please try again in a moment.")

    async with generation_lock:
        try:
            # Re-check cache inside lock in case a request finished while waiting
            cached_path = redis_client.get(cache_key)
            if cached_path and os.path.exists(cached_path):
                return FileResponse(cached_path, media_type="video/mp4", filename="animation.mp4")

            final_video_path = await generate_animation_video(question)
            redis_client.set(cache_key, final_video_path, ex=86400)  # Cache for 24 hours
            return FileResponse(final_video_path, media_type="video/mp4", filename="animation.mp4")
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
        if payload.get("type") != "question" or "data" not in payload:
            await send_status_update(websocket, "Error: Invalid payload.")
            return

        question = payload["data"].strip().lower()
        if generation_lock.locked():
            await send_status_update(websocket, "Error: Server is busy. Please try again later.")
            return

        async with generation_lock:
            # We don't use cache for WebSocket to always show the progress
            final_video_path = await generate_animation_video(question, websocket=websocket)
            cache_key = f"mathviz:{hashlib.md5(question.encode()).hexdigest()}"
            redis_client.set(cache_key, final_video_path, ex=86400)
            await websocket.send_json({"status": "complete", "detail": "Video is ready to be fetched."})

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await send_status_update(websocket, f"An error occurred: {str(e)[:100]}")
    finally:
        if websocket.client_state.name != 'DISCONNECTED':
            await websocket.close()