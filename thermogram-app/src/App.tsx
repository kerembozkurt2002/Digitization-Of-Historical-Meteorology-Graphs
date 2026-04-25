import { useCallback, useEffect, useRef, useState } from "react";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore } from "./stores/imageStore";
import { useCalibrationStore } from "./stores/calibrationStore";
import { useCurveStore } from "./stores/curveStore";
import { UploadPanel } from "./components/Sidebar/UploadPanel";
import { GridOverlay } from "./components/Workspace/GridOverlay";
import { CurveOverlay } from "./components/Workspace/CurveOverlay";
import { TemplateSelector } from "./components/Sidebar/TemplateSelector";
import { CalibrationModal } from "./components/CalibrationModal";
import { ExportModal } from "./components/ExportModal";
import { useImageLoader } from "./hooks/useImageLoader";
import type { ViewMode, GetCalibrationResponse } from "./types";
import "./App.css";

function App() {
  const {
    imagePath,
    originalImage,
    imageWidth,
    imageHeight,
    detectedTemplate,
    viewMode,
    setViewMode,
    processing,
    gridCalibration,
  } = useImageStore();

  const { loadImageFromPath } = useImageLoader();
  const { openModal: openCalibrationModal, openAlignment } = useCalibrationStore();
  const {
    points: curvePoints,
    isExtracting,
    showCurve,
    error: curveError,
    extractCurve,
    setShowCurve,
    resetEdits: resetCurveEdits,
    undo: undoCurve,
    redo: redoCurve,
    canUndo: canUndoCurve,
    canRedo: canRedoCurve,
    deleteSelectedPoints,
    isMarkingStartingPoints,
    startingPoints,
    setMarkingStartingPoints,
    removeStartingPoint,
    clearStartingPoints,
    xMin: curveXMin,
    xMax: curveXMax,
    yHint: curveYHint,
    yHintEnd: curveYHintEnd,
    isDrawing,
    drawingStrokes,
    activeStrokeId,
    setDrawingMode,
    startNewStroke,
    removeStroke,
    clearDrawing,
    getTotalDrawingPoints,
    isRefineSelecting,
    refineXMin,
    refineXMax,
    refineYMin,
    refineYMax,
    setRefineSelecting,
    clearRefineArea,
    refineInArea,
    isRefining,
    snapDrawingAndMerge,
  } = useCurveStore();

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

  // Export modal state
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Global notification state
  const [notification, setNotification] = useState<string | null>(null);

  // Clear notification after 3 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  // Track if calibration file exists for current template
  const [hasCalibrationFile, setHasCalibrationFile] = useState(false);

  // Check calibration file existence when template changes
  useEffect(() => {
    if (!detectedTemplate?.templateId) {
      setHasCalibrationFile(false);
      return;
    }

    const checkCalibration = async () => {
      try {
        const result = await invoke<GetCalibrationResponse>("get_calibration", {
          templateId: detectedTemplate.templateId,
        });
        setHasCalibrationFile(result.success && result.exists === true);
      } catch {
        setHasCalibrationFile(false);
      }
    };

    checkCalibration();
  }, [detectedTemplate?.templateId]);

  // Check if calibration is needed (for UI display)
  const canCalibrate = !!detectedTemplate?.templateId && !!originalImage && imageWidth > 0 && imageHeight > 0;
  const canAlign = canCalibrate && hasCalibrationFile;
  const needsCalibration = canCalibrate && !hasCalibrationFile;

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

  // Workspace zoom
  const [zoom, setZoom] = useState(1.0);
  const workspaceRef = useRef<HTMLElement>(null);

  // Reset zoom on image change
  useEffect(() => {
    setZoom(1.0);
  }, [originalImage]);

  // Track image dimensions for canvas overlay
  const imageRef = useRef<HTMLImageElement>(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });

  // Update dimensions when image loads - use natural dimensions for canvas overlay
  const handleImageLoad = () => {
    if (imageRef.current) {
      setImageDimensions({
        width: imageRef.current.naturalWidth,
        height: imageRef.current.naturalHeight,
      });
    }
  };

  useEffect(() => {
    const img = imageRef.current;
    if (!img || !originalImage) return;
    // Set natural dimensions once the image is available
    // Natural dimensions don't change on resize, only on image load
    if (img.naturalWidth > 0 && img.naturalHeight > 0) {
      setImageDimensions({
        width: img.naturalWidth,
        height: img.naturalHeight,
      });
    }
  }, [originalImage]);

  // Ctrl+scroll to zoom workspace (non-passive to allow preventDefault)
  useEffect(() => {
    const el = workspaceRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.15 : 0.15;
        setZoom((z) => Math.max(0.25, Math.min(5.0, z + delta)));
      }
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, []);

  const zoomIn = useCallback(() => setZoom((z) => Math.min(5.0, z + 0.25)), []);
  const zoomOut = useCallback(() => setZoom((z) => Math.max(0.25, z - 0.25)), []);
  const zoomReset = useCallback(() => setZoom(1.0), []);

  // Get curve bounds: prefer manual bounds from store, fall back to grid calibration
  const getCurveBounds = useCallback(() => {
    if (curveXMin !== null && curveXMax !== null) {
      return { xMin: curveXMin, xMax: curveXMax, yHint: curveYHint ?? undefined, yHintEnd: curveYHintEnd ?? undefined };
    }
    if (gridCalibration?.linePositions && gridCalibration.linePositions.length >= 2) {
      const positions = gridCalibration.linePositions;
      return { xMin: Math.min(...positions), xMax: Math.max(...positions), yHint: undefined, yHintEnd: undefined };
    }
    return { xMin: undefined, xMax: undefined, yHint: undefined, yHintEnd: undefined };
  }, [curveXMin, curveXMax, curveYHint, curveYHintEnd, gridCalibration]);

  // Handle extracting the curve with starting points
  const handleExtractCurve = useCallback(async () => {
    if (!imagePath || !detectedTemplate?.templateId) return;
    if (startingPoints.length > 0) {
      // Use starting points for multi-segment extraction
      await extractCurve(imagePath, detectedTemplate.templateId, 5, undefined, undefined, undefined, undefined, imageWidth || undefined);
    } else {
      const { xMin, xMax, yHint, yHintEnd } = getCurveBounds();
      await extractCurve(imagePath, detectedTemplate.templateId, 5, xMin, xMax, yHint, yHintEnd);
    }
  }, [imagePath, detectedTemplate?.templateId, extractCurve, getCurveBounds, startingPoints, imageWidth]);

  // Auto-extract curve when switching to curve view if not already extracted
  const handleCurveView = useCallback(() => {
    setViewMode("curve");
    if (curvePoints.length === 0 && !isExtracting && imagePath && detectedTemplate?.templateId) {
      if (startingPoints.length > 0) {
        extractCurve(imagePath, detectedTemplate.templateId, 5, undefined, undefined, undefined, undefined, imageWidth || undefined);
      } else {
        const { xMin, xMax, yHint, yHintEnd } = getCurveBounds();
        extractCurve(imagePath, detectedTemplate.templateId, 5, xMin, xMax, yHint, yHintEnd);
      }
    }
  }, [setViewMode, curvePoints.length, isExtracting, imagePath, detectedTemplate?.templateId, extractCurve, getCurveBounds, startingPoints, imageWidth]);

  // Auto-extract when starting points change (add/remove/update)
  const prevStartingPointsRef = useRef<string>("");
  useEffect(() => {
    // Serialize starting points including endX/endY to detect all changes
    const currentKey = JSON.stringify(startingPoints.map(sp => ({
      x: sp.x,
      y: sp.y,
      endX: sp.endX,
      endY: sp.endY
    })));

    // Only re-extract if starting points actually changed
    // And we have at least one complete segment (with end point)
    const hasCompleteSegment = startingPoints.some(sp => sp.endX !== undefined && sp.endY !== undefined);

    if (currentKey !== prevStartingPointsRef.current && hasCompleteSegment) {
      if (imagePath && detectedTemplate?.templateId && viewMode === "curve") {
        extractCurve(imagePath, detectedTemplate.templateId, 5, undefined, undefined, undefined, undefined, imageWidth || undefined);
      }
    }
    prevStartingPointsRef.current = currentKey;
  }, [startingPoints, imagePath, detectedTemplate?.templateId, extractCurve, imageWidth, viewMode]);

  // Handle opening the export modal
  const handleExport = useCallback(() => {
    if (!gridCalibration || curvePoints.length === 0 || !detectedTemplate?.templateId) return;
    setIsExportModalOpen(true);
  }, [gridCalibration, curvePoints.length, detectedTemplate?.templateId]);

  // Show grid overlay when calibration exists and viewing grid or curve
  const showGridOverlay = gridCalibration !== null && (viewMode === "original" || viewMode === "curve");
  const hasDrawingContent = drawingStrokes.some((s) => s.points.length > 0);
  const showCurveOverlay = viewMode === "curve" && (isDrawing || hasDrawingContent || isRefineSelecting || refineXMin !== null || (showCurve && curvePoints.length > 0) || isMarkingStartingPoints || startingPoints.length > 0);

  // Keyboard shortcuts for switching views (0-2), curve undo/redo, and delete points
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      const mod = e.ctrlKey || e.metaKey;

      if (mod) {
        switch (e.key) {
          case "=":
          case "+":
            e.preventDefault();
            setZoom((z) => Math.min(5.0, z + 0.25));
            return;
          case "-":
            e.preventDefault();
            setZoom((z) => Math.max(0.25, z - 0.25));
            return;
          case "0":
            e.preventDefault();
            setZoom(1.0);
            return;
          case "z":
            if (viewMode === "curve") {
              e.preventDefault();
              if (e.shiftKey) redoCurve();
              else undoCurve();
            }
            return;
        }
      }

      // Delete key to remove selected curve points
      if ((e.key === "Delete" || e.key === "Backspace") && viewMode === "curve") {
        e.preventDefault();
        deleteSelectedPoints();
        return;
      }

      switch (e.key) {
        case "0":
          if (originalImage) setViewMode("image");
          break;
        case "1":
          if (originalImage) setViewMode("original");
          break;
        case "2":
          if (originalImage) handleCurveView();
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [originalImage, setViewMode, handleCurveView, viewMode, undoCurve, redoCurve, deleteSelectedPoints]);

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
            disabled={!canAlign}
            title={
              !canAlign
                ? "No calibration file for this template"
                : `Align grid for ${detectedTemplate?.templateId}`
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

      {/* Global notification toast */}
      {notification && (
        <div className="global-notification">
          <span className="notification-icon">&#10003;</span>
          {notification}
        </div>
      )}

      <CalibrationModal />
      {/* CurveBoundsModal removed - using starting points click mode */}
      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        onExportSuccess={() => setNotification("Exported CSV")}
      />

      <div className="main-layout">
        <aside className="sidebar">
          <div className="sidebar-scrollable">
            <UploadPanel />

            <TemplateSelector />

            <div className="panel">
              <h2>View (0-2)</h2>
              <div className="view-buttons view-buttons-3">
                <button
                  onClick={() => setViewMode("image")}
                  disabled={!originalImage}
                  className={`btn ${isViewActive("image") ? "btn-active" : ""}`}
                  title="Rotated image only"
                >
                  0. Image
                </button>
                <button
                  onClick={() => setViewMode("original")}
                  disabled={!originalImage}
                  className={`btn ${isViewActive("original") ? "btn-active" : ""}`}
                  title="Image with grid overlay"
                >
                  1. Grid
                </button>
                <button
                  onClick={handleCurveView}
                  disabled={!originalImage}
                  className={`btn ${isViewActive("curve") ? "btn-active" : ""}`}
                  title="Extract and edit temperature curve"
                >
                  2. Curve
                </button>
              </div>
            </div>

            {viewMode === "curve" && (
              <div className="panel">
                <h2>Curve</h2>

                {/* Starting Points section */}
                <div className="bounds-section">
                  <button
                    className={`btn ${isMarkingStartingPoints ? "btn-active" : "btn-secondary"}`}
                    onClick={() => setMarkingStartingPoints(!isMarkingStartingPoints)}
                    disabled={!originalImage}
                    title={isMarkingStartingPoints ? "Stop marking starting points" : "Click on image to mark curve starting points"}
                  >
                    {isMarkingStartingPoints ? "Done Marking" : "Set Starting Points"}
                  </button>
                  {isMarkingStartingPoints && (
                    <p className="bounds-hint" style={{ color: "#4ade80" }}>
                      Click on the image to mark where each curve segment starts
                    </p>
                  )}
                  {startingPoints.length > 0 ? (
                    <div className="bounds-info">
                      {startingPoints.map((pt, i) => (
                        <div key={pt.id} className="bounds-segment-row">
                          <span className="bounds-label">
                            Point {i + 1}: ({Math.round(pt.x)}, {Math.round(pt.y)})
                          </span>
                          <button
                            className="btn btn-secondary btn-small"
                            onClick={() => removeStartingPoint(pt.id)}
                            title={`Remove point ${i + 1}`}
                          >
                            &times;
                          </button>
                        </div>
                      ))}
                      <button
                        className="btn btn-secondary btn-small"
                        onClick={clearStartingPoints}
                        title="Clear all starting points"
                      >
                        Clear All
                      </button>
                    </div>
                  ) : (
                    !isMarkingStartingPoints && (
                      <p className="bounds-hint">
                        No starting points — extracting full curve
                      </p>
                    )
                  )}
                </div>

                {/* Manual drawing section */}
                <div className="drawing-section">
                  <h3>Manual Drawing</h3>
                  <div className="curve-controls">
                    <button
                      className={`btn ${isDrawing ? "btn-active" : "btn-secondary"}`}
                      onClick={async () => {
                        if (isDrawing) {
                          // Stop drawing: snap to curve and merge with existing points
                          if (imagePath && detectedTemplate?.templateId && drawingStrokes.some(s => s.points.length > 0)) {
                            await snapDrawingAndMerge(imagePath, detectedTemplate.templateId);
                          } else {
                            // No drawing or no template, just exit
                            setDrawingMode(false);
                          }
                        } else {
                          // Start drawing
                          setDrawingMode(true);
                        }
                      }}
                      disabled={!originalImage}
                      title={isDrawing ? "Snap drawing to curve and merge" : "Enter freehand drawing mode"}
                    >
                      {isDrawing ? "Apply Drawing" : "Draw Curve"}
                    </button>
                    {isDrawing && drawingStrokes.length > 0 && (
                      <button
                        className="btn btn-secondary"
                        onClick={startNewStroke}
                        title="Add another curve stroke"
                      >
                        + Add Curve
                      </button>
                    )}
                  </div>

                  {/* Stroke list */}
                  {drawingStrokes.length > 0 && (
                    <div className="stroke-list">
                      {drawingStrokes.map((stroke) => (
                        <div
                          key={stroke.id}
                          className={`stroke-item ${stroke.id === activeStrokeId ? "stroke-active" : ""}`}
                        >
                          <span className="stroke-label">{stroke.label}</span>
                          <span className="stroke-pts">{stroke.points.length} pts</span>
                          <button
                            className="stroke-remove-btn"
                            onClick={() => removeStroke(stroke.id)}
                            title={`Remove ${stroke.label}`}
                          >
                            &times;
                          </button>
                        </div>
                      ))}
                      <p className="curve-info">{getTotalDrawingPoints()} total points</p>
                    </div>
                  )}

                  <div className="curve-controls">
                    <button
                      className="btn btn-secondary"
                      onClick={clearDrawing}
                      disabled={drawingStrokes.length === 0}
                      title="Clear all drawn strokes"
                    >
                      Clear All
                    </button>
                  </div>
                </div>

                {isExtracting && <p className="curve-info">Extracting...</p>}
                {curvePoints.length > 0 && (
                  <>
                    <p className="curve-info">{curvePoints.length} points</p>
                    <div className="curve-controls">
                      <button
                        onClick={undoCurve}
                        disabled={!canUndoCurve()}
                        className="btn btn-secondary"
                        title="Undo (Ctrl+Z)"
                      >
                        Undo
                      </button>
                      <button
                        onClick={redoCurve}
                        disabled={!canRedoCurve()}
                        className="btn btn-secondary"
                        title="Redo (Ctrl+Shift+Z)"
                      >
                        Redo
                      </button>
                    </div>
                    <div className="curve-controls">
                      <button
                        onClick={resetCurveEdits}
                        className="btn btn-secondary"
                        title="Reset all edits to original extraction"
                      >
                        Reset Edits
                      </button>
                      <button
                        onClick={handleExtractCurve}
                        disabled={isExtracting}
                        className="btn btn-secondary"
                        title="Re-extract curve from image"
                      >
                        Re-extract
                      </button>
                    </div>
                    {/* Refine Area */}
                    <div className="refine-section">
                      <button
                        className={`btn ${isRefineSelecting ? "btn-active" : "btn-secondary"}`}
                        onClick={() => {
                          if (isRefineSelecting) {
                            setRefineSelecting(false);
                          } else {
                            clearRefineArea();
                            setRefineSelecting(true);
                          }
                        }}
                        disabled={isRefining}
                        title="Select an area on the image to re-extract the curve only within that region"
                      >
                        {isRefineSelecting ? "Cancel Selection" : "Select Area to Refine"}
                      </button>
                      {refineXMin !== null && refineXMax !== null && refineYMin !== null && refineYMax !== null && (
                        <div className="refine-info">
                          <span className="refine-range">
                            X: {Math.round(refineXMin)}–{Math.round(refineXMax)}px,
                            Y: {Math.round(refineYMin)}–{Math.round(refineYMax)}px
                          </span>
                          <p className="refine-hint">
                            Optionally draw the correct path in the area, then click Refine.
                          </p>
                          <div className="curve-controls">
                            <button
                              className={`btn ${isDrawing ? "btn-active" : "btn-secondary"} btn-small`}
                              onClick={() => setDrawingMode(!isDrawing)}
                              title={isDrawing ? "Stop drawing" : "Draw the correct curve path in the refine area"}
                            >
                              {isDrawing ? "Stop Draw" : "Draw"}
                            </button>
                            <button
                              className="btn btn-primary"
                              onClick={async () => {
                                if (!imagePath || !detectedTemplate?.templateId) return;
                                const ok = await refineInArea(imagePath, detectedTemplate.templateId);
                                if (ok) {
                                  setNotification("Area refined successfully");
                                } else {
                                  const err = useCurveStore.getState().error;
                                  setNotification(`Refine failed: ${err || "unknown error"}`);
                                }
                              }}
                              disabled={isRefining || !imagePath || !detectedTemplate?.templateId}
                              title="Re-extract the curve only within the selected area"
                            >
                              {isRefining ? "Refining..." : "Refine This Area"}
                            </button>
                            <button
                              className="btn btn-secondary btn-small"
                              onClick={clearRefineArea}
                              title="Clear the selected refine area"
                            >
                              Clear
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    <label className="curve-toggle">
                      <input
                        type="checkbox"
                        checked={showCurve}
                        onChange={(e) => setShowCurve(e.target.checked)}
                      />
                      Show Curve
                    </label>
                    <button
                      onClick={handleExport}
                      disabled={!gridCalibration}
                      className="btn btn-primary"
                      title="Export curve data to CSV"
                    >
                      Export CSV
                    </button>
                  </>
                )}
                {curveError && <p className="curve-error">{curveError}</p>}
              </div>
            )}
          </div>

          <div className="sidebar-pinned">
            <div className="panel status-panel">
              <h2>Status</h2>
              <p className="status-text">{processing.message || "Ready"}</p>
            </div>
          </div>
        </aside>

        <main
          ref={workspaceRef}
          className={`workspace ${isDragOver ? "drag-over" : ""} ${zoom > 1 ? "workspace-zoomed" : ""}`}
        >
          {isDragOver && (
            <div className="drop-overlay">
              <div className="drop-message">
                <span className="drop-icon">📁</span>
                <p>Drop image here</p>
              </div>
            </div>
          )}
          {originalImage ? (
            <>
              <div
                className="zoom-sizer"
                style={{
                  width: imageDimensions.width * zoom,
                  height: imageDimensions.height * zoom,
                }}
              >
                <div
                  className="image-container"
                  style={{
                    transform: `scale(${zoom})`,
                    transformOrigin: "0 0",
                  }}
                >
                  <img
                    ref={imageRef}
                    src={`data:image/png;base64,${originalImage}`}
                    alt={viewMode}
                    className="thermogram-image"
                    style={{
                      width: imageDimensions.width || 'auto',
                      height: imageDimensions.height || 'auto',
                      maxWidth: 'none',
                      maxHeight: 'none',
                    }}
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
                  {showCurveOverlay && imageDimensions.width > 0 && (
                    <CurveOverlay
                      width={imageDimensions.width}
                      height={imageDimensions.height}
                    />
                  )}
                </div>
              </div>

              <div className="workspace-zoom-controls">
                <button className="zoom-btn" onClick={zoomOut} disabled={zoom <= 0.25} title="Zoom out">
                  &minus;
                </button>
                <button className="zoom-level-btn" onClick={zoomReset} title="Reset zoom">
                  {Math.round(zoom * 100)}%
                </button>
                <button className="zoom-btn" onClick={zoomIn} disabled={zoom >= 5.0} title="Zoom in">
                  +
                </button>
              </div>
            </>
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
