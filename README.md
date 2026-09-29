# AphanesKyma

> *Aphanes* (ἀφανής) — invisible · *Kyma* (κῦμα) — wave

A dual-purpose frequency-domain steganography and image sonification platform. Hide encrypted messages or images inside cover photos, or convert images into audio waveforms and reconstruct them later — even after playing them through a speaker and recording with a microphone.

---

## Features

### 🔒 Steganography Studio (`index.html`)
- **Text & image payloads** — embed a secret message or an entire image inside any cover photo.
- **Frequency-domain embedding** — DCT (8×8 block QIM) and FFT methods; modifications live in mid-frequency coefficients that are perceptually invisible.
- **AES-256-GCM encryption** — every payload is encrypted with a random salt and nonce before embedding; the stego image is useless without the passphrase.
- **APKY magic signature** — a versioned binary header (`APKY v1`) tags every payload so the decoder can validate it without trial-and-error.
- **Lossless PNG output** — the stego image is always saved as PNG to preserve every modified bit exactly.
- **Self-verification on encode** — the backend re-extracts and re-decrypts from the saved file before serving it, catching pixel-clipping failures early.
- **Configurable quantization step** (4 – 32) and choice of embedding method exposed in the UI.

### 🎵 Sonification Studio (`sonification.html`)
- **Image → Audio** — each row of a grayscale image is treated as a frequency-domain magnitude spectrum and synthesised via inverse rFFT at 48 kHz.
- **Audio → Image** — the process is inverted: rFFT the audio frame-by-frame to recover the pixel magnitudes.
- **Self-describing header** — image dimensions, audio preset, and data-repeat count are encoded into a fixed-length header frame using Hamming(7,4) ECC with pilot tones, interleaved bits, and 3× majority-vote redundancy.
- **Chirp preamble marker** — a 500 Hz → 18 kHz matched-filter chirp marks the start of the signal; robust to room reverb unlike copy-vs-copy NCC.
- **Capture-decode path** — records live microphone audio, resamples to the encoding rate, locates the marker via matched filtering, fine-tunes alignment by maximising pilot-tone energy, and reconstructs the image.
- **Audio presets** — *Fidelity* (flat spectrum) and *Balanced* (A-weighting de-emphasis + row blur) presets stored by ID in the header.
- **Phase modes** — Fixed, Chirp, Random-per-row, Minimum-phase, and Borrowed for controlling the perceptual character of the output audio.
- **Data repeats** — each image row can be transmitted 1 – 15× ; the decoder collapses each group via per-bin median, raising noise robustness at a linear cost in audio length.
- **Post-decode denoising** — Median, 2D DFT Spectral Low-Pass, Box Blur, or passthrough.
- **Audio trimmer** — trim leading/trailing silence from mic recordings before decoding.

---

## Project Structure

```
AphanesKyma/
├── backend/
│   └── main.py             # FastAPI server — all API endpoints
├── src/
│   ├── image_audio_fft.py  # Core FFT image↔audio codec (phase modes, rFFT synthesis)
│   ├── header_fft.py       # Self-describing header (Hamming ECC, presets, full pipeline)
│   ├── capture_decode.py   # Live mic capture path (resample, marker search, decode)
│   ├── marker.py           # Chirp preamble — make_marker() & find_marker_offset()
│   ├── hamming_bits.py     # Hamming(7,4) encode/decode helpers
│   ├── denoise.py          # Post-decode denoising filters
│   ├── preprocessing.py    # resize_for_audio()
│   └── image.py            # Misc image utilities
├── legacy/
│   ├── steganography_engine.py   # High-level encode/decode orchestrator
│   ├── dct_steganography.py      # DCT QIM embedding
│   ├── fft_steganography.py      # FFT embedding (legacy)
│   ├── crypto.py                 # AES-256-GCM encrypt/decrypt
│   ├── payload.py                # APKY payload framing (magic bytes, type, length)
│   └── image_payload.py          # Image payload serialisation
├── ui/
│   ├── index.html          # Steganography Studio UI
│   ├── sonification.html   # Sonification Studio UI
│   ├── app.js              # Steganography Studio JavaScript
│   ├── sonification.js     # Sonification Studio JavaScript
│   └── style.css           # Shared stylesheet
└── requirements.txt
```

