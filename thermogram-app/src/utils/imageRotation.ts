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

      // Clear with white background (or transparent)
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Move to center point, rotate, then draw image offset back
      ctx.translate(centerX, centerY);
      ctx.rotate(-angleRadians); // Negative because we want to correct the skew
      ctx.translate(-centerX, -centerY);

      // Draw the image
      ctx.drawImage(img, 0, 0);

      // Get rotated image as base64
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
