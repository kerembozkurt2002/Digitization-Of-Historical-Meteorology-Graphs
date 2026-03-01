/**
 * ImageViewer Component - Displays the thermogram image with zoom/pan controls.
 */

import { useCallback, useRef, useEffect, useState } from "react";
import { useImageStore, selectCurrentImage } from "../../stores/imageStore";

interface ImageViewerProps {
  className?: string;
}

export function ImageViewer({ className = "" }: ImageViewerProps) {
  const { viewMode, zoom, setZoom, resetZoom } = useImageStore();
  const currentImage = useImageStore(selectCurrentImage);

  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Handle wheel zoom
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.max(0.1, Math.min(10, zoom.scale * delta));
      setZoom({ scale: newScale });
    },
    [zoom.scale, setZoom]
  );

  // Set up wheel event listener
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.addEventListener("wheel", handleWheel, { passive: false });
      return () => container.removeEventListener("wheel", handleWheel);
    }
  }, [handleWheel]);

  // Handle mouse down for panning
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button === 0) {
        setIsDragging(true);
        setDragStart({ x: e.clientX - zoom.offsetX, y: e.clientY - zoom.offsetY });
      }
    },
    [zoom.offsetX, zoom.offsetY]
  );

  // Handle mouse move for panning
  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isDragging) {
        setZoom({
          offsetX: e.clientX - dragStart.x,
          offsetY: e.clientY - dragStart.y,
        });
      }
    },
    [isDragging, dragStart, setZoom]
  );

  // Handle mouse up
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Handle double-click to reset zoom
  const handleDoubleClick = useCallback(() => {
    resetZoom();
  }, [resetZoom]);

  // Keyboard shortcuts for zoom
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key) {
        case "+":
        case "=":
          setZoom({ scale: Math.min(10, zoom.scale * 1.2) });
          break;
        case "-":
          setZoom({ scale: Math.max(0.1, zoom.scale / 1.2) });
          break;
        case "0":
          resetZoom();
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [zoom.scale, setZoom, resetZoom]);

  if (!currentImage) {
    return (
      <div className={`image-viewer-placeholder ${className}`}>
        <p>No image to display</p>
        <p className="hint">Select and process an image to view results</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`image-viewer ${className}`}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
      style={{ cursor: isDragging ? "grabbing" : "grab" }}
    >
      <div
        className="image-container"
        style={{
          transform: `translate(${zoom.offsetX}px, ${zoom.offsetY}px) scale(${zoom.scale})`,
          transformOrigin: "center center",
        }}
      >
        <img
          src={`data:image/png;base64,${currentImage}`}
          alt={viewMode}
          className="thermogram-image"
          draggable={false}
        />
      </div>
      <div className="zoom-indicator">
        {Math.round(zoom.scale * 100)}%
      </div>
    </div>
  );
}

export default ImageViewer;
