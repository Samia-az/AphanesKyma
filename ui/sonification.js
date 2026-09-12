/**
 * AphanesKyma — Sonification Studio Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
  initSonificationTabs();
  initAudioSourceTabs();
  initSonificationDropZones();
  initDenoiseControls();
  initImageToAudioFlow();
  initAudioToImageFlow();
  initLiveMicRecorder();
});

// State storage
let liveRecordedBlob = null;
let rawRecordedFloat32Samples = null;
let rawRecordedSampleRate = 44100;
let currentSonificationAudioBlob = null;
let mediaRecorder = null;
let audioChunks = [];
let recordStartTime = 0;
let recordTimerInterval = null;

// ── Tab Switcher: Image2Audio vs Audio2Img ──────────────────────
function initSonificationTabs() {
  const tabImg2Audio = document.getElementById('tab-img2audio');
  const tabAudio2Img = document.getElementById('tab-audio2img');
  const paneImg2Audio = document.getElementById('pane-img2audio');
  const paneAudio2Img = document.getElementById('pane-audio2img');

  if (!tabImg2Audio || !tabAudio2Img) return;

  tabImg2Audio.addEventListener('click', () => {
    tabImg2Audio.classList.add('active');
    tabAudio2Img.classList.remove('active');
    tabImg2Audio.setAttribute('aria-selected', 'true');
    tabAudio2Img.setAttribute('aria-selected', 'false');
    paneImg2Audio.hidden = false;
    paneAudio2Img.hidden = true;
  });

  tabAudio2Img.addEventListener('click', () => {
    tabAudio2Img.classList.add('active');
    tabImg2Audio.classList.remove('active');
    tabAudio2Img.setAttribute('aria-selected', 'true');
    tabImg2Audio.setAttribute('aria-selected', 'false');
    paneAudio2Img.hidden = false;
    paneImg2Audio.hidden = true;
  });
}

// ── Audio Source Switcher: File vs Mic ──────────────────────────
function initAudioSourceTabs() {
  const srcTabFile = document.getElementById('src-tab-file');
  const srcTabMic  = document.getElementById('src-tab-mic');
  const srcPaneFile = document.getElementById('src-pane-file');
  const srcPaneMic  = document.getElementById('src-pane-mic');

  if (!srcTabFile || !srcTabMic) return;

  srcTabFile.addEventListener('click', () => {
    srcTabFile.classList.add('active');
    srcTabMic.classList.remove('active');
    srcPaneFile.hidden = false;
    srcPaneMic.hidden = true;
  });

  srcTabMic.addEventListener('click', () => {
    srcTabMic.classList.add('active');
    srcTabFile.classList.remove('active');
    srcPaneMic.hidden = false;
    srcPaneFile.hidden = true;
  });
}

// ── Drop Zones for Sonification ─────────────────────────────────
function initSonificationDropZones() {
  // Sonification image dropzone
  setupDropZone({
    zone: 'son-image-zone',
    input: 'son-image-input',
    idle: 'son-image-idle',
    preview: 'son-image-preview',
    img: 'son-image-img',
    info: 'son-image-info',
    change: 'son-image-change',
    isImage: true
  });

  // WAV audio dropzone
  setupDropZone({
    zone: 'son-wav-zone',
    input: 'son-wav-input',
    idle: 'son-wav-idle',
    preview: 'son-wav-preview',
    info: 'son-wav-info',
    change: 'son-wav-change',
    isImage: false
  });
}

function setupDropZone(config) {
  const zoneEl = document.getElementById(config.zone);
  const inputEl = document.getElementById(config.input);
  const idleEl = document.getElementById(config.idle);
  const previewEl = document.getElementById(config.preview);
  const infoEl = document.getElementById(config.info);
  const changeBtn = document.getElementById(config.change);
  const imgEl = config.img ? document.getElementById(config.img) : null;

  if (!zoneEl) return;

  zoneEl.addEventListener('click', (e) => {
    if (e.target !== changeBtn) inputEl.click();
  });

  zoneEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    zoneEl.classList.add('drag-over');
  });

  zoneEl.addEventListener('dragleave', () => {
    zoneEl.classList.remove('drag-over');
  });

  zoneEl.addEventListener('drop', (e) => {
    e.preventDefault();
    zoneEl.classList.remove('drag-over');
    if (e.dataTransfer.files.length) {
      inputEl.files = e.dataTransfer.files;
      handleSelectedFile(inputEl.files[0], config);
    }
  });

  inputEl.addEventListener('change', () => {
    if (inputEl.files.length) {
      handleSelectedFile(inputEl.files[0], config);
    }
  });

  changeBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    inputEl.value = '';
    idleEl.hidden = false;
    previewEl.hidden = true;
  });
}

function handleSelectedFile(file, config) {
  const idleEl = document.getElementById(config.idle);
  const previewEl = document.getElementById(config.preview);
  const infoEl = document.getElementById(config.info);
  const imgEl = config.img ? document.getElementById(config.img) : null;

  if (config.isImage) {
    if (!file.type.startsWith('image/')) {
      showToast('Please select an image file', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      if (imgEl) imgEl.src = e.target.result;
      const kb = (file.size / 1024).toFixed(1);
      infoEl.textContent = `${file.name} (${kb} KB)`;
      idleEl.hidden = true;
      previewEl.hidden = false;
    };
    reader.readAsDataURL(file);
  } else {
    // Audio file
    const kb = (file.size / 1024).toFixed(1);
    infoEl.textContent = `${file.name} (${kb} KB)`;
    idleEl.hidden = true;
    previewEl.hidden = false;
  }
}

// ── Denoise Filter Sliders & Toggle ──────────────────────────────
function initDenoiseControls() {
  const methodSelect = document.getElementById('son-denoise-method');
  const groupKernel = document.getElementById('group-kernel-size');
  const groupFraction = document.getElementById('group-keep-fraction');
  const kernelRange = document.getElementById('son-kernel-size');
  const kernelVal = document.getElementById('son-kernel-val');
  const fractionRange = document.getElementById('son-keep-fraction');
  const fractionVal = document.getElementById('son-fraction-val');

  if (!methodSelect) return;

  methodSelect.addEventListener('change', () => {
    const val = methodSelect.value;
    if (val === 'median' || val === 'blur') {
      groupKernel.style.display = 'block';
      groupFraction.style.display = 'none';
    } else if (val === 'spectral') {
      groupKernel.style.display = 'none';
      groupFraction.style.display = 'block';
    } else {
      groupKernel.style.display = 'none';
      groupFraction.style.display = 'none';
    }
  });

  if (kernelRange && kernelVal) {
    kernelRange.addEventListener('input', () => {
      kernelVal.textContent = `${kernelRange.value} x ${kernelRange.value}`;
    });
  }

  if (fractionRange && fractionVal) {
    fractionRange.addEventListener('input', () => {
      fractionVal.textContent = fractionRange.value;
    });
  }
}

// ── Image to Audio Conversion Pipeline ──────────────────────────
function initImageToAudioFlow() {
  const btn = document.getElementById('son-encode-btn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const imgInput = document.getElementById('son-image-input');
    const modeSelect = document.getElementById('son-audio-mode');
    const placeholder = document.getElementById('son-encode-placeholder');
    const resultPanel = document.getElementById('son-encode-result');
    const errorPanel = document.getElementById('son-encode-error');
    const errorMsg = document.getElementById('son-encode-error-msg');
    const audioPlayer = document.getElementById('son-audio-player');
    const downloadBtn = document.getElementById('son-audio-download');
    const sendToDecodeBtn = document.getElementById('son-send-to-decode');

    if (!imgInput || !imgInput.files.length) {
      showToast('Please select an image file to convert', 'error');
      return;
    }

    placeholder.hidden = false;
    resultPanel.hidden = true;
    errorPanel.hidden = true;
    btn.disabled = true;

    const formData = new FormData();
    formData.append('image', imgInput.files[0]);
    formData.append('mode', modeSelect ? modeSelect.value : 'listenable');

    try {
      const response = await fetch('/api/convert/image-to-audio', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Image to audio conversion failed');
      }

      const blob = await response.blob();
      currentSonificationAudioBlob = blob;
      const audioUrl = URL.createObjectURL(blob);

      audioPlayer.src = audioUrl;
      placeholder.hidden = true;
      resultPanel.hidden = false;
      showToast('Audio waveform synthesized successfully!', 'success');

      downloadBtn.onclick = () => {
        const a = document.createElement('a');
        a.href = audioUrl;
        a.download = `sonification_${modeSelect.value}.wav`;
        a.click();
      };

      if (sendToDecodeBtn) {
        sendToDecodeBtn.onclick = () => {
          // Transfer current blob into Audio-to-Image WAV input
          const file = new File([blob], 'sonification.wav', { type: 'audio/wav' });
          const wavInput = document.getElementById('son-wav-input');
          
          const dt = new DataTransfer();
          dt.items.add(file);
          wavInput.files = dt.files;
          
          handleSelectedFile(file, {
            zone: 'son-wav-zone',
            input: 'son-wav-input',
            idle: 'son-wav-idle',
            preview: 'son-wav-preview',
            info: 'son-wav-info',
            change: 'son-wav-change',
            isImage: false
          });

          // Switch to Audio to Image tab & File sub-tab
          document.getElementById('tab-audio2img').click();
          document.getElementById('src-tab-file').click();
          showToast('Audio loaded into decoder tab!', 'info');
        };
      }

    } catch (err) {
      placeholder.hidden = true;
      errorPanel.hidden = false;
      errorMsg.textContent = err.message;
      showToast('Conversion failed', 'error');
    } finally {
      btn.disabled = false;
    }
  });
}

// ── Audio to Image Reconstruction Pipeline ──────────────────────
function initAudioToImageFlow() {
  const btn = document.getElementById('son-decode-btn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const isFileSource = document.getElementById('src-tab-file').classList.contains('active');
    const wavInput = document.getElementById('son-wav-input');
    const denoiseSelect = document.getElementById('son-denoise-method');
    const kernelRange = document.getElementById('son-kernel-size');
    const fractionRange = document.getElementById('son-keep-fraction');

    const placeholder = document.getElementById('son-decode-placeholder');
    const resultPanel = document.getElementById('son-decode-result');
    const errorPanel = document.getElementById('son-decode-error');
    const errorMsg = document.getElementById('son-decode-error-msg');
    const resultImg = document.getElementById('son-result-img');
    const metaMode = document.getElementById('son-meta-mode');
    const metaDims = document.getElementById('son-meta-dims');
    const downloadBtn = document.getElementById('son-img-download');

    let audioFileToUpload = null;

    if (isFileSource) {
      if (!wavInput || !wavInput.files.length) {
        showToast('Please upload a WAV audio file', 'error');
        return;
      }
      audioFileToUpload = wavInput.files[0];
    } else {
      if (!liveRecordedBlob) {
        showToast('Please record audio using the microphone first', 'error');
        return;
      }
      audioFileToUpload = new File([liveRecordedBlob], 'mic_capture.wav', { type: 'audio/wav' });
    }

    placeholder.hidden = false;
    resultPanel.hidden = true;
    errorPanel.hidden = true;
    btn.disabled = true;

    const formData = new FormData();
    formData.append('audio', audioFileToUpload);
    formData.append('denoise_method', denoiseSelect ? denoiseSelect.value : 'median');
    formData.append('kernel_size', kernelRange ? kernelRange.value : 3);
    formData.append('keep_fraction', fractionRange ? fractionRange.value : 0.35);

    try {
      const response = await fetch('/api/convert/audio-to-image', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Audio to image reconstruction failed');
      }

      const modeName = response.headers.get('X-Decoded-Mode') || 'Unknown';
      const rows = response.headers.get('X-Decoded-Rows') || '?';
      const cols = response.headers.get('X-Decoded-Cols') || '?';

      const blob = await response.blob();
      const imgUrl = URL.createObjectURL(blob);

      resultImg.src = imgUrl;
      metaMode.textContent = modeName;
      metaDims.textContent = `${rows} × ${cols}`;

      placeholder.hidden = true;
      resultPanel.hidden = false;
      showToast('Image reconstructed from audio signal!', 'success');

      downloadBtn.onclick = () => {
        const a = document.createElement('a');
        a.href = imgUrl;
        a.download = 'reconstructed_spectrum.png';
        a.click();
      };

    } catch (err) {
      placeholder.hidden = true;
      errorPanel.hidden = false;
      errorMsg.textContent = err.message;
      showToast('Reconstruction failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });
}

// ── Live Microphone Recorder with pure PCM 16-bit WAV Export ────
function initLiveMicRecorder() {
  const btnRecord = document.getElementById('btn-mic-record');
  const btnStop = document.getElementById('btn-mic-stop');
  const statusText = document.getElementById('mic-status-text');
  const timerText = document.getElementById('mic-timer-text');
  const playbackWrap = document.getElementById('mic-playback-wrap');
  const audioPreview = document.getElementById('mic-audio-preview');

  if (!btnRecord || !btnStop) return;

  let micStream = null;

  btnRecord.addEventListener('click', async () => {
    try {
      const audioConstraints = {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        googEchoCancellation: false,
        googAutoGainControl: false,
        googNoiseSuppression: false,
        googHighpassFilter: false
      };

      try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      } catch (_) {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }

      audioChunks = [];

      let options = {};
      if (MediaRecorder.isTypeSupported('audio/webm')) {
        options.mimeType = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        options.mimeType = 'audio/mp4';
      }

      mediaRecorder = new MediaRecorder(micStream, options);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunks.push(e.data);
        }
      };

      mediaRecorder.start(100);

      const chkAutoPlay = document.getElementById('chk-auto-play-source');
      const sonPlayer = document.getElementById('son-audio-player');
      if (chkAutoPlay && chkAutoPlay.checked && sonPlayer && sonPlayer.src) {
        sonPlayer.currentTime = 0;
        sonPlayer.play().catch(() => {});
      }

      btnRecord.disabled = true;
      btnStop.disabled = false;
      statusText.textContent = 'Recording in progress...';
      statusText.style.color = '#0ff8e7';

      recordStartTime = Date.now();
      recordTimerInterval = setInterval(() => {
        const elapsedSec = Math.floor((Date.now() - recordStartTime) / 1000);
        const mins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
        const secs = String(elapsedSec % 60).padStart(2, '0');
        timerText.textContent = `${mins}:${secs}`;
      }, 500);

      btnStop.onclick = () => {
        clearInterval(recordTimerInterval);

        if (sonPlayer) {
          sonPlayer.pause();
        }

        mediaRecorder.onstop = async () => {
          if (micStream) {
            micStream.getTracks().forEach(track => track.stop());
          }

          statusText.textContent = 'Processing recorded audio...';
          const rawBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });

          try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            if (audioCtx.state === 'suspended') {
              await audioCtx.resume();
            }

            const arrayBuffer = await rawBlob.arrayBuffer();
            const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

            rawRecordedFloat32Samples = audioBuffer.getChannelData(0);
            rawRecordedSampleRate = audioBuffer.sampleRate;

            liveRecordedBlob = encodePCM16Wav(rawRecordedFloat32Samples, rawRecordedSampleRate);
            const audioUrl = URL.createObjectURL(liveRecordedBlob);

            audioPreview.src = audioUrl;
            audioPreview.load();
            playbackWrap.hidden = false;

            const totalDurationSec = audioBuffer.duration;
            setupAudioTrimmerSliders(totalDurationSec);

            statusText.textContent = 'Recording Captured';
            statusText.style.color = '#10b981';
            audioCtx.close();
            showToast('Mic audio captured & ready to play!', 'success');

          } catch (errDecode) {
            console.error('Audio decode error, falling back to raw blob:', errDecode);
            liveRecordedBlob = rawBlob;
            audioPreview.src = URL.createObjectURL(rawBlob);
            audioPreview.load();
            playbackWrap.hidden = false;
            statusText.textContent = 'Recording Captured';
            statusText.style.color = '#10b981';
          } finally {
            btnRecord.disabled = false;
            btnStop.disabled = true;
          }
        };

        mediaRecorder.stop();
      };

    } catch (err) {
      showToast('Microphone access error: ' + err.message, 'error');
    }
  });
}

// ── Audio Trimmer Event Handlers ────────────────────────────────
function setupAudioTrimmerSliders(totalDurationSec) {
  const startRange = document.getElementById('trim-start-range');
  const endRange = document.getElementById('trim-end-range');
  const startDisplay = document.getElementById('trim-start-display');
  const endDisplay = document.getElementById('trim-end-display');
  const badgeDisplay = document.getElementById('trim-duration-badge');

  if (!startRange || !endRange) return;

  const maxSec = Math.max(0.5, totalDurationSec).toFixed(2);
  startRange.min = '0';
  startRange.max = maxSec;
  startRange.value = '0';

  endRange.min = '0';
  endRange.max = maxSec;
  endRange.value = maxSec;

  startDisplay.textContent = '0.00s';
  endDisplay.textContent = `${maxSec}s`;
  badgeDisplay.textContent = `${maxSec}s selected`;

  const onTrimChange = () => {
    updateAudioTrim();
  };

  startRange.oninput = onTrimChange;
  endRange.oninput = onTrimChange;
}

function updateAudioTrim() {
  if (!rawRecordedFloat32Samples || !rawRecordedSampleRate) return;

  const startRange = document.getElementById('trim-start-range');
  const endRange = document.getElementById('trim-end-range');
  const startDisplay = document.getElementById('trim-start-display');
  const endDisplay = document.getElementById('trim-end-display');
  const badgeDisplay = document.getElementById('trim-duration-badge');
  const audioPreview = document.getElementById('mic-audio-preview');

  let startVal = parseFloat(startRange.value) || 0;
  let endVal = parseFloat(endRange.value) || (rawRecordedFloat32Samples.length / rawRecordedSampleRate);

  if (startVal >= endVal) {
    startVal = Math.max(0, endVal - 0.05);
    startRange.value = startVal.toFixed(2);
  }

  const durationSec = (rawRecordedFloat32Samples.length / rawRecordedSampleRate);
  if (endVal > durationSec) endVal = durationSec;

  startDisplay.textContent = startVal.toFixed(2) + 's';
  endDisplay.textContent = endVal.toFixed(2) + 's';
  badgeDisplay.textContent = `${(endVal - startVal).toFixed(2)}s selected`;

  const startIdx = Math.floor(startVal * rawRecordedSampleRate);
  const endIdx = Math.floor(endVal * rawRecordedSampleRate);

  const trimmedSamples = rawRecordedFloat32Samples.subarray(startIdx, endIdx);
  liveRecordedBlob = encodePCM16Wav(trimmedSamples, rawRecordedSampleRate);
  audioPreview.src = URL.createObjectURL(liveRecordedBlob);
  audioPreview.load();
}

// ── Pure JS PCM 16-bit WAV Encoder ──────────────────────────────
function encodePCM16Wav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  /* RIFF identifier */
  writeString(view, 0, 'RIFF');
  /* RIFF chunk length */
  view.setUint32(4, 36 + samples.length * 2, true);
  /* RIFF type */
  writeString(view, 8, 'WAVE');
  /* format chunk identifier */
  writeString(view, 12, 'fmt ');
  /* format chunk length */
  view.setUint32(16, 16, true);
  /* sample format (raw PCM int16) */
  view.setUint16(20, 1, true);
  /* channel count (mono) */
  view.setUint16(22, 1, true);
  /* sample rate */
  view.setUint32(24, sampleRate, true);
  /* byte rate (sampleRate * 2) */
  view.setUint32(28, sampleRate * 2, true);
  /* block align */
  view.setUint16(32, 2, true);
  /* bits per sample */
  view.setUint16(34, 16, true);
  /* data chunk identifier */
  writeString(view, 36, 'data');
  /* data chunk length */
  view.setUint32(40, samples.length * 2, true);

  // Write float32 samples to int16
  let ptr = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(ptr, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    ptr += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}
