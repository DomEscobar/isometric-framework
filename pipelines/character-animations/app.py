from __future__ import annotations

import hmac
import io
import json
import os
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Literal

from runner import AUTOMATIC_REVIEW_MODEL, PAID_STAGES, Runner, automatic_review_policy, validate_stage_request
from store import Conflict, Store, safe_basename
from provider import available_presets

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
MAX_IMAGE_SIDE = 4096
MAX_IMAGE_PIXELS = 16_000_000
MAX_OPTIONS_BYTES = 4096
PROJECT_ROOT = Path(__file__).resolve().parent
UI_DIR = PROJECT_ROOT / "ui"
UI_DEMO_DIR = PROJECT_ROOT / "ui-demo"
PUBLIC_BASE_URL = "https://isoani.huecki.com/animation"
AGENT_DOCS = {
    "agent-guide.md": (PROJECT_ROOT / "docs" / "AGENT_GUIDE.md", "text/markdown; charset=utf-8"),
    "agent-prompt.txt": (PROJECT_ROOT / "docs" / "AGENT_PROMPT.txt", "text/plain; charset=utf-8"),
}
UI_ASSETS = {
    "app.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
UI_DEMO_ASSETS = {
    "atlas.png": "image/png",
    "atlas-manifest.json": "application/json",
}
UI_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
    "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)

STAGE_CAPABILITIES = {
    "inspect_reference": {"paid": False, "capability": None, "supported": True},
    "generate_facing": {"paid": True, "capability": "image_edit", "supported": True},
    "generate_video": {"paid": True, "capability": "image_to_video", "supported": True},
    "extract_frames": {"paid": False, "capability": None, "supported": True},
    "automatic_review": {"paid": True, "capability": "animation_review", "supported": True},
    "remove_background": {"paid": True, "capability": "background_removal", "supported": True},
    "pack": {"paid": False, "capability": None, "supported": True},
    "mirror": {"paid": False, "capability": None, "supported": True},
    "spatial_export": {"paid": False, "capability": "cache_backed_spatial_export", "supported": True},
}


class RequestBodyTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    def __init__(self, app: Any, maximum: int):
        self.app = app
        self.maximum = maximum

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        declared = headers.get(b"content-length")
        if declared:
            try:
                if int(declared) > self.maximum:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send)
                return
        received = 0
        response_started = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.maximum:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            if not response_started:
                await self._reject(send)

    @staticmethod
    async def _reject(send: Any) -> None:
        body = b'{"detail":"request body exceeds size limit"}'
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: str
    sha256: str
    decision: Literal["approve", "reject"]


class StageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Stufenspezifische Parameter. Der Container ist absichtlich generisch; "
            "vollständige implementierte Schemas und Beispiele stehen unter "
            "https://isoani.huecki.com/animation/agent-guide.md. Budget- und Autorisierungsfelder "
            "gehören nicht in params."
        ),
    )
    authorize_paid: bool = False
    budget_cap_usd: float | None = None


class AutomaticReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: str
    sha256: str
    revision: int
    authorize_paid_review: bool = False
    budget_cap_usd: float | None = None
    frame_policy: Literal["8", "12", "16", "native"] = "8"
    action: Literal["walk", "punch"] = "walk"


class SpatialSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_artifact: str
    source_sha256: str
    source_revision: int
    native_fps: float
    cycle_start: int
    cycle_end_exclusive: int
    selected_indices: list[int]


