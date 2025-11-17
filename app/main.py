"""
Main FastAPI application.
"""
import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
import uvicorn

from videotext.pipeline import Pipeline, PipelineCallback
from app.vtt import write_vtt, write_srt


# Environment variables
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Check for dependencies
CTRANSLATE2_AVAILABLE = False
FASTER_WHISPER_AVAILABLE = False

try:
    import ctranslate2
    CTRANSLATE2_AVAILABLE = True
except ImportError:
    pass

try:
    import faster_whisper
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    pass

# FastAPI app
app = FastAPI(
    title="TurboScribe API",
    description="Сервис автоматической транскрипции аудио и видео",
    version="1.0.0"
)

# Templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Artifacts serving
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")

# Job storage (in-memory for scaffold; replace with DB)


class InMemoryJobStore:
    """Lightweight in-memory job registry."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(self, job_id: str, mode: str, language: Optional[str]) -> Dict[str, Any]:
        job = {
            "id": job_id,
            "status": "created",
            "progress": 0.0,
            "stage": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "completed_at": None,
            "error": None,
            "mode": mode,
            "language": language,
            "duration": None,
            "artifacts": [],
        }
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Dict[str, Any]:
        return self._jobs.get(job_id)

    def require_job(self, job_id: str) -> Dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return job

    def update_job(self, job_id: str, **fields: Any) -> None:
        job = self.require_job(job_id)
        job.update(fields)
        job["updated_at"] = datetime.utcnow()

    def mark_completed(self, job_id: str, artifacts: List[str]) -> None:
        job = self.require_job(job_id)
        job.update(
            {
                "status": "completed",
                "stage": None,
                "progress": 1.0,
                "completed_at": datetime.utcnow(),
                "artifacts": artifacts,
            }
        )
        job["updated_at"] = datetime.utcnow()

    def mark_failed(self, job_id: str, error: Exception) -> None:
        self.update_job(job_id, status="failed", error=str(error), progress=0.0)

    def mark_cancelled(self, job_id: str) -> None:
        self.update_job(job_id, status="cancelled")


jobs = InMemoryJobStore()


# Pydantic models
class JobCreate(BaseModel):
    source_url: Optional[HttpUrl] = None
    mode: str = "balance"
    language: Optional[str] = None
    diarization: bool = False
    ocr_enabled: bool = False
    ocr_interval: int = 5
    denoise: bool = False
    translate_to: Optional[str] = None
    keywords: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    status: str
    progress: float
    stage: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class PipelineProgressCallback(PipelineCallback):
    """Callback for pipeline progress updates."""

    def __init__(self, job_store: InMemoryJobStore, job_id: str):
        self.job_store = job_store
        self.job_id = job_id

    def _update(self, **fields: Any) -> None:
        self.job_store.update_job(self.job_id, **fields)

    def on_start(self, job_id: str, config: dict) -> None:
        self._update(status="processing", stage="initializing", progress=0.0)

    def on_audio_extracted(self, job_id: str, audio_path: str, duration: float) -> None:
        self._update(stage="audio_extracted", progress=0.1, duration=duration)

    def on_asr_started(self, job_id: str) -> None:
        self._update(stage="asr", progress=0.2)

    def on_asr_completed(self, job_id: str, segments: list) -> None:
        self._update(progress=0.6)

    def on_diarization_completed(self, job_id: str, segments: list) -> None:
        self._update(stage="diarization", progress=0.7)

    def on_ocr_started(self, job_id: str) -> None:
        self._update(stage="ocr", progress=0.5)

    def on_ocr_completed(self, job_id: str, segments: list) -> None:
        self._update(progress=0.65)

    def on_translation_completed(self, job_id: str, segments: list) -> None:
        self._update(stage="translation", progress=0.9)

    def on_export_started(self, job_id: str) -> None:
        self._update(stage="exporting", progress=0.95)

    def on_done(self, job_id: str, artifacts: list) -> None:
        self.job_store.mark_completed(job_id, artifacts)

    def on_error(self, job_id: str, error: Exception) -> None:
        self.job_store.mark_failed(job_id, error)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page with upload form."""
    show_warning = not (CTRANSLATE2_AVAILABLE and FASTER_WHISPER_AVAILABLE)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "show_warning": show_warning,
        "ctranslate2_available": CTRANSLATE2_AVAILABLE,
        "faster_whisper_available": FASTER_WHISPER_AVAILABLE
    })


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_view(request: Request, job_id: str):
    """Job results page."""
    job = jobs.require_job(job_id)
    vtt_path = None
    
    # Find VTT file
    if 'artifacts' in job:
        for artifact in job['artifacts']:
            if artifact.endswith('merged.vtt'):
                vtt_path = artifact
                break
    
    return templates.TemplateResponse("job.html", {
        "request": request,
        "job": job,
        "job_id": job_id,
        "vtt_path": vtt_path
    })


