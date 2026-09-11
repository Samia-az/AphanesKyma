import os
import sys
import shutil
import logging
from pathlib import Path
from tempfile import mkdtemp

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("aphaneskyma")
logging.basicConfig(level=logging.INFO)

# Add legacy folder to Python path so we can import the engine
BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_DIR = BASE_DIR / "legacy"
sys.path.append(str(LEGACY_DIR))

from legacy.steganography_engine import SteganographyEngine

app = FastAPI(title="AphanesKyma API")

# Setup temp directory for processing
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)


def _verify_stego(engine: "SteganographyEngine", stego_path, password: str):
    """
    Re-extract and re-decrypt from the just-saved stego file.
    Raises ValueError if any bits were corrupted during the DCT round-trip.
    This is cheap (the payload is already on disk) and catches the
    high-contrast / near-capacity pixel-clipping failure mode.
    """
    payload  = engine._extract_payload(str(stego_path))
    enc_data = engine.payload.extract_data(payload)
    engine.crypto.decrypt_bytes(enc_data, password)   # raises InvalidTag on corruption

@app.post("/api/encode/text")
async def api_encode_text(
    cover: UploadFile = File(...),
    message: str = Form(...),
    password: str = Form(...),
    method: str = Form("dct"),
    quantization_step: int = Form(16)
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

        # Self-verify: re-extract from the saved file before serving
        try:
            _verify_stego(engine, output_path, password)
        except Exception:
            raise ValueError(
                "Embedding verification failed — the cover image has too many "
                "extreme-value pixels (pure black/white) for this payload size. "
                "Use a natural photograph as the cover image, or a shorter message."
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


@app.post("/api/encode/image")
async def api_encode_image(
    cover: UploadFile = File(...),
    secret: UploadFile = File(...),
    password: str = Form(...),
    method: str = Form("dct"),
    quantization_step: int = Form(16)
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

        # Self-verify: re-extract from the saved file before serving
        try:
            _verify_stego(engine, output_path, password)
        except Exception:
            raise ValueError(
                "Embedding verification failed — the cover image has too many "
                "extreme-value pixels (pure black/white) for this payload size. "
                "Use a natural photograph as the cover image, or a smaller secret image."
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
    method: str = Form("dct"),
    quantization_step: int = Form(16)
):
    temp_dir = Path(mkdtemp(dir=TMP_DIR))
    try:
        stego_path = temp_dir / stego.filename

        with open(stego_path, "wb") as buffer:
            shutil.copyfileobj(stego.file, buffer)

        engine = SteganographyEngine(
            quantization_step=quantization_step,
            method=method
        )

        # Extract payload once, inspect type, then decrypt inline
        # (avoids running _extract_payload twice)
        payload   = engine._extract_payload(str(stego_path))
        data_type = engine.payload.get_data_type(payload)
        enc_data  = engine.payload.extract_data(payload)

        logger.info("Decode: data_type=%s  enc_bytes=%d  method=%s  quant=%d",
                    data_type, len(enc_data), method, quantization_step)

        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        if data_type == engine.payload.TYPE_TEXT:
            decrypted_bytes = engine.crypto.decrypt_bytes(enc_data, password)
            decrypted_text  = decrypted_bytes.decode("utf-8")
            return JSONResponse(
                content={"type": "text", "data": decrypted_text},
                background=background_tasks
            )

        elif data_type == engine.payload.TYPE_IMAGE:
            decrypted_bytes      = engine.crypto.decrypt_bytes(enc_data, password)
            output_secret_path   = temp_dir / "secret_extracted.png"
            engine.image_payload.save_image(decrypted_bytes, str(output_secret_path))

            logger.info("Decode image: saved to %s  (%d bytes)",
                        output_secret_path, len(decrypted_bytes))

            return FileResponse(
                path=str(output_secret_path),
                filename="secret_extracted.png",
                media_type="image/png",
                headers={"X-Payload-Type": "image"},
                background=background_tasks
            )

        else:
            raise ValueError("Unknown payload type.")

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception("Decode failed: %s", e)
        detail = str(e).strip()
        if not detail:
            cls = type(e).__name__
            if 'InvalidTag' in cls or 'InvalidSignature' in cls:
                detail = (
                    "Decryption failed (InvalidTag). "
                    "The passphrase is wrong, or the quantization step / method does not match."
                )
            else:
                detail = f"Unexpected error: {cls}"
        raise HTTPException(status_code=400, detail=detail)

# Mount the static UI files at the root
UI_DIR = BASE_DIR / "ui"
app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