def create_app(
    *,
    db_path: str | Path | None = None,
    data_dir: str | Path | None = None,
    pipeline_module: Any | None = None,
    review_module: Any | None = None,
    start_worker: bool = False,
) -> FastAPI:
    root = Path(os.environ.get("ANIMATION_DATA_DIR", "./var"))
    store = Store(db_path or root / "jobs.sqlite3", data_dir or root / "jobs")
    runner = Runner(store, pipeline_module=pipeline_module, review_module=review_module)
    token = os.environ.get("ANIMATION_API_TOKEN")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_worker:
            runner.start_background()
        try:
            yield
        finally:
            runner.stop_background()

    app = FastAPI(
        title="Animation Pipeline API",
        version="1.0.0",
        description=(
            "Stufenbasierte Single-Owner-API. Integrationsanleitung: "
            "https://isoani.huecki.com/animation/agent-guide.md"
        ),
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(RequestSizeLimitMiddleware, maximum=MAX_REQUEST_BYTES)
    app.state.store = store
    app.state.runner = runner

    def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
        if not token:
            raise HTTPException(status_code=503, detail="service token is not configured")
        scheme, separator, supplied = (authorization or "").partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not hmac.compare_digest(supplied, token):
            raise HTTPException(status_code=401, detail="invalid bearer token", headers={"WWW-Authenticate": "Bearer"})

    def require_job(job_id: str) -> dict[str, Any]:
        if not safe_basename(job_id):
            raise HTTPException(status_code=404, detail="job not found")
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/docs", include_in_schema=False)
    def api_docs() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="./openapi.json",
            title="Animation Pipeline API – OpenAPI",
        )

    @app.get("/agent-guide.md", include_in_schema=False)
    def agent_guide() -> Response:
        path, media_type = AGENT_DOCS["agent-guide.md"]
        return Response(
            path.read_bytes(),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/agent-prompt.txt", include_in_schema=False)
    def agent_prompt() -> Response:
        path, media_type = AGENT_DOCS["agent-prompt.txt"]
        return Response(
            path.read_bytes(),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/ui/", response_class=HTMLResponse)
    @app.get("/ui", response_class=HTMLResponse)
    def ui_index() -> HTMLResponse:
        return HTMLResponse(
            (UI_DIR / "index.html").read_text(encoding="utf-8"),
            headers={"Content-Security-Policy": UI_CSP, "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/ui/{asset}")
    def ui_asset(asset: str) -> Response:
        media_type = UI_ASSETS.get(asset)
        if not media_type:
            raise HTTPException(status_code=404, detail="UI asset not found")
        return Response(
            (UI_DIR / asset).read_bytes(),
            media_type=media_type,
            headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/ui/demo/{name}")
    def ui_demo_asset(name: str) -> FileResponse:
        media_type = UI_DEMO_ASSETS.get(name)
        if not media_type:
            raise HTTPException(status_code=404, detail="demo asset not found")
        return FileResponse(
            UI_DEMO_DIR / name,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/v1/capabilities", dependencies=[Depends(require_token)])
    def capabilities() -> dict[str, Any]:
        paid_enabled = os.environ.get("ANIMATION_PAID_ENABLED") == "1"
        try:
            server_cap = max(0.0, float(os.environ.get("ANIMATION_MAX_STAGE_USD", "0")))
        except ValueError:
            server_cap = 0.0
        review_policy = automatic_review_policy()
        return {
            "presets": available_presets(),
            "stages": STAGE_CAPABILITIES,
            "paid_policy": {"enabled": paid_enabled and server_cap > 0, "max_stage_usd": server_cap},
            "automatic_review": {
                "model": AUTOMATIC_REVIEW_MODEL,
                "input_modalities": ["video", "image"],
                "local_analysis": {"available": True, "paid": False},
                "frame_policy": {"default": "8", "allowed": ["8", "12", "16", "native"]},
                "reviewer": {
                    "available": review_policy["available"],
                    "blocked_reason": review_policy.get("blocked_reason"),
                    "max_review_usd": review_policy.get("max_review_usd", 0.0),
                    "fallback_allowed": False,
                },
            },
        }

    @app.get("/v1/jobs", dependencies=[Depends(require_token)])
    def list_jobs() -> list[dict[str, Any]]:
        return store.list_jobs()

    @app.get("/v1/jobs/{job_id}", dependencies=[Depends(require_token)])
    def get_job(job_id: str) -> dict[str, Any]:
        return require_job(job_id)

    @app.post("/v1/jobs", status_code=201, dependencies=[Depends(require_token)])
    async def create_job(
        reference: Annotated[UploadFile, File()],
        options: Annotated[str, Form()] = "{}",
    ) -> dict[str, Any]:
        parsed_options = _parse_options(options)
        content = await _read_bounded(reference, MAX_UPLOAD_BYTES)
        _validate_png(content)
        job = store.create_job("reference.png", parsed_options, content)
        if parsed_options["auto_start"]:
            store.enqueue_stage(job["id"], "inspect_reference", {"input": "reference.png"})
            if start_worker:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    current = store.get_job(job["id"])
                    if current and current["state"] != "queued":
                        if current["state"] != "running":
                            return current
                    time.sleep(0.01)
        return store.get_job(job["id"]) or job

    @app.post("/v1/jobs/{job_id}/stages", status_code=202, dependencies=[Depends(require_token)])
    def submit_stage(job_id: str, request: StageRequest) -> dict[str, Any]:
        require_job(job_id)
        raw_params = request.params if isinstance(request.params, dict) else {}
        try:
            _validate_client_locations(raw_params)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        required = _required_approvals(request.stage, raw_params)
        missing = [name for name in required if not store.has_approval(job_id, name)]
        if missing:
            raise HTTPException(status_code=409, detail=f"review approval required for: {', '.join(missing)}")
        try:
            params = validate_stage_request(request.stage, request.params)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if request.stage in PAID_STAGES:
            paid_enabled = os.environ.get("ANIMATION_PAID_ENABLED") == "1"
            server_cap = float(os.environ.get("ANIMATION_MAX_STAGE_USD", "0"))
            if not request.authorize_paid or request.budget_cap_usd is None or request.budget_cap_usd <= 0:
                raise HTTPException(status_code=422, detail="paid stage requires explicit authorization and positive budget cap")
            if not paid_enabled:
                raise HTTPException(status_code=403, detail="paid stages are disabled by server policy")
            if server_cap <= 0 or request.budget_cap_usd > server_cap:
                raise HTTPException(status_code=422, detail="budget cap exceeds server policy")
            params["budget"] = {"authorized": True, "max_usd": request.budget_cap_usd}
        elif request.authorize_paid or request.budget_cap_usd is not None:
            raise HTTPException(status_code=422, detail="paid authorization is not valid for this stage")
        return store.enqueue_stage(job_id, request.stage, params)

    @app.post("/v1/jobs/{job_id}/automatic-review", status_code=202, dependencies=[Depends(require_token)])
    def submit_automatic_review(job_id: str, request: AutomaticReviewRequest) -> dict[str, Any]:
        require_job(job_id)
        if not safe_basename(request.artifact) or Path(request.artifact).suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
            raise HTTPException(status_code=422, detail="automatic review requires a recorded video artifact basename")
        artifact = store.get_artifact(job_id, request.artifact)
        if not artifact or artifact["sha256"] != request.sha256 or artifact["revision"] != request.revision:
            raise HTTPException(status_code=409, detail="automatic review source does not match current artifact revision")
        if request.authorize_paid_review:
            if request.budget_cap_usd is None or request.budget_cap_usd <= 0:
                raise HTTPException(status_code=422, detail="authorized automatic review requires a positive budget cap")
        elif request.budget_cap_usd is not None:
            raise HTTPException(status_code=422, detail="review budget is invalid without paid review authorization")
        return store.enqueue_stage(job_id, "automatic_review", {
            "input": artifact["name"],
            "source_sha256": artifact["sha256"],
            "source_revision": artifact["revision"],
            "authorize_paid_review": request.authorize_paid_review,
            "budget_cap_usd": request.budget_cap_usd,
            "frame_policy": request.frame_policy,
            "action": request.action,
        })

    @app.post("/v1/jobs/{job_id}/reviews", status_code=201, dependencies=[Depends(require_token)])
    def review_artifact(job_id: str, request: ReviewRequest) -> dict[str, Any]:
        require_job(job_id)
        if not safe_basename(request.artifact):
            raise HTTPException(status_code=404, detail="artifact not found")
        try:
            return store.add_review(job_id, request.artifact, request.sha256, request.decision)
        except Conflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/jobs/{job_id}/selections", status_code=201, dependencies=[Depends(require_token)])
    def create_spatial_selection(job_id: str, request: SpatialSelectionRequest) -> dict[str, Any]:
        require_job(job_id)
        if not safe_basename(request.source_artifact) or Path(request.source_artifact).suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
            raise HTTPException(status_code=422, detail="selection source must be a recorded video artifact basename")
        source = store.get_artifact(job_id, request.source_artifact)
        if not source or source["sha256"] != request.source_sha256 or source["revision"] != request.source_revision:
            raise HTTPException(status_code=409, detail="selection source does not match current artifact revision")
        indices = request.selected_indices
        if (
            not 0 < request.native_fps <= 120
            or not 0 <= request.cycle_start < request.cycle_end_exclusive <= 100000
            or not 1 <= len(indices) <= 128
            or indices != sorted(set(indices))
            or any(not request.cycle_start <= index < request.cycle_end_exclusive for index in indices)
        ):
            raise HTTPException(status_code=422, detail="selection timeline is invalid")
        receipt = {
            "schema": "animation-spatial-selection-v1",
            "mode": "explicit_human_reviewed",
            "source": {"file": source["name"], "sha256": source["sha256"], "revision": source["revision"]},
            "native_fps": request.native_fps,
            "cycle_start": request.cycle_start,
            "cycle_end_exclusive": request.cycle_end_exclusive,
            "selected_indices": indices,
            "visual_quality_certified": False,
        }
        target = store.job_dir(job_id) / "spatial-selection.json"
        temporary = store.job_dir(job_id) / ".spatial-selection.json.tmp"
        temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        with store.connect() as connection:
            store.upsert_artifact(connection, job_id, target.name, "spatial_selection", target)
        return store.get_artifact(job_id, target.name) or {}

    @app.get("/v1/jobs/{job_id}/artifacts/{name}", dependencies=[Depends(require_token)])
    def download_artifact(job_id: str, name: str) -> FileResponse:
        require_job(job_id)
        record = store.get_artifact(job_id, name)
        if not record:
            raise HTTPException(status_code=404, detail="artifact not found")
        path = _recorded_artifact_path(store, job_id, name)
        return FileResponse(path, filename=name, media_type="application/octet-stream")

    @app.get("/v1/jobs/{job_id}/download", dependencies=[Depends(require_token)])
    def download_zip(job_id: str) -> FileResponse:
        require_job(job_id)
        records = store.list_artifacts(job_id)
        archive = store.job_dir(job_id) / ".download.zip"
        temporary = store.job_dir(job_id) / ".download.zip.tmp"
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as output:
            for record in records:
                name = record["name"]
                path = _recorded_artifact_path(store, job_id, name)
                output.write(path, arcname=name)
        os.replace(temporary, archive)
        return FileResponse(archive, filename=f"animation-job-{job_id}.zip", media_type="application/zip")

    def public_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema["servers"] = [
            {"url": PUBLIC_BASE_URL, "description": "Öffentlicher Produktionsendpunkt"}
        ]
        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {})["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API token",
        }
        for path, methods in schema.get("paths", {}).items():
            for operation in methods.values():
                if not isinstance(operation, dict):
                    continue
                operation["security"] = [{"bearerAuth": []}] if path.startswith("/v1/") else []
                operation["parameters"] = [
                    parameter for parameter in operation.get("parameters", [])
                    if not (
                        parameter.get("in") == "header"
                        and str(parameter.get("name", "")).lower() == "authorization"
                    )
                ]
                if not operation["parameters"]:
                    operation.pop("parameters", None)
        app.openapi_schema = schema
        return schema

    app.openapi = public_openapi

    return app


async def _read_bounded(upload: UploadFile, maximum: int) -> bytes:
    result = bytearray()
    while True:
        chunk = await upload.read(min(1024 * 1024, maximum + 1 - len(result)))
        if not chunk:
            return bytes(result)
        result.extend(chunk)
        if len(result) > maximum:
            raise HTTPException(status_code=413, detail="upload exceeds size limit")


def _validate_png(content: bytes) -> None:
    if not content:
        raise HTTPException(status_code=400, detail="empty upload")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != "PNG":
                raise HTTPException(status_code=415, detail="v1 accepts PNG references only")
            width, height = image.size
            if width < 1 or height < 1 or width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="image dimensions exceed limit")
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid PNG upload") from exc


def _parse_options(raw: str) -> dict[str, bool]:
    if len(raw.encode("utf-8")) > MAX_OPTIONS_BYTES:
        raise HTTPException(status_code=413, detail="options exceed size limit")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="options must be valid JSON") from exc
    if not isinstance(value, dict) or set(value) - {"auto_start"}:
        raise HTTPException(status_code=422, detail="only the auto_start option is supported")
    auto_start = value.get("auto_start", True)
    if not isinstance(auto_start, bool):
        raise HTTPException(status_code=422, detail="auto_start must be boolean")
    return {"auto_start": auto_start}


def _validate_client_locations(params: dict[str, Any]) -> None:
    def reject_urls(value: Any) -> None:
        if isinstance(value, str) and value.lower().startswith(("http://", "https://", "file://")):
            raise ValueError("client-supplied URLs are not allowed")
        if isinstance(value, dict):
            for nested in value.values():
                reject_urls(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_urls(nested)

    reject_urls(params)
    for key in ("input", "source", "selection_receipt", "atlas", "manifest"):
        if key in params and not safe_basename(params[key]):
            raise ValueError(f"{key} must be an artifact basename")
    if "inputs" in params:
        inputs = params["inputs"]
        if not isinstance(inputs, list) or not inputs or any(not safe_basename(name) for name in inputs):
            raise ValueError("inputs must contain artifact basenames")


def _required_approvals(stage: str, params: dict[str, Any]) -> list[str]:
    if stage == "inspect_reference":
        return []
    if stage == "generate_facing":
        return [str(params.get("input", "reference.png"))]
    if stage in {"generate_video", "extract_frames"}:
        default = "facing-output.png" if stage == "generate_video" else "video-output.mp4"
        return [str(params.get("input", default))]
    if stage in {"remove_background", "pack"}:
        inputs = params.get("inputs", [])
        return [str(name) for name in inputs] if isinstance(inputs, list) else ["<invalid>"]
    if stage == "mirror":
        return [str(params.get("atlas", "atlas.png")), str(params.get("manifest", "atlas-manifest.json"))]
    if stage == "spatial_export":
        source = str(params.get("source", "video-output.mp4"))
        if params.get("selection_mode") == "automatic_model_validated":
            return [source]
        return [source, str(params.get("selection_receipt", "spatial-selection.json"))]
    return []


def _recorded_artifact_path(store: Store, job_id: str, name: str) -> Path:
    if not safe_basename(name):
        raise HTTPException(status_code=404, detail="artifact not found")
    root = store.job_dir(job_id).resolve()
    path = root / name
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="artifact file missing") from exc
    if resolved.parent != root or path.is_symlink() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return resolved


app = create_app(start_worker=True)
