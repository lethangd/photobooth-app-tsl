/**
 * Tiny synthesized UI sounds (Web Audio, no asset files): pop, whoosh, shutter, chime, error.
 * Browsers only allow audio after a user gesture; the first tap on the kiosk unlocks it.
 */

let ctx: AudioContext | null = null;
let enabled = true;

export function setSoundEnabled(value: boolean): void {
  enabled = value;
}

function audio(): AudioContext | null {
  if (!enabled) return null;
  try {
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

function envelope(
  ac: AudioContext,
  peak: number,
  attack: number,
  release: number,
  at = ac.currentTime,
): GainNode {
  const gain = ac.createGain();
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(peak, at + attack);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + attack + release);
  gain.connect(ac.destination);
  return gain;
}

function noise(ac: AudioContext, seconds: number): AudioBufferSourceNode {
  const buffer = ac.createBuffer(1, Math.ceil(ac.sampleRate * seconds), ac.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
  const source = ac.createBufferSource();
  source.buffer = buffer;
  return source;
}

function tone(
  ac: AudioContext,
  type: OscillatorType,
  from: number,
  to: number,
  at: number,
  length: number,
  peak: number,
): void {
  const osc = ac.createOscillator();
  osc.type = type;
  osc.frequency.setValueAtTime(from, at);
  osc.frequency.exponentialRampToValueAtTime(to, at + length);
  osc.connect(envelope(ac, peak, 0.008, length, at));
  osc.start(at);
  osc.stop(at + length + 0.05);
}

export function pop(): void {
  const ac = audio();
  if (!ac) return;
  tone(ac, "sine", 720, 260, ac.currentTime, 0.09, 0.22);
}

export function whoosh(): void {
  const ac = audio();
  if (!ac) return;
  const source = noise(ac, 0.45);
  const filter = ac.createBiquadFilter();
  filter.type = "bandpass";
  filter.Q.value = 0.9;
  filter.frequency.setValueAtTime(380, ac.currentTime);
  filter.frequency.exponentialRampToValueAtTime(2600, ac.currentTime + 0.32);
  source.connect(filter);
  filter.connect(envelope(ac, 0.18, 0.12, 0.3));
  source.start();
}

export function shutter(): void {
  const ac = audio();
  if (!ac) return;
  for (const offset of [0, 0.075]) {
    const at = ac.currentTime + offset;
    const source = noise(ac, 0.06);
    const filter = ac.createBiquadFilter();
    filter.type = "highpass";
    filter.frequency.value = 1800;
    source.connect(filter);
    filter.connect(envelope(ac, 0.35, 0.002, 0.045, at));
    source.start(at);
  }
}

export function chime(): void {
  const ac = audio();
  if (!ac) return;
  tone(ac, "sine", 880, 880, ac.currentTime, 0.32, 0.16);
  tone(ac, "sine", 1318, 1318, ac.currentTime + 0.12, 0.45, 0.14);
}

export function error(): void {
  const ac = audio();
  if (!ac) return;
  tone(ac, "triangle", 240, 200, ac.currentTime, 0.12, 0.2);
  tone(ac, "triangle", 240, 180, ac.currentTime + 0.16, 0.16, 0.2);
}