@app.post("/v1/jobs")
async def create_job(
    source: UploadFile = File(None),
    source_url: Optional[str] = Form(None),
    mode: str = Form("balance"),
    language: Optional[str] = Form(None),
    diarization: bool = Form(False),
    ocr_enabled: bool = Form(False),
    ocr_interval: int = Form(5),
    denoise: bool = Form(False),
    translate_to: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None)
):
    """Create a new transcription job."""
    job_id = str(uuid.uuid4())
    
    # Determine source
    if source:
        source_path = UPLOAD_DIR / job_id / source.filename
        source_path.parent.mkdir(parents=True, exist_ok=True)
        with open(source_path, "wb") as f:
            content = await source.read()
            f.write(content)
    elif source_url:
        # TODO: Download from URL
        source_path = None
        raise HTTPException(status_code=400, detail="URL загрузка пока не реализована")
    else:
        raise HTTPException(status_code=400, detail="Необходимо указать файл или URL")
    
    # Create job record
    jobs.create_job(job_id, mode, language)
    
    # Start pipeline in background
    callback = PipelineProgressCallback(jobs, job_id)
    pipeline = Pipeline(callback=callback, output_dir=str(ARTIFACTS_DIR))
    
    def run_pipeline():
        try:
            pipeline.run(
                job_id=job_id,
                source_path=str(source_path),
                mode=mode,
                language=language,
                diarization=diarization,
                ocr_enabled=ocr_enabled,
                ocr_interval=ocr_interval,
                denoise=denoise,
                translate_to=translate_to,
                keywords=keywords
            )
        except Exception as e:
            callback.on_error(job_id, e)
    
    # Run in thread pool executor to avoid blocking
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_pipeline)
    
    return JobResponse(**jobs.require_job(job_id))


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job status."""
    return JobResponse(**jobs.require_job(job_id))


@app.get("/v1/jobs/{job_id}/progress")
async def get_job_progress(job_id: str):
    """SSE stream for job progress."""
    jobs.require_job(job_id)

    async def event_stream():
        last_progress = -1
        while True:
            job = jobs.get_job(job_id)
            if not job:
                break
            
            if job['progress'] != last_progress:
                yield f"event: progress\n"
                yield f"data: {job['progress']}\n\n"
                last_progress = job['progress']
            
            if job['status'] in ['completed', 'failed', 'cancelled']:
                yield f"event: done\n"
                yield f"data: {job['status']}\n\n"
                break
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/v1/jobs/{job_id}/artifacts")
async def get_job_artifacts(job_id: str):
    """Get job artifacts."""
    job = jobs.require_job(job_id)
    artifacts = job.get('artifacts', [])
    
    return {
        'artifacts': [
            {
                'type': Path(a).stem,
                'path': a,
                'url': f"/artifacts/{a}"
            }
            for a in artifacts
        ]
    }


@app.delete("/v1/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a job."""
    job = jobs.require_job(job_id)
    if job['status'] in ['completed', 'failed', 'cancelled']:
        raise HTTPException(status_code=400, detail="Задача уже завершена")

    jobs.mark_cancelled(job_id)
    
    return {"status": "cancelled"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "ctranslate2": CTRANSLATE2_AVAILABLE,
        "faster_whisper": FASTER_WHISPER_AVAILABLE
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