---

## Installation

**Prerequisites:** Python 3.10+

```bash
# Clone the repository
git clone https://github.com/your-username/AphanesKyma.git
cd AphanesKyma

# Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Running the Server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in your browser.

The FastAPI server serves the `ui/` directory as static files at `/` and exposes the following REST endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/encode/text` | Embed encrypted text into a cover image |
| `POST` | `/api/encode/image` | Embed a secret image into a cover image |
| `POST` | `/api/decode` | Extract and decrypt a payload from a stego image |
| `POST` | `/api/convert/image-to-audio` | Synthesise audio from an image |
| `POST` | `/api/convert/audio-to-image` | Reconstruct an image from audio |

---

## How It Works

### Steganography

1. **Encrypt** — the payload (text or image bytes) is encrypted with AES-256-GCM. A random 16-byte salt is passed through SHA-256 to derive the key; a random 12-byte nonce is generated per operation.
2. **Frame** — the ciphertext is wrapped in an APKY payload: `APKY` magic + version byte + type byte + length + data.
3. **Transform** — for DCT, the cover image is split into 8×8 blocks and transformed. Mid-frequency coefficients are modified using Quantization Index Modulation (QIM) with a configurable step size.
4. **Save** — the modified image is written as PNG (lossless), preserving every altered coefficient exactly.
5. **Verify** — the server immediately re-extracts and decrypts to confirm the round-trip before sending the file to the client.

### Sonification

```
Image (rows × cols)
  │
  ├─ Preset applied (A-weighting curve × row blur)
  ├─ Rows repeated data_repeats times
  │
  ▼
Header frame (Hamming-coded, pilot tones, interleaved)
  × HEADER_REPEATS (majority-voted on decode)
  +
Chirp marker (matched-filter preamble)
  +
Data audio (irFFT of each magnitude row → overlap-add)
  │
  ▼
WAV file @ 48 kHz, 16-bit mono
```

Decode reverses the pipeline: locate the marker via matched filter → strip it → majority-vote the header to recover dimensions and preset → inverse-FFT each frame → apply per-bin median across data-repeat groups → invert the preset weighting → save PNG.

---

## Audio Presets

| ID | Name | Description |
|----|------|-------------|
| 0 | `fidelity` | Flat spectrum — maximum reconstruction fidelity. |
| 1 | `balanced` | A-weighting de-emphasis (strength 0.6) + 5% row blur — smoother sound, still decodable. |

---

## Phase Modes

| Mode | Behaviour |
|------|-----------|
| `fixed` | One random phase vector drawn once, reused for every row. |
| `random_per_row` | Fresh random phase per row — broadband hiss. |
| `chirp` | Quadratic phase ramp — spreads each frame's energy into a short sweep. |
| `minphase` | Minimum-phase reconstruction via the real cepstrum method. |

All modes recover the image identically up to a global scale constant.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `numpy` | FFT, array arithmetic |
| `scipy` | Polyphase resampler (`resample_poly`) |
| `imageio` | Image I/O |
| `Pillow` | PNG saving |
| `matplotlib` | (Available for debugging/visualisation) |
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server |
| `python-multipart` | `multipart/form-data` uploads |
| `cryptography` | AES-256-GCM via `cryptography.hazmat` |

---

## Notes & Limitations

- **Cover image quality** — images with large areas of pure black or white pixels may fail self-verification at high payload sizes; use natural photographs for best results.
- **Steganography round-trip** — decoding requires the exact same embedding method and quantization step used during encoding.
- **Sonification fidelity** — reconstruction quality degrades with acoustic noise, microphone frequency response colouring, and room reverb. Using `data_repeats > 1` significantly improves robustness at the cost of longer audio.
- **Capture rate** — the live capture path reads the WAV framerate from the file header and resamples correctly; do not assume a fixed rate.
- **Maximum image size** — images are resized to at most 256×256 before sonification to keep audio duration manageable.

---

## License

This project is for educational and research purposes. See `LICENSE` for details.
