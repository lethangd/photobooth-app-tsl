/**
 * Fallback camera running in the browser (getUserMedia): the laptop webcam on the kiosk,
 * or the front camera when the kiosk is opened on a phone/tablet. Used when the server
 * camera is unavailable and in the public demo.
 *
 * Browsers only expose cameras on secure origins: https, localhost or 127.0.0.1.
 */

let stream: MediaStream | null = null;

export function browserCameraSupported(): boolean {
  return Boolean(window.isSecureContext && navigator.mediaDevices?.getUserMedia);
}

export async function startBrowserCamera(video: HTMLVideoElement): Promise<void> {
  stream ??= await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: { facingMode: "user", width: { ideal: 1920 }, height: { ideal: 1080 } },
  });
  if (video.srcObject !== stream) video.srcObject = stream;
  await video.play().catch(() => undefined);
  if (!video.videoWidth) {
    await new Promise<void>((resolve) =>
      video.addEventListener("loadeddata", () => resolve(), { once: true }),
    );
  }
}

export function stopBrowserCamera(): void {
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
}

/** Grab the current frame as JPEG, mirrored like the selfie preview the guest sees. */
export async function snapshot(video: HTMLVideoElement, mirror = true): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx || !canvas.width) throw new Error("camera frame not ready");
  if (mirror) {
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
  }
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("camera snapshot failed"))),
      "image/jpeg",
      0.92,
    ),
  );
}
