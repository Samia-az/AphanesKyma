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
  initEncodeDecodePipelines();
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
    particles.forEach(p => {
      p.update();
      p.draw();
    });
    
    // Draw lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        if (dist < 100) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.1 - dist/1000})`;
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

  // Text message counter
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
      strengthFill.style.background = '#ef4444'; // Red
      strengthLabel.textContent = 'Weak';
      strengthLabel.style.color = '#ef4444';
    } else if (strength <= 50) {
      strengthFill.style.background = '#eab308'; // Yellow
      strengthLabel.textContent = 'Fair';
      strengthLabel.style.color = '#eab308';
    } else if (strength <= 75) {
      strengthFill.style.background = '#3b82f6'; // Blue
      strengthLabel.textContent = 'Good';
      strengthLabel.style.color = '#3b82f6';
    } else {
      strengthFill.style.background = '#10b981'; // Green
      strengthLabel.textContent = 'Strong';
      strengthLabel.style.color = '#10b981';
    }
  });
}

// ── Mock Encoding/Decoding Pipelines ────────────────────────────
// In a real implementation, this will send FormData to your Python backend
function initEncodeDecodePipelines() {
  const encodeBtn = document.getElementById('encode-btn');
  const decodeBtn = document.getElementById('decode-btn');

  if (encodeBtn) {
    encodeBtn.addEventListener('click', () => {
      // Validate inputs
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

      runEncodeMockPipeline();
    });
  }

  if (decodeBtn) {
    decodeBtn.addEventListener('click', () => {
       // Validate inputs
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
 
       runDecodeMockPipeline();
    });
  }
}

async function runEncodeMockPipeline() {
  const placeholder = document.getElementById('encode-placeholder');
  const pipeline = document.getElementById('encode-pipeline');
  const result = document.getElementById('encode-result');
  const errorEl = document.getElementById('encode-error');
  
  placeholder.hidden = true;
  result.hidden = true;
  errorEl.hidden = true;
  pipeline.hidden = false;

  const steps = [
    { id: 'pipe-load', status: 'Reading pixels and analyzing capacity...' },
    { id: 'pipe-encrypt', status: 'AES-256-GCM encryption applied' },
    { id: 'pipe-dct', status: 'Applying selected transform (DCT/FFT)...' },
    { id: 'pipe-embed', status: 'Embedding payload in frequency coefficients...' },
    { id: 'pipe-save', status: 'Generating lossless PNG...' },
  ];

  // Reset steps
  steps.forEach(s => {
    const el = document.getElementById(s.id);
    el.className = 'pipeline-step';
    el.querySelector('.pipe-status').textContent = '';
  });

  const tabText = document.getElementById('tab-text').classList.contains('active');
  const formData = new FormData();
  
  const coverFile = document.getElementById('encode-cover-input').files[0];
  const password = document.getElementById('encode-password').value;
  const method = document.getElementById('encode-method').value;
  const quant = document.getElementById('encode-quant').value;
  
  formData.append('cover', coverFile);
  formData.append('password', password);
  formData.append('method', method);
  formData.append('quantization_step', quant);

  let endpoint = '';
  if (tabText) {
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

  // Visual simulation for upload start
  for (let i = 0; i < 2; i++) {
      const el = document.getElementById(steps[i].id);
      el.classList.add('active');
      el.querySelector('.pipe-status').textContent = 'Processing...';
      await new Promise(r => setTimeout(r, 300));
      el.classList.remove('active');
      el.classList.add('done');
      el.querySelector('.pipe-status').textContent = steps[i].status;
  }

  const elDct = document.getElementById('pipe-dct');
  elDct.classList.add('active');
  elDct.querySelector('.pipe-status').textContent = 'Awaiting API response...';

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to encode');
    }
    
    elDct.classList.remove('active'); elDct.classList.add('done');
    elDct.querySelector('.pipe-status').textContent = steps[2].status;
    
    const elEmbed = document.getElementById('pipe-embed');
    elEmbed.classList.add('active');
    await new Promise(r => setTimeout(r, 200));
    elEmbed.classList.remove('active'); elEmbed.classList.add('done');
    elEmbed.querySelector('.pipe-status').textContent = steps[3].status;
    
    const elSave = document.getElementById('pipe-save');
    elSave.classList.add('active');
    await new Promise(r => setTimeout(r, 200));
    elSave.classList.remove('active'); elSave.classList.add('done');
    elSave.querySelector('.pipe-status').textContent = steps[4].status;

    // Get metrics from headers
    const payloadSize = response.headers.get('X-Metrics-Payload') || '-';
    const bits = response.headers.get('X-Metrics-Bits') || '-';
    const psnr = response.headers.get('X-Metrics-PSNR') || '-';
    const mse = response.headers.get('X-Metrics-MSE') || '-';

    // Get the image blob
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    pipeline.hidden = true;
    result.hidden = false;
    
    document.getElementById('encode-result-img').src = url;
    document.getElementById('metric-payload').textContent = payloadSize + ' bytes';
    document.getElementById('metric-bits').textContent = bits;
    document.getElementById('metric-psnr').textContent = psnr + ' dB';
    document.getElementById('metric-mse').textContent = mse;
    
    const downloadBtn = document.getElementById('encode-download-btn');
    downloadBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = url;
      a.download = 'stego.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
    };

    showToast('Image successfully encoded!', 'success');

  } catch (err) {
    pipeline.hidden = true;
    errorEl.hidden = false;
    document.getElementById('encode-error-msg').textContent = err.message;
    showToast('Encoding failed', 'error');
  }
}

async function runDecodeMockPipeline() {
  const placeholder = document.getElementById('decode-placeholder');
  const resultText = document.getElementById('decode-result-text');
  const resultImage = document.getElementById('decode-result-image');
  const errorEl = document.getElementById('decode-error');
  
  placeholder.hidden = false;
  resultText.hidden = true;
  resultImage.hidden = true;
  errorEl.hidden = true;

  placeholder.querySelector('p').textContent = 'Extracting and decrypting...';
  
  const formData = new FormData();
  const stegoFile = document.getElementById('decode-stego-input').files[0];
  const password = document.getElementById('decode-password').value;
  const method = document.getElementById('decode-method').value;

  formData.append('stego', stegoFile);
  formData.append('password', password);
  formData.append('method', method);

  try {
    const response = await fetch('/api/decode', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to decode');
    }

    const contentType = response.headers.get('content-type');
    placeholder.hidden = true;

    if (contentType && contentType.includes('application/json')) {
      const data = await response.json();
      resultText.hidden = false;
      document.getElementById('decode-message-text').textContent = data.data;
      showToast('Secret message revealed successfully', 'success');
      
      const copyBtn = document.getElementById('decode-copy-btn');
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(data.data);
        showToast('Copied to clipboard', 'info');
      };
      
    } else {
      // It's an image
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      resultImage.hidden = false;
      document.getElementById('decode-result-img').src = url;
      showToast('Secret image revealed successfully', 'success');

      const downloadBtn = document.getElementById('decode-download-btn');
      downloadBtn.onclick = () => {
        const a = document.createElement('a');
        a.href = url;
        a.download = 'secret.png';
        document.body.appendChild(a);
        a.click();
        a.remove();
      };
    }

  } catch (err) {
    placeholder.hidden = true;
    errorEl.hidden = false;
    document.getElementById('decode-error-msg').textContent = err.message;
    showToast('Decoding failed', 'error');
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
  if (type === 'error') icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;

  toast.innerHTML = `${icon}<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
}
