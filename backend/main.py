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

# Add legacy folder and src folder to Python path
BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_DIR = BASE_DIR / "legacy"
SRC_DIR = BASE_DIR / "src"

sys.path.append(str(LEGACY_DIR))
sys.path.append(str(SRC_DIR))

from legacy.steganography_engine import SteganographyEngine

# Imports for Image to Audio conversion
import wave
from imageio.v2 import imread
from src.preprocessing import resize_for_audio
from src.image_audio_fft import normalize_image_to_magnitude, SAMPLE_RATE, magnitude_to_image_uint8
from src.header_fft import image_to_audio_with_header, audio_with_header_to_image
from src.capture_decode import decode_captured_audio
from src.denoise import denoise_image
from PIL import Image as PILImage
import numpy as np

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


@app.post("/api/convert/image-to-audio")
async def api_image_to_audio(
    image: UploadFile = File(...),
    mode: str = Form("listenable"),
    data_repeats: int = Form(1)
):
    temp_dir = Path(mkdtemp(dir=TMP_DIR))
    try:
        image_path = temp_dir / image.filename
        output_path = temp_dir / "output.wav"

        # Save uploaded image
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # Read and process image
        img_array = imread(str(image_path))
        if img_array.ndim == 3:
            img_gray = img_array[:,:,0].astype(np.float64)
        else:
            img_gray = img_array.astype(np.float64)

        img_gray = resize_for_audio(img_gray, max_dimension=256) 
        mag_img = normalize_image_to_magnitude(img_gray)
        
        # Convert to audio
        audio = image_to_audio_with_header(mag_img, mode=mode, data_repeats=data_repeats)
        
        # Convert to int16 and save as wav
        audio_int16 = (audio * 32767 * 0.9).astype(np.int16)
        with wave.open(str(output_path), 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        return FileResponse(
            path=output_path, 
            filename="sonification.wav",
            media_type="audio/wav",
            background=background_tasks
        )

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception("Image to audio conversion failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/convert/audio-to-image")
async def api_audio_to_image(
    audio: UploadFile = File(...),
    denoise_method: str = Form("median"),
    kernel_size: int = Form(3),
    keep_fraction: float = Form(0.35)
):
    temp_dir = Path(mkdtemp(dir=TMP_DIR))
    try:
        audio_path = temp_dir / audio.filename
        output_png_path = temp_dir / "reconstructed.png"

        # Save uploaded audio file
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Read WAV file
        with wave.open(str(audio_path), 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        if sampwidth == 2:
            samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float64) / 32767.0
        elif sampwidth == 4:
            samples = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float64) / 2147483647.0
        elif sampwidth == 1:
            samples = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
        else:
            samples = np.frombuffer(raw_bytes, dtype=np.float32).astype(np.float64)

        if n_channels > 1:
            samples = samples[::n_channels]

        # Try clean header decode first, fallback to capture decode if needed
        try:
            img_matrix, n_rows, n_cols, mode_name, source = audio_with_header_to_image(samples)
            if source == 'thumbnail_fallback':
                logger.info("Clean decode returned thumbnail_fallback, attempting capture decode...")
                try:
                    cap_img_matrix, cap_n_rows, cap_n_cols, cap_mode_name, cap_source = decode_captured_audio(samples, native_rate=framerate)
                    if cap_source == 'full':
                        img_matrix, n_rows, n_cols, mode_name, source = cap_img_matrix, cap_n_rows, cap_n_cols, cap_mode_name, cap_source
                except Exception as err_cap:
                    logger.info("Capture decode attempt failed (%s), keeping thumbnail fallback.", err_cap)
        except Exception as err_clean:
            logger.info("Clean decode failed (%s), attempting capture decode...", err_clean)
            img_matrix, n_rows, n_cols, mode_name, source = decode_captured_audio(samples, native_rate=framerate)

        # Apply denoising if requested
        if denoise_method and denoise_method != "none":
            img_matrix = denoise_image(
                img_matrix,
                method=denoise_method,
                kernel_size=kernel_size,
                keep_fraction=keep_fraction
            )

        # Convert to PNG image
        uint8_img = magnitude_to_image_uint8(img_matrix)
        pil_img = PILImage.fromarray(uint8_img)
        pil_img.save(str(output_png_path), format="PNG")

        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        return FileResponse(
            path=output_png_path,
            filename="reconstructed.png",
            media_type="image/png",
            headers={
                "X-Decoded-Mode": str(mode_name),
                "X-Decoded-Rows": str(n_rows),
                "X-Decoded-Cols": str(n_cols),
                "X-Decoded-Source": str(source)
            },
            background=background_tasks
        )

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception("Audio to image conversion failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# Mount the static UI files at the root
UI_DIR = BASE_DIR / "ui"
app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
