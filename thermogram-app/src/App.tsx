import { useEffect, useRef, useState, useCallback } from "react";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore } from "./stores/imageStore";
import { useCalibrationStore } from "./stores/calibrationStore";
import { UploadPanel } from "./components/Sidebar/UploadPanel";
import { CalibrationPanel } from "./components/Sidebar/CalibrationPanel";
import { GridOverlay } from "./components/Workspace/GridOverlay";
import { TemplateSelector } from "./components/Sidebar/TemplateSelector";
import { CalibrationModal } from "./components/CalibrationModal";
import { useProcessing } from "./hooks/useProcessing";
import { useImageLoader } from "./hooks/useImageLoader";
import type { ViewMode, GetCalibrationResponse } from "./types";
import "./App.css";

function App() {
  const {
    imagePath,
    originalImage,
    matchImage,
    imageWidth,
    imageHeight,
    detectedTemplate,
    viewMode,
    setViewMode,
    processing,
    gridCalibration,
  } = useImageStore();

  const { processMatchTemplate, isProcessing } = useProcessing();
  const { loadImageFromPath } = useImageLoader();
  const { openModal: openCalibrationModal, openAlignment } = useCalibrationStore();

  // Handle opening calibration modal
  const handleOpenCalibration = () => {
    if (!detectedTemplate?.templateId || !imageWidth || !imageHeight) return;
    openCalibrationModal(detectedTemplate.templateId, imageWidth, imageHeight);
  };

  // Handle opening alignment modal (re-align existing calibration)
  const handleOpenAlignment = useCallback(async () => {
    if (!detectedTemplate?.templateId || !imageWidth || !imageHeight) return;

    try {
      // Fetch fresh calibration data from backend
      const calibResult = await invoke<GetCalibrationResponse>("get_calibration", {
        templateId: detectedTemplate.templateId,
      });

      if (calibResult.success && calibResult.exists && calibResult.derived) {
        const savedCalibrationData = {
          referenceHour: calibResult.derived.reference_hour ?? 12,
          referenceMinute: calibResult.derived.reference_minute ?? 0,
          referenceTemp: calibResult.derived.reference_temp ?? calibResult.derived.horizontal_top_temp ?? 0,
          verticalSpacing: calibResult.derived.line_spacing,
          horizontalSpacing: calibResult.derived.horizontal_spacing ?? 25,
          curvature: calibResult.derived.curve_coeff_a,
          centerY: calibResult.derived.curve_center_y,
          topPoint: calibResult.derived.top_point,
          bottomPoint: calibResult.derived.bottom_point,
        };

        openAlignment(detectedTemplate.templateId, imageWidth, imageHeight, savedCalibrationData);
      }
    } catch (err) {
      console.error("Failed to load calibration for alignment:", err);
    }
  }, [detectedTemplate?.templateId, imageWidth, imageHeight, openAlignment]);

  // Drag and drop state
  const [isDragOver, setIsDragOver] = useState(false);

  // Check if calibration is needed (for UI display)
  const canCalibrate = !!detectedTemplate?.templateId && !!originalImage && imageWidth > 0 && imageHeight > 0;
  const needsCalibration = canCalibrate && gridCalibration === null;

  // Tauri drag-drop event listener
  useEffect(() => {
    const webview = getCurrentWebviewWindow();

    const unlisten = webview.onDragDropEvent(async (event) => {
      const eventType = event.payload.type;
      if (eventType === "enter" || eventType === "over") {
        setIsDragOver(true);
      } else if (eventType === "leave") {
        setIsDragOver(false);
      } else if (eventType === "drop") {
        setIsDragOver(false);
        const paths = event.payload.paths;
        if (paths && paths.length > 0) {
          const filePath = paths[0];
          // Validate file extension
          const ext = filePath.split(".").pop()?.toLowerCase();
          const validExtensions = ["tif", "tiff", "png", "jpg", "jpeg"];
          if (ext && validExtensions.includes(ext)) {
            // loadImageFromPath handles calibration prompt internally
            await loadImageFromPath(filePath);
          }
        }
      }
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, [loadImageFromPath]);

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

  // Show grid overlay when calibration exists and viewing original
  const showGridOverlay = gridCalibration !== null && viewMode === "original";

  // Determine which image to show
  const displayImage = viewMode === "match" ? matchImage : originalImage;

  // Keyboard shortcuts for switching views (1-2)
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
          if (matchImage) setViewMode("match");
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [originalImage, matchImage, setViewMode]);

  const isViewActive = (mode: ViewMode): boolean => viewMode === mode;

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1>Thermogram Digitizer</h1>
          <p className="subtitle">
            Kandilli Observatory Historical Data Digitization
          </p>
        </div>
        <div className="header-right">
          <button
            className="btn btn-align"
            onClick={handleOpenAlignment}
            disabled={!gridCalibration}
            title={
              !gridCalibration
                ? "Calibrate first to enable alignment"
                : `Re-align grid for ${detectedTemplate?.templateId}`
            }
          >
            Align
          </button>
          <button
            className={`btn btn-calibrate ${needsCalibration ? "btn-calibrate-required" : ""}`}
            onClick={handleOpenCalibration}
            disabled={!canCalibrate}
            title={
              !canCalibrate
                ? "Load an image first"
                : needsCalibration
                  ? `⚠ Calibration required for ${detectedTemplate?.templateId} - Click to calibrate`
                  : `Recalibrate grid for ${detectedTemplate?.templateId}`
            }
          >
            {needsCalibration && <span className="calibrate-warning">⚠</span>}
            Calibrate
            {detectedTemplate?.templateId && (
              <span className="calibrate-template">({detectedTemplate.templateId})</span>
            )}
          </button>
        </div>
      </header>

      <CalibrationModal />

      <div className="main-layout">
        <aside className="sidebar">
          <div className="sidebar-scrollable">
            <UploadPanel />

            <TemplateSelector />

            <div className="panel">
              <h2>Tools</h2>
              <button
                onClick={processMatchTemplate}
                disabled={!imagePath || isProcessing}
                className="btn btn-primary"
              >
                {isProcessing ? "Processing..." : "Match 10s"}
              </button>
            </div>

            <div className="panel">
              <h2>View (1-2)</h2>
              <div className="view-buttons">
                <button
                  onClick={() => setViewMode("original")}
                  disabled={!originalImage}
                  className={`btn ${isViewActive("original") ? "btn-active" : ""}`}
                  title="Original image with grid overlay"
                >
                  1. Image {gridCalibration ? "+ Grid" : ""}
                </button>
                <button
                  onClick={() => setViewMode("match")}
                  disabled={!matchImage}
                  className={`btn ${isViewActive("match") ? "btn-active" : ""}`}
                  title="Template matching for '10' labels"
                >
                  2. Match
                </button>
              </div>
            </div>

            <CalibrationPanel />
          </div>

          <div className="sidebar-pinned">
            <div className="panel status-panel">
              <h2>Status</h2>
              <p className="status-text">{processing.message || "Ready"}</p>
            </div>
          </div>
        </aside>

        <main className={`workspace ${isDragOver ? "drag-over" : ""}`}>
          {isDragOver && (
            <div className="drop-overlay">
              <div className="drop-message">
                <span className="drop-icon">📁</span>
                <p>Drop image here</p>
              </div>
            </div>
          )}
          {displayImage ? (
            <div className="image-container" style={{ position: "relative" }}>
              <img
                ref={imageRef}
                src={`data:image/png;base64,${displayImage}`}
                alt={viewMode}
                className="thermogram-image"
                onLoad={handleImageLoad}
              />
              {showGridOverlay && imageDimensions.width > 0 && (
                <GridOverlay
                  width={imageDimensions.width}
                  height={imageDimensions.height}
                  showVertical={true}
                  showHorizontal={true}
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
