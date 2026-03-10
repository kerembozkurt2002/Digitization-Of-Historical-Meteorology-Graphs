import { useEffect, useRef, useState } from "react";
import { useImageStore, selectCurrentImage } from "./stores/imageStore";
import { UploadPanel } from "./components/Sidebar/UploadPanel";
import { CalibrationPanel } from "./components/Sidebar/CalibrationPanel";
import { GridOverlay } from "./components/Workspace/GridOverlay";
import { useProcessing } from "./hooks/useProcessing";
import type { ViewMode } from "./types";
import "./App.css";

function App() {
  const {
    imagePath,
    originalImage,
    horizontalImage,
    verticalImage,
    combinedImage,
    matchImage,
    verticalLinePositions,
    viewMode,
    setViewMode,
    processing,
  } = useImageStore();

  const currentImage = useImageStore(selectCurrentImage);
  const { processGridDetection, processMatchTemplate, isProcessing } = useProcessing();

  // Track image dimensions for canvas overlay
  const imageRef = useRef<HTMLImageElement>(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });

  // Update dimensions when image loads
  const handleImageLoad = () => {
    if (imageRef.current) {
      setImageDimensions({
        width: imageRef.current.clientWidth,
        height: imageRef.current.clientHeight,
      });
    }
  };

  // Determine if we should use client-side rendering for vertical lines
  const useClientSideVertical = verticalLinePositions.length > 0;
  const showVerticalOverlay = useClientSideVertical && (viewMode === "vertical" || viewMode === "combined");

  // For vertical/combined views, use original image as base when using client-side rendering
  const baseImage = useClientSideVertical && (viewMode === "vertical" || viewMode === "combined")
    ? (viewMode === "combined" ? horizontalImage : originalImage)
    : currentImage;

  // Keyboard shortcuts for switching views (1-4)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.key) {
        case "1":
          if (originalImage) setViewMode("original");
          break;
        case "2":
          if (horizontalImage) setViewMode("horizontal");
          break;
        case "3":
          if (verticalImage) setViewMode("vertical");
          break;
        case "4":
          if (combinedImage) setViewMode("combined");
          break;
        case "5":
          if (matchImage) setViewMode("match");
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [originalImage, horizontalImage, verticalImage, combinedImage, matchImage, setViewMode]);

  const isViewActive = (mode: ViewMode): boolean => viewMode === mode;

  return (
    <div className="app">
      <header className="header">
        <h1>Thermogram Digitizer</h1>
        <p className="subtitle">
          Kandilli Observatory Historical Data Digitization
        </p>
      </header>

      <div className="main-layout">
        <aside className="sidebar">
          <UploadPanel />

          <CalibrationPanel />

          <div className="panel">
            <h2>Process</h2>
            <button
              onClick={processGridDetection}
              disabled={!imagePath || isProcessing}
              className="btn btn-primary"
            >
              {isProcessing ? "Processing..." : "Detect Grid"}
            </button>
            <button
              onClick={processMatchTemplate}
              disabled={!imagePath || isProcessing}
              className="btn btn-primary"
              style={{ marginTop: "8px" }}
            >
              {isProcessing ? "Processing..." : "Match 10s"}
            </button>
          </div>

          <div className="panel">
            <h2>View (1-5)</h2>
            <div className="view-buttons">
              <button
                onClick={() => setViewMode("original")}
                disabled={!originalImage}
                className={`btn ${isViewActive("original") ? "btn-active" : ""}`}
                title="Original image"
              >
                1. Original
              </button>
              <button
                onClick={() => setViewMode("horizontal")}
                disabled={!horizontalImage}
                className={`btn ${isViewActive("horizontal") ? "btn-active" : ""}`}
                title="Horizontal grid lines (green)"
              >
                2. H-Lines
              </button>
              <button
                onClick={() => setViewMode("vertical")}
                disabled={!verticalImage}
                className={`btn ${isViewActive("vertical") ? "btn-active" : ""}`}
                title="Vertical grid lines (blue)"
              >
                3. V-Lines
              </button>
              <button
                onClick={() => setViewMode("combined")}
                disabled={!combinedImage}
                className={`btn ${isViewActive("combined") ? "btn-active" : ""}`}
                title="Both horizontal and vertical lines"
              >
                4. Combined
              </button>
              <button
                onClick={() => setViewMode("match")}
                disabled={!matchImage}
                className={`btn ${isViewActive("match") ? "btn-active" : ""}`}
                title="Template matching for '10' labels"
              >
                5. Match
              </button>
            </div>
          </div>

          <div className="panel status-panel">
            <h2>Status</h2>
            <p className="status-text">{processing.message || "Ready"}</p>
          </div>
        </aside>

        <main className="workspace">
          {baseImage ? (
            <div className="image-container" style={{ position: "relative" }}>
              <img
                ref={imageRef}
                src={`data:image/png;base64,${baseImage}`}
                alt={viewMode}
                className="thermogram-image"
                onLoad={handleImageLoad}
              />
              {showVerticalOverlay && imageDimensions.width > 0 && (
                <GridOverlay
                  width={imageDimensions.width}
                  height={imageDimensions.height}
                  showVertical={true}
                  showHorizontal={false}
                />
              )}
            </div>
          ) : (
            <div className="placeholder">
              <p>Select an image to begin</p>
              <p className="hint">Supported formats: TIFF, PNG, JPG</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
