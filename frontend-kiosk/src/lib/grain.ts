/**
 * Film grain tile, drawn once and reused: the grain layer only moves this tile around in steps
 * (cheap), instead of generating new noise every frame.
 */
let tile = "";

export function grainTile(size = 256): string {
  if (tile) return tile;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  const image = ctx.createImageData(size, size);
  for (let i = 0; i < image.data.length; i += 4) {
    const value = Math.random() < 0.5 ? 0 : 255;
    image.data[i] = value;
    image.data[i + 1] = value;
    image.data[i + 2] = value;
    image.data[i + 3] = Math.random() * 160;
  }
  ctx.putImageData(image, 0, 0);
  tile = canvas.toDataURL("image/png");
  return tile;
}
