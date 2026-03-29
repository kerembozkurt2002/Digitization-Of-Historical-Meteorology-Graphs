/**
 * Map between natural image pixel coordinates and the displayed <img> box
 * when CSS object-fit: contain is used (uniform scale + letterboxing).
 */

export interface ContainedImageLayout {
  scale: number;
  offsetX: number;
  offsetY: number;
  drawnW: number;
  drawnH: number;
}

export function getContainedImageLayout(
  boxWidth: number,
  boxHeight: number,
  naturalWidth: number,
  naturalHeight: number
): ContainedImageLayout {
  if (naturalWidth <= 0 || naturalHeight <= 0 || boxWidth <= 0 || boxHeight <= 0) {
    return { scale: 1, offsetX: 0, offsetY: 0, drawnW: boxWidth, drawnH: boxHeight };
  }
  const scale = Math.min(boxWidth / naturalWidth, boxHeight / naturalHeight);
  const drawnW = naturalWidth * scale;
  const drawnH = naturalHeight * scale;
  const offsetX = (boxWidth - drawnW) / 2;
  const offsetY = (boxHeight - drawnH) / 2;
  return { scale, offsetX, offsetY, drawnW, drawnH };
}

export function naturalToCanvas(
  nx: number,
  ny: number,
  layout: ContainedImageLayout
): { sx: number; sy: number } {
  return {
    sx: layout.offsetX + nx * layout.scale,
    sy: layout.offsetY + ny * layout.scale,
  };
}

export function canvasToNatural(
  sx: number,
  sy: number,
  layout: ContainedImageLayout
): { nx: number; ny: number } {
  return {
    nx: (sx - layout.offsetX) / layout.scale,
    ny: (sy - layout.offsetY) / layout.scale,
  };
}
