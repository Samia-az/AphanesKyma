import os
import sys
import shutil
from pathlib import Path
from tempfile import mkdtemp

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add legacy folder to Python path so we can import the engine
BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_DIR = BASE_DIR / "legacy"
sys.path.append(str(LEGACY_DIR))

from legacy.steganography_engine import SteganographyEngine

app = FastAPI(title="AphanesKyma API")

# Setup temp directory for processing
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)


@app.post("/api/encode/text")
async def api_encode_text(
    cover: UploadFile = File(...),
    message: str = Form(...),
    password: str = Form(...),
    method: str = Form("dct"),
    quantization_step: int = Form(8)
):
    temp_dir = Path(mkdtemp(dir=TMP_DIR))
    try:
        cover_path = temp_dir / cover.filename
        output_path = temp_dir / "stego.png"

        # Save uploaded cover image
        with open(cover_path, "wb") as buffer:
            shutil.copyfileobj(cover.file, buffer)

        # Initialize engine
        engine = SteganographyEngine(
            quantization_step=quantization_step,
            method=method
        )

        # Encode
        metrics = engine.encode_text(
            cover_path=str(cover_path),
            output_path=str(output_path),
            message=message,
            password=password
        )

        # Return the generated stego image as a file download. 
        # We can't delete the temp_dir immediately if we're returning FileResponse directly,
        # unless we use a BackgroundTask. We'll use BackgroundTask for cleanup.
        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        return FileResponse(
            path=output_path, 
            filename="stego.png",
            media_type="image/png",
            headers={
                "X-Metrics-Payload": str(metrics.get("payload_size")),
                "X-Metrics-Bits": str(metrics.get("bits")),
                "X-Metrics-PSNR": f"{metrics.get('psnr'):.2f}",
                "X-Metrics-MSE": f"{metrics.get('mse'):.4f}"
            },
            background=background_tasks
        )

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/encode/image")
async def api_encode_image(
    cover: UploadFile = File(...),
    secret: UploadFile = File(...),
    password: str = Form(...),
    method: str = Form("dct"),
    quantization_step: int = Form(8)
):
    temp_dir = Path(mkdtemp(dir=TMP_DIR))
    try:
        cover_path = temp_dir / cover.filename
        secret_path = temp_dir / secret.filename
        output_path = temp_dir / "stego.png"

        # Save uploaded files
        with open(cover_path, "wb") as buffer:
            shutil.copyfileobj(cover.file, buffer)
        with open(secret_path, "wb") as buffer:
            shutil.copyfileobj(secret.file, buffer)

        engine = SteganographyEngine(
            quantization_step=quantization_step,
            method=method
        )

        metrics = engine.encode_image(
            cover_path=str(cover_path),
            output_path=str(output_path),
            secret_image_path=str(secret_path),
            password=password
        )

        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        return FileResponse(
            path=output_path, 
            filename="stego.png",
            media_type="image/png",
            headers={
                "X-Metrics-Payload": str(metrics.get("payload_size")),
                "X-Metrics-Bits": str(metrics.get("bits")),
                "X-Metrics-PSNR": f"{metrics.get('psnr'):.2f}",
                "X-Metrics-MSE": f"{metrics.get('mse'):.4f}"
            },
            background=background_tasks
        )

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/decode")
async def api_decode(
    stego: UploadFile = File(...),
    password: str = Form(...),
    method: str = Form("dct")
):
    temp_dir = Path(mkdtemp(dir=TMP_DIR))
    try:
        stego_path = temp_dir / stego.filename
        
        with open(stego_path, "wb") as buffer:
            shutil.copyfileobj(stego.file, buffer)

        engine = SteganographyEngine(method=method)

        # We first need to check what type of payload it is to know which decode function to call.
        # But payload type is inside the header. The UI doesn't explicitly send what it is (or it could, but 
        # usually we don't know). 
        # Wait, in the legacy engine, _extract_payload and get_data_type can tell us.
        payload = engine._extract_payload(str(stego_path))
        data_type = engine.payload.get_data_type(payload)

        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        if data_type == engine.payload.TYPE_TEXT:
            decrypted_text = engine.decode_text(str(stego_path), password)
            return JSONResponse(
                content={"type": "text", "data": decrypted_text},
                background=background_tasks
            )
        
        elif data_type == engine.payload.TYPE_IMAGE:
            output_secret_path = temp_dir / "secret_extracted.png"
            engine.decode_image(str(stego_path), str(output_secret_path), password)
            
            return FileResponse(
                path=output_secret_path, 
                filename="secret_extracted.png",
                media_type="image/png",
                headers={"X-Payload-Type": "image"},
                background=background_tasks
            )
        
        else:
            raise ValueError("Unknown payload type.")

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))

# Mount the static UI files at the root
UI_DIR = BASE_DIR / "ui"
app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
