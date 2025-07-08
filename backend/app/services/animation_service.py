import os
import re
import subprocess
import tempfile
import uuid
import logging
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from fastapi import WebSocket, HTTPException

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")
genai.configure(api_key=GEMINI_API_KEY)
generation_config = {"temperature": 0.3, "max_output_tokens": 4096}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
ai_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings,
)

# --- Security Validation ---
DANGEROUS_KEYWORDS = [
    "os", "sys", "subprocess", "shutil", "requests", "socket", "urllib",
    "eval", "exec", "open", "input", "ctypes", "pickle", "glob",
]
DANGEROUS_PATTERN = re.compile(r'\b(' + '|'.join(DANGEROUS_KEYWORDS) + r')\b')

def validate_manim_code(code: str):
    if DANGEROUS_PATTERN.search(code):
        keyword = DANGEROUS_PATTERN.search(code).group(1)
        logger.warning(f"Validation failed: unsafe keyword '{keyword}' found.")
        raise HTTPException(status_code=400, detail=f"Generated code contains disallowed keyword: '{keyword}'.")
    if "class GeneratedScene(Scene):" not in code:
        raise HTTPException(status_code=500, detail="AI failed to generate a valid Manim scene named 'GeneratedScene'.")
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=500, detail=f"AI-generated code is not valid Python: {e}")
    logger.info("Generated code passed security validation.")

async def send_status_update(websocket: Optional[WebSocket], message: str):
    logger.info(message)
    if websocket:
        await websocket.send_json({"status": message})

async def get_manim_code_from_ai(question: str) -> str:
    import os
    template_path = os.path.join(os.path.dirname(__file__), "prompt_template.txt")
    with open(template_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
    # Insert the user question at the end for context
    prompt = f"{prompt_template}\n\nUser request: {question}\n"
    try:
        response = await ai_model.generate_content_async(prompt)
        code = response.text
        # Optionally, you can parse for <code>...</code> or <plainResponse>...</plainResponse> here
        return code
    except Exception as e:
        logger.error(f"Error calling AI model: {e}")
        raise HTTPException(status_code=500, detail=f"AI model failed to generate code: {e}")

async def generate_animation_video(question: str, websocket: Optional[WebSocket] = None) -> str:
    temp_dir = tempfile.mkdtemp()
    try:
        await send_status_update(websocket, "Generating animation script...")
        manim_code = await get_manim_code_from_ai(question)
        
        await send_status_update(websocket, "Validating generated script...")
        validate_manim_code(manim_code)

        script_path = Path(temp_dir) / "generated_scene.py"
        script_path.write_text(manim_code)

        await send_status_update(websocket, "Rendering animation with Manim...")
        
        # Minimal Manim command to avoid parameter conflicts
        manim_cmd = [
            "manim",
            str(script_path),
            "GeneratedScene",
            "-ql",
            "--format", "mp4",
            "--media_dir", str(temp_dir),
            "--disable_caching",
        ]


        
        logger.info(f"Running Manim command: {' '.join(manim_cmd)}")
        process = subprocess.run(manim_cmd, capture_output=True, text=True, cwd=temp_dir, timeout=120)
        
        if process.returncode != 0:
            error_output = process.stderr or process.stdout
            logger.error(f"Manim rendering failed:\n{error_output}")
            raise HTTPException(status_code=500, detail=f"Manim rendering failed: {error_output[:500]}")
        
        # More flexible path checking for Manim output (default quality paths)
        possible_paths = [
            Path(temp_dir) / "videos" / "generated_scene" / "1080p60" / "GeneratedScene.mp4",
            Path(temp_dir) / "videos" / "generated_scene" / "720p30" / "GeneratedScene.mp4", 
            Path(temp_dir) / "videos" / "generated_scene" / "480p15" / "GeneratedScene.mp4",
            Path(temp_dir) / "videos" / "GeneratedScene.mp4",
        ]
        
        logger.info(f"Got question: {question}")
        logger.info(f"Manim code:\n{manim_code}")
        logger.info(f"Temp dir created at: {temp_dir}")
        logger.info(f"Checking possible output paths...")
        logger.info(f"FFmpeg started...")

        raw_video_path = None
        for path in possible_paths:
            if path.exists():
                raw_video_path = path
                break
        
        if not raw_video_path:
            # List all files in temp_dir for debugging
            all_files = list(Path(temp_dir).rglob("*.mp4"))
            logger.error(f"Video files found: {all_files}")
            raise HTTPException(status_code=500, detail=f"Manim output video not found. Available files: {all_files}")

        await send_status_update(websocket, "Encoding video for web delivery...")
        final_video_name = f"{uuid.uuid4()}.mp4"
        cache_dir = Path("backend/video_cache")
        cache_dir.mkdir(exist_ok=True)
        final_video_path = str(cache_dir / final_video_name)

        # Improved FFmpeg command with better error handling
        ffmpeg_cmd = [
            "ffmpeg", "-y", 
            "-i", str(raw_video_path), 
            "-vcodec", "libx264", 
            "-preset", "fast", 
            "-crf", "24", 
            "-vf", "scale=320:-2",
            "-movflags", "+faststart",  # Optimize for web streaming
            final_video_path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
        process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
        
        if process.returncode != 0:
            error_output = process.stderr or process.stdout
            logger.error(f"FFmpeg failed:\n{error_output}")
            raise HTTPException(status_code=500, detail=f"FFmpeg optimization failed: {error_output[:500]}")

        await send_status_update(websocket, "Processing complete.")
        return final_video_path
        
    except subprocess.TimeoutExpired:
        logger.error("A subprocess (Manim or FFmpeg) timed out.")
        raise HTTPException(status_code=500, detail="Video generation took too long and was cancelled.")
    except Exception as e:
        logger.error(f"Unexpected error in generate_animation_video: {e}")
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temporary directory: {temp_dir}")