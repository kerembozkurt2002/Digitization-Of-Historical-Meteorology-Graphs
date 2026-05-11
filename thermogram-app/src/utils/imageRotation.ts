/**
 * Image Rotation Utility
 *
 * Rotates an image around a specified center point.
 * Used to correct skewed scans before grid calibration.
 */

export interface RotationResult {
  /** Rotated image as base64 (without data:image prefix) */
  rotatedImage: string;
  /** New width after rotation */
  newWidth: number;
  /** New height after rotation */
  newHeight: number;
  /** Transform function: original coords -> rotated coords */
  transformPoint: (x: number, y: number) => { x: number; y: number };
}

/**
 * Rotate an image around a center point.
 *
 * @param base64Image - Base64 encoded image (without data:image prefix)
 * @param angleRadians - Rotation angle in radians (positive = counter-clockwise)
 * @param centerX - X coordinate of rotation center
 * @param centerY - Y coordinate of rotation center
 * @returns Promise with rotated image and metadata
 */
export async function rotateImage(
  base64Image: string,
  angleRadians: number,
  centerX: number,
  centerY: number
): Promise<RotationResult> {
  return new Promise((resolve, reject) => {
    const img = new Image();

    img.onload = () => {
      const origWidth = img.width;
      const origHeight = img.height;

      // For small rotations, keep original dimensions
      // This avoids black borders and maintains coordinate system
      const canvas = document.createElement("canvas");
      canvas.width = origWidth;
      canvas.height = origHeight;

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("Could not get canvas context"));
        return;
      }

      ctx.translate(centerX, centerY);
      ctx.rotate(-angleRadians); // Negative because we want to correct the skew
      ctx.translate(-centerX, -centerY);

      ctx.drawImage(img, 0, 0);

      // PNG preserves the alpha channel so the wedges stay transparent.
      const dataUrl = canvas.toDataURL("image/png");
      const rotatedBase64 = dataUrl.replace(/^data:image\/png;base64,/, "");

      // Create transform function for converting coordinates
      const cos = Math.cos(-angleRadians);
      const sin = Math.sin(-angleRadians);

      const transformPoint = (x: number, y: number) => {
        // Translate to center, rotate, translate back
        const dx = x - centerX;
        const dy = y - centerY;
        return {
          x: centerX + dx * cos - dy * sin,
          y: centerY + dx * sin + dy * cos,
        };
      };

      resolve({
        rotatedImage: rotatedBase64,
        newWidth: origWidth,
        newHeight: origHeight,
        transformPoint,
      });
    };

    img.onerror = () => {
      reject(new Error("Failed to load image"));
    };

    img.src = `data:image/png;base64,${base64Image}`;
  });
}

/**
 * Calculate the inverse transform (rotated coords -> original coords)
 */
export function createInverseTransform(
  angleRadians: number,
  centerX: number,
  centerY: number
): (x: number, y: number) => { x: number; y: number } {
  const cos = Math.cos(angleRadians); // Note: positive angle (inverse)
  const sin = Math.sin(angleRadians);

  return (x: number, y: number) => {
    const dx = x - centerX;
    const dy = y - centerY;
    return {
      x: centerX + dx * cos - dy * sin,
      y: centerY + dx * sin + dy * cos,
    };
  };
}
