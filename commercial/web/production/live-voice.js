/* Hands-free, turn-based voice. Callbacks retain the editor's authorization gates. */
class AvanLiveVoice {
  constructor({transcribe, turn, speech, cancelCurrent}) {
    Object.assign(this, {transcribe, turn, speech, cancelCurrent});
    this.active = false;
  }
  async open() {
    if (this.active) return;
    this.active = true;
    this.controller = new AbortController();
    const signal = this.controller.signal;
    this.dialog = document.createElement('dialog');
    this.dialog.className = 'live-voice-dialog';
    this.dialog.dir = 'rtl';
    this.dialog.setAttribute('aria-label', 'گفتگوی صوتی با اوان');
    this.dialog.innerHTML = '<button class="voice-close" aria-label="پایان گفتگو">×</button><h2>گفتگو با اوان</h2><canvas width="560" height="400" aria-hidden="true"></canvas><p role="status" aria-live="polite"></p><p class="voice-hint">هر بار صحبت کنید و کمی مکث کنید. ارسال نهایی فرم با تأیید شما انجام می‌شود.</p><button class="voice-interrupt">پایان صحبت</button>';
    this.status = this.dialog.querySelector('[role=status]');
    this.button = this.dialog.querySelector('.voice-interrupt');
    this.canvas = this.dialog.querySelector('canvas');
    document.body.append(this.dialog);
    this.dialog.showModal();
    this.dialog.querySelector('.voice-close').onclick = () => this.close();
    this.dialog.addEventListener('cancel', e => { e.preventDefault(); this.close(); });
    this.button.onclick = () => {
      if (this.state === 'listening') this.finishTurn();
      else if (this.state === 'speaking') { this.stopPlayback(); this.listen(); }
    };
    this.visibility = () => { if (document.hidden) this.close(); };
    document.addEventListener('visibilitychange', this.visibility);
    this.timer = setTimeout(() => this.close(), 15 * 60 * 1000);
    this.setState('connecting', 'در حال اتصال به میکروفون…');
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw Error('این مرورگر ضبط صدا را پشتیبانی نمی‌کند؛ از مرورگر جدید و اتصال HTTPS استفاده کنید.');
      const stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
      if (signal.aborted) { stream.getTracks().forEach(t => t.stop()); return; }
      this.stream = stream;
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      await this.audioContext.resume();
      if (signal.aborted) return;
      this.mic = this.audioContext.createMediaStreamSource(stream);
      this.micAnalyser = this.audioContext.createAnalyser();
      this.micAnalyser.fftSize = 512;
      this.mic.connect(this.micAnalyser);
      this.draw();
      this.listen();
    } catch (error) { if (!signal.aborted) this.fail(error); }
  }
  setState(state, message) {
    this.state = state;
    this.status.textContent = message;
    this.button.disabled = !['listening', 'speaking'].includes(state);
    this.button.textContent = state === 'speaking' ? 'نوبت من' : 'پایان صحبت';
  }
  listen() {
    if (!this.active || this.controller.signal.aborted) return;
    this.stopPlayback();
    this.chunks = [];
    this.heard = false;
    this.started = performance.now();
    this.lastSound = this.started;
    const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm'].find(t => MediaRecorder.isTypeSupported(t));
    try {
      const recorder = new MediaRecorder(this.stream, mimeType ? {mimeType} : {});
      this.recorder = recorder;
      recorder.ondataavailable = e => { if (e.data.size) this.chunks.push(e.data); };
      recorder.onstop = () => {
        if (!this.active || this.controller.signal.aborted) return;
        const blob = new Blob(this.chunks, {type: recorder.mimeType});
        if (this.heard && blob.size) this.process(blob);
        else this.listen();
      };
      recorder.onerror = () => this.fail(Error('ضبط صدا متوقف شد؛ دوباره مکالمه را باز کنید.'));
      recorder.start(250);
      this.setState('listening', 'گوش می‌دهم…');
    } catch (error) { this.fail(error); }
  }
  finishTurn() {
    if (this.recorder?.state === 'recording') {
      this.setState('thinking', 'در حال دریافت صحبت شما…');
      this.recorder.stop();
    }
  }
  async process(blob) {
    const signal = this.controller.signal;
    try {
      const text = await this.transcribe(blob, signal);
      if (signal.aborted) return;
      if (!String(text || '').trim()) { this.listen(); return; }
      this.setState('thinking', 'اوان در حال پاسخ دادن است…');
      await this.turn(text, signal);
      if (signal.aborted) return;
      // Keep the thinking state while fetching; interruption becomes available
      // only when an actual audio object can be cancelled.
      for (let part = 0, parts = 1; part < parts; part++) {
        const result = await this.speech(part, signal);
        if (signal.aborted) return;
        parts = Math.min(20, Math.max(1, Number(result.parts) || 1));
        this.setState('speaking', 'اوان صحبت می‌کند…');
        const completed = await this.play(result.blob);
        if (!completed || signal.aborted) return;
        if (part + 1 < parts) this.setState('thinking', 'ادامهٔ پاسخ…');
      }
      this.listen();
    } catch (error) { if (!signal.aborted) this.fail(error); }
  }
  play(blob) {
    this.stopPlayback();
    this.url = URL.createObjectURL(blob);
    this.audio = new Audio(this.url);
    this.output = this.audioContext.createMediaElementSource(this.audio);
    this.outputAnalyser = this.audioContext.createAnalyser();
    this.outputAnalyser.fftSize = 512;
    this.output.connect(this.outputAnalyser);
    this.outputAnalyser.connect(this.audioContext.destination);
    return new Promise((resolve, reject) => {
      this.resolvePlayback = resolve;
      this.audio.onended = () => { this.stopPlayback(true); };
      this.audio.onerror = () => { this.stopPlayback(); reject(Error('پخش پاسخ صوتی ممکن نشد.')); };
      this.audio.play().catch(error => { this.stopPlayback(); reject(error); });
    });
  }
  stopPlayback(completed = false) {
    if (this.audio) { this.audio.onended = null; this.audio.onerror = null; this.audio.pause(); this.audio.removeAttribute('src'); this.audio.load(); }
    this.output?.disconnect();
    this.outputAnalyser?.disconnect();
    if (this.url) URL.revokeObjectURL(this.url);
    this.resolvePlayback?.(completed);
    this.resolvePlayback = null;
    this.output = this.outputAnalyser = this.audio = this.url = null;
  }
  draw() {
    if (!this.active) return;
    const analyser = this.state === 'speaking' ? this.outputAnalyser : this.micAnalyser;
    let rms = 0;
    if (analyser) {
      const data = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(data);
      rms = Math.sqrt(data.reduce((sum, n) => sum + ((n - 128) / 128) ** 2, 0) / data.length);
    }
    const now = performance.now();
    if (this.state === 'listening') {
      if (rms > .022) { this.heard = true; this.lastSound = now; }
      if ((this.heard && now - this.lastSound > 1100) || now - this.started > 45000) this.finishTurn();
    }
    this.level = (this.level || 0) * .75 + Math.min(1, rms * 8) * .25;
    const ctx = this.canvas.getContext('2d'), x = 280, y = 200, r = 88 + this.level * 46;
    ctx.clearRect(0, 0, 560, 400);
    for (let n = 0; n < 3; n++) {
      const wave = ((now / 2200 + n / 3) % 1);
      ctx.beginPath(); ctx.arc(x, y, r + 12 + wave * (45 + this.level * 28), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(69,177,255,${(1 - wave) * (.13 + this.level * .45)})`;
      ctx.lineWidth = 1.5; ctx.stroke();
    }
    const gradient = ctx.createRadialGradient(x - r * .3, y - r * .35, r * .05, x, y, r);
    gradient.addColorStop(0, '#d5f8ff'); gradient.addColorStop(.3, '#59d7ed'); gradient.addColorStop(.7, '#3686e8'); gradient.addColorStop(1, '#344ba6');
    ctx.shadowColor = '#59cfff'; ctx.shadowBlur = 24 + this.level * 30;
    ctx.fillStyle = gradient; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
    this.frame = requestAnimationFrame(() => this.draw());
  }
  fail(error) {
    this.release();
    this.setState('error', error?.name === 'NotAllowedError' ? 'دسترسی میکروفون داده نشد. مجوز مرورگر را بررسی کنید.' : (error?.message || 'ارتباط صوتی قطع شد.'));
  }
  release() {
    this.active = false;
    this.controller?.abort();
    this.cancelCurrent?.();
    if (this.recorder?.state === 'recording') { this.recorder.onstop = null; this.recorder.stop(); }
    this.stream?.getTracks().forEach(t => t.stop());
    this.stopPlayback();
    this.mic?.disconnect();
    this.audioContext?.close().catch(() => {});
    cancelAnimationFrame(this.frame);
    clearTimeout(this.timer);
    document.removeEventListener('visibilitychange', this.visibility);
  }
  close() {
    this.release();
    this.dialog?.close();
    this.dialog?.remove();
  }
}
window.AvanLiveVoice = AvanLiveVoice;
