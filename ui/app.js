/**
 * AphanesKyma — Frontend Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initCanvasAnimation();
  initDragAndDrop();
  initPayloadSwitcher();
  initPasswordToggles();
  initPasswordStrength();
  initPipelines();
  initAudioPipeline();
});

// ── Navigation ──────────────────────────────────────────────────
function initNavigation() {
  const sections = document.querySelectorAll('.studio-section, .hero-section');
  const navLinks = document.querySelectorAll('.nav-link');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');
          navLinks.forEach((link) => {
            link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
          });
        }
      });
    },
    { threshold: 0.3 }
  );

  sections.forEach((section) => observer.observe(section));
}

// ── Canvas Animation ────────────────────────────────────────────
function initCanvasAnimation() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let width, height;
  let particles = [];

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  window.addEventListener('resize', resize);
  resize();

  class Particle {
    constructor() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * 0.5;
      this.vy = (Math.random() - 0.5) * 0.5;
      this.size = Math.random() * 2;
      this.color = Math.random() > 0.5 ? 'rgba(15, 248, 231, 0.4)' : 'rgba(168, 85, 247, 0.4)';
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0 || this.x > width) this.vx *= -1;
      if (this.y < 0 || this.y > height) this.vy *= -1;
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = this.color;
      ctx.fill();
    }
  }

  for (let i = 0; i < 50; i++) particles.push(new Particle());

  function animate() {
    ctx.clearRect(0, 0, width, height);
    particles.forEach(p => { p.update(); p.draw(); });

    for (let i = 0; i < particles.length; i++) {
      for (let j = i; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 100) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.1 - dist / 1000})`;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(animate);
  }

  animate();
}

// ── Drag and Drop ───────────────────────────────────────────────
function initDragAndDrop() {
  const zones = [
    { zone: 'encode-cover-zone', input: 'encode-cover-input', idle: 'encode-cover-idle', preview: 'encode-cover-preview', img: 'encode-cover-img', info: 'encode-cover-info', change: 'encode-cover-change' },
    { zone: 'encode-secret-zone', input: 'encode-secret-input', idle: 'encode-secret-idle', preview: 'encode-secret-preview', img: 'encode-secret-img', info: 'encode-secret-info', change: 'encode-secret-change' },
    { zone: 'decode-stego-zone', input: 'decode-stego-input', idle: 'decode-stego-idle', preview: 'decode-stego-preview', img: 'decode-stego-img', info: 'decode-stego-info', change: 'decode-stego-change' },
    { zone: 'audio-image-zone', input: 'audio-image-input', idle: 'audio-image-idle', preview: 'audio-image-preview', img: 'audio-image-img', info: 'audio-image-info', change: 'audio-image-change' },
  ];

  zones.forEach(z => {
    const zoneEl = document.getElementById(z.zone);
    const inputEl = document.getElementById(z.input);
    const idleEl = document.getElementById(z.idle);
    const previewEl = document.getElementById(z.preview);
    const imgEl = document.getElementById(z.img);
    const infoEl = document.getElementById(z.info);
    const changeBtn = document.getElementById(z.change);

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
        handleFileSelection(inputEl.files[0], idleEl, previewEl, imgEl, infoEl);
      }
    });

    inputEl.addEventListener('change', () => {
      if (inputEl.files.length) {
        handleFileSelection(inputEl.files[0], idleEl, previewEl, imgEl, infoEl);
      }
    });

    changeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      inputEl.value = '';
      idleEl.hidden = false;
      previewEl.hidden = true;
    });
  });
}

function handleFileSelection(file, idleEl, previewEl, imgEl, infoEl) {
  if (!file.type.startsWith('image/')) {
    showToast('Please select an image file', 'error');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    imgEl.src = e.target.result;
    const kb = (file.size / 1024).toFixed(1);
    infoEl.textContent = `${file.name} (${kb} KB)`;
    idleEl.hidden = true;
    previewEl.hidden = false;
  };
  reader.readAsDataURL(file);
}

// ── Payload Switcher ────────────────────────────────────────────
function initPayloadSwitcher() {
  const tabText = document.getElementById('tab-text');
  const tabImage = document.getElementById('tab-image');
  const paneText = document.getElementById('pane-text');
  const paneImage = document.getElementById('pane-image');

  if (!tabText || !tabImage) return;

  tabText.addEventListener('click', () => {
    tabText.classList.add('active');
    tabImage.classList.remove('active');
    tabText.setAttribute('aria-selected', 'true');
    tabImage.setAttribute('aria-selected', 'false');
    paneText.hidden = false;
    paneImage.hidden = true;
  });

  tabImage.addEventListener('click', () => {
    tabImage.classList.add('active');
    tabText.classList.remove('active');
    tabImage.setAttribute('aria-selected', 'true');
    tabText.setAttribute('aria-selected', 'false');
    paneImage.hidden = false;
    paneText.hidden = true;
  });

  const msgInput = document.getElementById('encode-message');
  const msgCount = document.getElementById('encode-msg-count');
  if (msgInput && msgCount) {
    msgInput.addEventListener('input', () => {
      msgCount.textContent = `${msgInput.value.length} chars`;
    });
  }
}

// ── Password Toggles ────────────────────────────────────────────
function initPasswordToggles() {
  const toggles = document.querySelectorAll('.password-toggle');
  toggles.forEach(toggle => {
    toggle.addEventListener('click', () => {
      const input = toggle.previousElementSibling;
      const eyeOpen = toggle.querySelector('.eye-open');
      const eyeClosed = toggle.querySelector('.eye-closed');

      if (input.type === 'password') {
        input.type = 'text';
        eyeOpen.style.display = 'none';
        eyeClosed.style.display = 'block';
      } else {
        input.type = 'password';
        eyeOpen.style.display = 'block';
        eyeClosed.style.display = 'none';
      }
    });
  });
}

// ── Password Strength ───────────────────────────────────────────
function initPasswordStrength() {
  const pwInput = document.getElementById('encode-password');
  const strengthFill = document.getElementById('encode-strength-fill');
  const strengthLabel = document.getElementById('encode-strength-label');

  if (!pwInput || !strengthFill) return;

  pwInput.addEventListener('input', () => {
    const val = pwInput.value;
    let strength = 0;

    if (val.length > 0) strength += 25;
    if (val.length > 7) strength += 25;
    if (/[A-Z]/.test(val) && /[a-z]/.test(val)) strength += 25;
    if (/[0-9]/.test(val) && /[^A-Za-z0-9]/.test(val)) strength += 25;

    strengthFill.style.width = `${strength}%`;

    if (strength === 0) {
      strengthFill.style.background = 'transparent';
      strengthLabel.textContent = '';
    } else if (strength <= 25) {
      strengthFill.style.background = '#ef4444';
      strengthLabel.textContent = 'Weak';
      strengthLabel.style.color = '#ef4444';
    } else if (strength <= 50) {
      strengthFill.style.background = '#eab308';
      strengthLabel.textContent = 'Fair';
      strengthLabel.style.color = '#eab308';
    } else if (strength <= 75) {
      strengthFill.style.background = '#3b82f6';
      strengthLabel.textContent = 'Good';
      strengthLabel.style.color = '#3b82f6';
    } else {
      strengthFill.style.background = '#10b981';
      strengthLabel.textContent = 'Strong';
      strengthLabel.style.color = '#10b981';
    }
  });
}

// ── Encode & Decode Pipelines ────────────────────────────────────
function initPipelines() {
  const encodeBtn = document.getElementById('encode-btn');
  const decodeBtn = document.getElementById('decode-btn');

  if (encodeBtn) {
    encodeBtn.addEventListener('click', () => {
      const coverInput = document.getElementById('encode-cover-input');
      const pwInput = document.getElementById('encode-password');
      if (!coverInput.files.length) {
        showToast('Please select a cover image', 'error');
        return;
      }
      if (!pwInput.value) {
        showToast('Please enter a passphrase', 'error');
        return;
      }
      runEncodePipeline();
    });
  }

  if (decodeBtn) {
    decodeBtn.addEventListener('click', () => {
      const stegoInput = document.getElementById('decode-stego-input');
      const pwInput = document.getElementById('decode-password');
      if (!stegoInput.files.length) {
        showToast('Please select a stego image', 'error');
        return;
      }
      if (!pwInput.value) {
        showToast('Please enter a passphrase', 'error');
        return;
      }
      runDecodePipeline();
    });
  }
}

// ── Helper: safely parse API error ──────────────────────────────
async function parseApiError(response, fallback) {
  try {
    const data = await response.json();
    return data.detail || fallback;
  } catch (_) {
    try {
      const text = await response.text();
      return text.trim() || fallback;
    } catch (_) {
      return fallback;
    }
  }
}

// ── Encode Pipeline ─────────────────────────────────────────────
async function runEncodePipeline() {
  const placeholder = document.getElementById('encode-placeholder');
  const pipeline    = document.getElementById('encode-pipeline');
  const result      = document.getElementById('encode-result');
  const errorEl     = document.getElementById('encode-error');

  placeholder.hidden = true;
  result.hidden      = true;
  errorEl.hidden     = true;
  pipeline.hidden    = false;

  const steps = [
    { id: 'pipe-load',    label: 'Reading pixels and analyzing capacity...' },
    { id: 'pipe-encrypt', label: 'AES-256-GCM encryption applied' },
    { id: 'pipe-dct',     label: 'Applying selected transform (DCT/FFT)...' },
    { id: 'pipe-embed',   label: 'Embedding payload in frequency coefficients...' },
    { id: 'pipe-save',    label: 'Generating lossless PNG...' },
  ];

  const setStep = (id, state, text) => {
    const el = document.getElementById(id);
    el.className = `pipeline-step${state ? ' ' + state : ''}`;
    el.querySelector('.pipe-status').textContent = text || '';
  };

  steps.forEach(s => setStep(s.id, '', ''));

  const isText   = document.getElementById('tab-text').classList.contains('active');
  const cover    = document.getElementById('encode-cover-input').files[0];
  const password = document.getElementById('encode-password').value;
  const method   = document.getElementById('encode-method')?.value || 'dct';
  const quant    = document.getElementById('encode-quant')?.value  || '8';

  const formData = new FormData();
  formData.append('cover', cover);
  formData.append('password', password);
  formData.append('method', method);
  formData.append('quantization_step', quant);

  let endpoint = '';
  if (isText) {
    const message = document.getElementById('encode-message').value;
    if (!message) { showToast('Message is empty', 'error'); return; }
    formData.append('message', message);
    endpoint = '/api/encode/text';
  } else {
    const secretFile = document.getElementById('encode-secret-input').files[0];
    if (!secretFile) { showToast('Secret image is missing', 'error'); return; }
    formData.append('secret', secretFile);
    endpoint = '/api/encode/image';
  }

  // Animate first two steps locally while request is in-flight
  for (let i = 0; i < 2; i++) {
    setStep(steps[i].id, 'active', 'Processing...');
    await new Promise(r => setTimeout(r, 300));
    setStep(steps[i].id, 'done', steps[i].label);
  }

  setStep('pipe-dct', 'active', 'Awaiting server response...');

  try {
    const response = await fetch(endpoint, { method: 'POST', body: formData });

    if (!response.ok) {
      const msg = await parseApiError(response, 'Encoding failed');
      throw new Error(msg);
    }

    setStep('pipe-dct',   'done', steps[2].label);
    setStep('pipe-embed', 'active', 'Processing...');
    await new Promise(r => setTimeout(r, 150));
    setStep('pipe-embed', 'done', steps[3].label);
    setStep('pipe-save',  'active', 'Processing...');
    await new Promise(r => setTimeout(r, 150));
    setStep('pipe-save',  'done', steps[4].label);

    // Metrics from response headers
    const payloadSize = response.headers.get('X-Metrics-Payload') || '-';
    const bits        = response.headers.get('X-Metrics-Bits')    || '-';
    const psnr        = response.headers.get('X-Metrics-PSNR')    || '-';
    const mse         = response.headers.get('X-Metrics-MSE')     || '-';

    const blob = await response.blob();
    const url  = URL.createObjectURL(blob);

    pipeline.hidden = true;
    result.hidden   = false;

    document.getElementById('encode-result-img').src = url;
    document.getElementById('metric-payload').textContent = payloadSize + ' bytes';
    document.getElementById('metric-bits').textContent    = bits;
    document.getElementById('metric-psnr').textContent    = psnr + ' dB';
    document.getElementById('metric-mse').textContent     = mse;

    document.getElementById('encode-download-btn').onclick = () => {
      const a = document.createElement('a');
      a.href = url;
      a.download = 'stego.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
    };

    showToast('Image encoded successfully!', 'success');

  } catch (err) {
    pipeline.hidden = true;
    errorEl.hidden  = false;
    document.getElementById('encode-error-msg').textContent = err.message;
    showToast('Encoding failed', 'error');
  }
}

// ── Decode Pipeline ─────────────────────────────────────────────
async function runDecodePipeline() {
  const placeholder  = document.getElementById('decode-placeholder');
  const resultText   = document.getElementById('decode-result-text');
  const resultImage  = document.getElementById('decode-result-image');
  const errorEl      = document.getElementById('decode-error');

  placeholder.hidden = false;
  resultText.hidden  = true;
  resultImage.hidden = true;
  errorEl.hidden     = true;

  const placeholderP = placeholder.querySelector('p');
  if (placeholderP) placeholderP.textContent = 'Extracting and decrypting...';

  const stego    = document.getElementById('decode-stego-input').files[0];
  const password = document.getElementById('decode-password').value;
  const method   = document.getElementById('decode-method')?.value  || 'dct';
  const quant    = document.getElementById('decode-quant')?.value   || '8';

  const formData = new FormData();
  formData.append('stego',              stego);
  formData.append('password',           password);
  formData.append('method',             method);
  formData.append('quantization_step',  quant);

  try {
    const response = await fetch('/api/decode', { method: 'POST', body: formData });

    if (!response.ok) {
      const msg = await parseApiError(response, 'Decoding failed');
      throw new Error(msg);
    }

    placeholder.hidden = true;
    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
      const data = await response.json();
      resultText.hidden = false;
      document.getElementById('decode-message-text').textContent = data.data;
      showToast('Secret message revealed!', 'success');

      const copyBtn = document.getElementById('decode-copy-btn');
      if (copyBtn) {
        copyBtn.onclick = () => {
          navigator.clipboard.writeText(data.data);
          showToast('Copied to clipboard', 'success');
        };
      }

    } else {
      const blob = await response.blob();
      const url  = URL.createObjectURL(blob);
      resultImage.hidden = false;
      document.getElementById('decode-result-img').src = url;
      showToast('Secret image revealed!', 'success');

      const downloadBtn = document.getElementById('decode-download-btn');
      if (downloadBtn) {
        downloadBtn.onclick = () => {
          const a = document.createElement('a');
          a.href = url;
          a.download = 'secret.png';
          document.body.appendChild(a);
          a.click();
          a.remove();
        };
      }
    }

  } catch (err) {
    placeholder.hidden = true;
    errorEl.hidden     = false;

    // Provide human-readable hint for common decryption errors
    let msg = err.message;
    if (msg.toLowerCase().includes('invalidtag') || msg.includes('decryption')) {
      msg = 'Decryption failed — wrong passphrase or mismatched quantization step / method.';
    } else if (msg.toLowerCase().includes('not an aphaneskyma')) {
      msg = 'This image does not appear to contain AphanesKyma steganography data.';
    }

    document.getElementById('decode-error-msg').textContent = msg;
    showToast('Decoding failed', 'error');
  }
}

// ── Audio Pipeline ─────────────────────────────────────────────
function initAudioPipeline() {
  const convertBtn = document.getElementById('audio-convert-btn');
  if (convertBtn) {
    convertBtn.addEventListener('click', runImageToAudioPipeline);
  }
}

async function runImageToAudioPipeline() {
  const imgInput = document.getElementById('audio-image-input');
  const modeSelect = document.getElementById('audio-mode');
  
  const convertBtn = document.getElementById('audio-convert-btn');
  const placeholder = document.getElementById('audio-placeholder');
  const resultPanel = document.getElementById('audio-result');
  const audioPlayer = document.getElementById('audio-player');
  const downloadBtn = document.getElementById('audio-download-btn');

  if (!imgInput.files[0]) {
    showToast("Please upload an image to convert.", "error");
    return;
  }

  // Reset UI
  resultPanel.hidden = true;
  convertBtn.hidden = true;
  placeholder.hidden = false;

  const formData = new FormData();
  formData.append('image', imgInput.files[0]);
  formData.append('mode', modeSelect ? modeSelect.value : 'fidelity');

  try {
    const res = await fetch('/api/convert/image-to-audio', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Conversion failed");
    }

    const blob = await res.blob();
    const audioUrl = URL.createObjectURL(blob);
    
    audioPlayer.src = audioUrl;
    resultPanel.hidden = false;
    showToast("Conversion successful!", "success");

    downloadBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = audioUrl;
      a.download = `sonification_${modeSelect.value}.wav`;
      a.click();
    };

  } catch (err) {
    showToast("Error: " + err.message, "error");
  } finally {
    placeholder.hidden = true;
    convertBtn.hidden = false;
  }
}

// ── Toast Notifications ─────────────────────────────────────────
function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  let icon = '';
  if (type === 'success') icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
  if (type === 'error')   icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;

  toast.innerHTML = `${icon}<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => toast.remove(), 4000);
}
