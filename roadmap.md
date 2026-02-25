# Thermogram Digitization - Roadmap

## Project Overview
**Goal:** Develop a desktop application to digitize thermogram charts from Kandilli Observatory archives (1940-1990).

**Input:** 1,682 TIFF images (Daily / 4-day / Weekly formats)
**Output:** Time-series data (datetime, temperature C) - CSV/JSON

---

## Technology Stack

| Layer | Technology | Description |
|-------|------------|-------------|
| Desktop Framework | **Tauri** | Lightweight (~10MB), fast, cross-platform |
| Frontend | **React + TypeScript** | Modern UI, large ecosystem |
| Backend/Processing | **Python 3.11+** | OpenCV, NumPy, scikit-image |
| Backend Integration | **Sidecar** | Bundled with PyInstaller, called from Tauri |
| Database | **SQLite** | Single file, no setup required |
| Image Processing | **OpenCV** | Classical CV approach |
| OS Support | **macOS + Windows** | Two platforms |

---

## Repository Structure

```
/
├── src-tauri/              # Tauri Rust backend
│   ├── src/
│   │   ├── main.rs         # Entry point
│   │   ├── commands.rs     # Tauri commands (IPC)
│   │   └── sidecar.rs      # Python sidecar management
│   ├── Cargo.toml
│   └── tauri.conf.json
│
├── src/                    # React Frontend
│   ├── components/
│   │   ├── Workspace/      # Main workspace
│   │   │   ├── ImageViewer.tsx
│   │   │   ├── OverlayCanvas.tsx
│   │   │   └── EditTools.tsx
│   │   ├── Sidebar/
│   │   │   ├── UploadPanel.tsx
│   │   │   ├── FormatSelector.tsx
│   │   │   ├── ConfigPanel.tsx
│   │   │   └── ProcessingStatus.tsx
│   │   └── Export/
│   │       └── ExportDialog.tsx
│   ├── hooks/
│   ├── stores/             # Zustand state management
│   ├── types/
│   ├── App.tsx
│   └── main.tsx
│
├── backend/                # Python Processing Pipeline
│   ├── main.py             # CLI entry point (sidecar)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── preprocessor.py     # Stage 1: Normalize, denoise
│   │   ├── dewarper.py         # Stage 2: Grid detection & straightening
│   │   ├── calibrator.py       # Stage 3: Axis calibration (pixel->value)
│   │   ├── segmenter.py        # Stage 4: Curve extraction
│   │   ├── digitizer.py        # Stage 5: Curve -> datapoints
│   │   └── validator.py        # Stage 6: Confidence scoring
│   ├── models/
│   │   └── datapoint.py
│   ├── utils/
│   │   ├── image_utils.py
│   │   └── grid_utils.py
│   └── requirements.txt
│
├── configs/                # Chart format configurations
│   ├── daily.json
│   ├── four_day.json
│   └── weekly.json
│
├── database/
│   └── schema.sql          # SQLite schema
│
├── docs/                   # Wiki documentation (gitignored)
└── roadmap.md              # This file
```

---

## Processing Pipeline - 6 Stages

### Stage 1: Preprocessor
**File:** `backend/pipeline/preprocessor.py`

**Purpose:** Clean and normalize the image

**Steps:**
1. Load TIFF file
2. Convert color space (BGR -> RGB -> HSV as needed)
3. Denoise (Bilateral filter or Non-local means)
4. Contrast normalization
5. Detect and crop ROI (Region of Interest)
6. Return processed image + metadata

```python
def preprocess(image_path: str) -> ProcessedImage:
    image = cv2.imread(image_path)

    # Denoise
    denoised = cv2.bilateralFilter(image, 9, 75, 75)

    # Normalize contrast
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    normalized = cv2.merge([l, a, b])
    normalized = cv2.cvtColor(normalized, cv2.COLOR_LAB2BGR)

    # Crop ROI (chart area)
    roi = detect_chart_boundaries(normalized)
    cropped = normalized[roi.y:roi.y+roi.h, roi.x:roi.x+roi.w]

    return ProcessedImage(image=cropped, metadata=roi)
```

---

### Stage 2: Dewarper (CRITICAL)
**File:** `backend/pipeline/dewarper.py`

**Purpose:** Straighten curved grid lines

**Problem:**
```
Original (Curved Grid):        Target (Straight Grid):
    ╭──────────────────╮       ┌──────────────────┐
    │  ╱  ╱  ╱  ╱  ╱   │       │  │  │  │  │  │   │
    │ ╱  ╱  ╱  ╱  ╱    │  -->  │  │  │  │  │  │   │
    │╱  ╱  ╱  ╱  ╱     │       │  │  │  │  │  │   │
    │  ╱  ╱  ╱  ╱  ╱   │       │  │  │  │  │  │   │
    ╰──────────────────╯       └──────────────────┘
```

**Algorithm Steps:**

#### Step 2.1: Detect Grid Lines
```python
def detect_grid_lines(image):
    # 1. Edge detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    # 2. Hough Line Transform
    lines = cv2.HoughLinesP(edges, 1, np.pi/180,
                            threshold=100,
                            minLineLength=100,
                            maxLineGap=10)

    # 3. Cluster into vertical and horizontal
    vertical_lines = []
    horizontal_lines = []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.arctan2(y2-y1, x2-x1) * 180 / np.pi

        if abs(angle) < 30 or abs(angle) > 150:
            horizontal_lines.append(line)
        elif 60 < abs(angle) < 120:
            vertical_lines.append(line)

    return vertical_lines, horizontal_lines
```

#### Step 2.2: Fit Curves to Lines
```python
def fit_curves_to_lines(lines, orientation='vertical'):
    # Polynomial fit for each line group
    fitted_curves = []

    for line_group in cluster_lines(lines):
        points = extract_line_points(line_group)

        if orientation == 'vertical':
            # Use x = f(y) instead of y = f(x)
            coeffs = np.polyfit(points[:, 1], points[:, 0], deg=2)
        else:
            coeffs = np.polyfit(points[:, 0], points[:, 1], deg=2)

        fitted_curves.append(coeffs)

    return fitted_curves
```

#### Step 2.3: Find Intersection Points
```python
def find_grid_intersections(v_curves, h_curves, image_shape):
    intersections = []

    for v_curve in v_curves:
        for h_curve in h_curves:
            # Find intersection of two curves
            point = find_curve_intersection(v_curve, h_curve)
            if point is not None:
                intersections.append(point)

    return np.array(intersections)
```

#### Step 2.4: Compute Transformation
```python
def compute_dewarp_transform(src_points, grid_size):
    # Target points (straight grid)
    rows, cols = grid_size
    dst_points = []

    for i in range(rows):
        for j in range(cols):
            x = j * (image_width / (cols - 1))
            y = i * (image_height / (rows - 1))
            dst_points.append([x, y])

    dst_points = np.array(dst_points)

    # Homography or TPS
    # For simple cases use homography
    H, _ = cv2.findHomography(src_points, dst_points, cv2.RANSAC)

    # For complex curvature use Thin-Plate Spline
    # tps = ThinPlateSpline()
    # tps.fit(src_points, dst_points)

    return H
```

#### Step 2.5: Warp Image
```python
def dewarp_image(image, transform):
    h, w = image.shape[:2]

    # Forward warp
    straightened = cv2.warpPerspective(image, transform, (w, h))

    # Store inverse transform for display
    inverse_transform = np.linalg.inv(transform)

    return DewarpResult(
        straightened_image=straightened,
        forward_transform=transform,
        inverse_transform=inverse_transform
    )
```

---

### Stage 3: Calibrator
**File:** `backend/pipeline/calibrator.py`

**Purpose:** Convert pixel coordinates to real values

**Mapping:**
- `pixel_x` -> `datetime`
- `pixel_y` -> `temperature (C)`

```python
@dataclass
class ChartConfig:
    format: str  # 'daily', 'four_day', 'weekly'
    time_range_hours: int
    temp_min: float
    temp_max: float
    grid_color_hsv: dict

def calibrate(image: DewarpedImage, config: ChartConfig) -> Calibration:
    h, w = image.shape[:2]

    # X axis: pixel -> time
    def pixel_to_time(x_pixel: int) -> datetime:
        ratio = x_pixel / w
        hours = ratio * config.time_range_hours
        return base_datetime + timedelta(hours=hours)

    # Y axis: pixel -> temperature
    def pixel_to_temp(y_pixel: int) -> float:
        ratio = 1 - (y_pixel / h)  # Y axis inverted
        temp_range = config.temp_max - config.temp_min
        return config.temp_min + (ratio * temp_range)

    return Calibration(
        pixel_to_time=pixel_to_time,
        pixel_to_temp=pixel_to_temp,
        time_to_pixel=...,  # inverse
        temp_to_pixel=...   # inverse
    )
```

**Format Configurations:**

```json
// configs/daily.json
{
  "format": "daily",
  "time_range_hours": 24,
  "vertical_grid_interval_hours": 1,
  "temp_min": -10,
  "temp_max": 40,
  "horizontal_grid_interval_celsius": 5,
  "grid_colors": {
    "orange": {"h_min": 10, "h_max": 25, "s_min": 100, "v_min": 100},
    "green": {"h_min": 35, "h_max": 85, "s_min": 50, "v_min": 50}
  }
}

// configs/four_day.json
{
  "format": "four_day",
  "time_range_hours": 96,
  "vertical_grid_interval_hours": 6,
  ...
}

// configs/weekly.json
{
  "format": "weekly",
  "time_range_hours": 168,
  "vertical_grid_interval_hours": 12,
  ...
}
```

---

### Stage 4: Segmenter
**File:** `backend/pipeline/segmenter.py`

**Purpose:** Separate temperature curve from grid

**Challenges:**
- Curve is very thin (~0.1-0.5% of pixels)
- Grid lines are dominant
- Curve constantly crosses grid lines

**Algorithm:**

#### Step 4.1: Detect Grid Color
```python
def detect_grid_color(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Orange grid mask
    orange_mask = cv2.inRange(hsv,
                              np.array([10, 100, 100]),
                              np.array([25, 255, 255]))

    # Green grid mask
    green_mask = cv2.inRange(hsv,
                             np.array([35, 50, 50]),
                             np.array([85, 255, 255]))

    # Which is more dominant?
    if cv2.countNonZero(orange_mask) > cv2.countNonZero(green_mask):
        return 'orange', orange_mask
    else:
        return 'green', green_mask
```

#### Step 4.2: Remove Grid
```python
def remove_grid(image, grid_mask):
    # Dilate grid mask to cover curve intersections
    kernel = np.ones((3, 3), np.uint8)
    dilated_grid = cv2.dilate(grid_mask, kernel, iterations=2)

    # Inpaint to fill grid areas
    no_grid = cv2.inpaint(image, dilated_grid, 3, cv2.INPAINT_TELEA)

    return no_grid
```

#### Step 4.3: Extract Curve
```python
def extract_curve(image_no_grid):
    gray = cv2.cvtColor(image_no_grid, cv2.COLOR_BGR2GRAY)

    # Find dark pixels (curve is black/dark)
    _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

    # Morphological cleanup
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

    return cleaned
```

#### Step 4.4: Skeletonize
```python
from skimage.morphology import skeletonize

def skeletonize_curve(curve_mask):
    # Reduce to 1px width
    skeleton = skeletonize(curve_mask // 255)
    return (skeleton * 255).astype(np.uint8)
```

---

### Stage 5: Digitizer
**File:** `backend/pipeline/digitizer.py`

**Purpose:** Convert curve to data points

```python
def digitize(skeleton: np.ndarray,
             calibration: Calibration,
             sample_interval: int) -> List[DataPoint]:

    h, w = skeleton.shape
    datapoints = []

    # For each vertical grid line (at sample_interval pixels)
    for x in range(0, w, sample_interval):
        # Where is the curve at this x?
        column = skeleton[:, x]
        y_positions = np.where(column > 0)[0]

        if len(y_positions) == 0:
            # Gap exists, may need interpolation
            continue

        # If multiple, take median
        y = int(np.median(y_positions))

        # Pixel -> real value
        dt = calibration.pixel_to_time(x)
        temp = calibration.pixel_to_temp(y)

        datapoints.append(DataPoint(
            x_pixel=x,
            y_pixel=y,
            datetime=dt.isoformat(),
            temperature=round(temp, 1),
            confidence=calculate_confidence(column, y_positions)
        ))

    return datapoints

def calculate_confidence(column, y_positions):
    if len(y_positions) == 0:
        return 0.0
    if len(y_positions) == 1:
        return 1.0
    # Multiple y values means low confidence
    spread = np.max(y_positions) - np.min(y_positions)
    return max(0.0, 1.0 - (spread / 20))  # 20px spread = 0 confidence
```

---

### Stage 6: Validator
**File:** `backend/pipeline/validator.py`

**Purpose:** Validate results and assign confidence scores

```python
def validate(datapoints: List[DataPoint]) -> ValidationResult:
    issues = []

    for i, point in enumerate(datapoints):
        # 1. Impossible values
        if point.temperature < -40 or point.temperature > 60:
            issues.append(Issue(
                type='impossible_value',
                index=i,
                message=f'Temperature {point.temperature}C out of range'
            ))

        # 2. Sudden jumps
        if i > 0:
            prev = datapoints[i-1]
            diff = abs(point.temperature - prev.temperature)
            if diff > 10:  # More than 10C jump
                issues.append(Issue(
                    type='sudden_jump',
                    index=i,
                    message=f'Jump of {diff}C between adjacent points'
                ))

    # 3. Gaps
    # ...

    # Overall score
    total = len(datapoints)
    low_confidence = sum(1 for p in datapoints if p.confidence < 0.5)
    overall_confidence = (total - low_confidence - len(issues)) / total

    return ValidationResult(
        issues=issues,
        overall_confidence=overall_confidence,
        needs_review=overall_confidence < 0.8 or len(issues) > 0
    )
```

---

## Frontend Architecture

### State Management (Zustand)

```typescript
interface AppState {
  // Image
  currentImage: ImageData | null;
  originalImagePath: string | null;
  straightenedImage: ImageData | null;

  // Processing
  processingStatus: 'idle' | 'processing' | 'complete' | 'error';
  processingStep: ProcessingStep;
  processingError: string | null;

  // Data
  datapoints: DataPoint[];
  selectedPointIndex: number | null;
  validationResult: ValidationResult | null;

  // Edit
  editMode: 'review' | 'edit';
  editHistory: EditAction[];
  historyIndex: number;

  // Config
  chartFormat: 'daily' | 'four_day' | 'weekly';
  overlaySettings: {
    showPoints: boolean;
    showCurve: boolean;
    showGrid: boolean;
    pointSize: number;
  };

  // Actions
  uploadImage: (path: string) => void;
  setFormat: (format: string) => void;
  runProcessing: () => Promise<void>;
  selectPoint: (index: number) => void;
  movePoint: (index: number, x: number, y: number) => void;
  addPoint: (x: number, y: number) => void;
  deletePoint: (index: number) => void;
  undo: () => void;
  redo: () => void;
  exportData: (format: 'csv' | 'json') => void;
}
```

### Component Hierarchy

```
App
├── Header
│   ├── Logo
│   └── MenuBar
│
├── MainLayout
│   ├── Sidebar (left)
│   │   ├── UploadPanel
│   │   │   ├── DropZone
│   │   │   └── FileInfo
│   │   ├── FormatSelector
│   │   │   └── RadioGroup (Daily/4-day/Weekly)
│   │   ├── ConfigPanel (collapsible)
│   │   │   ├── ROISettings
│   │   │   └── GridColorOverride
│   │   ├── OverlayControls
│   │   │   ├── Toggle (Points)
│   │   │   ├── Toggle (Curve)
│   │   │   └── Toggle (Grid)
│   │   └── ProcessButton
│   │       └── StatusIndicator
│   │
│   ├── Workspace (center)
│   │   ├── ImageViewer
│   │   │   ├── ZoomControls
│   │   │   └── PanHandler
│   │   └── OverlayCanvas
│   │       ├── PointMarkers
│   │       └── CurveLine
│   │
│   └── RightPanel
│       ├── ModeSwitch (Review/Edit)
│       ├── ReviewPanel (when review mode)
│       │   ├── PointInspector
│       │   └── ValidationWarnings
│       └── EditPanel (when edit mode)
│           ├── EditToolbar
│           │   ├── SelectTool
│           │   ├── MoveTool
│           │   ├── AddTool
│           │   └── DeleteTool
│           ├── PointEditor
│           └── UndoRedo
│
└── ExportDialog (modal)
    ├── FormatSelect (CSV/JSON)
    ├── VersionSelect (Raw/Edited)
    └── DownloadButton
```

---

## Database Schema

```sql
-- Charts: Each uploaded image
CREATE TABLE charts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('daily', 'four_day', 'weekly')),
    year INTEGER,
    month TEXT,
    day INTEGER,
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'processed', 'reviewed', 'exported')),
    confidence_score REAL,
    dewarp_transform BLOB,  -- Numpy array as bytes
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Datapoints: Extracted data points
CREATE TABLE datapoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id INTEGER NOT NULL,
    x_pixel INTEGER NOT NULL,
    y_pixel INTEGER NOT NULL,
    datetime TEXT NOT NULL,
    temperature REAL NOT NULL,
    confidence REAL DEFAULT 1.0,
    is_edited BOOLEAN DEFAULT FALSE,
    is_added BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chart_id) REFERENCES charts(id) ON DELETE CASCADE
);

-- Edit history: For undo/redo
CREATE TABLE edit_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id INTEGER NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('move', 'add', 'delete')),
    point_id INTEGER,
    old_x INTEGER,
    old_y INTEGER,
    new_x INTEGER,
    new_y INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chart_id) REFERENCES charts(id) ON DELETE CASCADE,
    FOREIGN KEY (point_id) REFERENCES datapoints(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX idx_datapoints_chart ON datapoints(chart_id);
CREATE INDEX idx_edit_history_chart ON edit_history(chart_id);
```

---

## Sidecar IPC Protocol

**Python CLI Interface:**

```bash
# Process a chart
python main.py process --image /path/to/image.tif --format daily --output /path/to/result.json

# Preview grid detection (for debugging)
python main.py preview --image /path/to/image.tif --output /path/to/preview.png

# Dewarp only
python main.py dewarp --image /path/to/image.tif --output /path/to/dewarped.png

# Export data
python main.py export --chart-id 123 --format csv --output /path/to/export.csv
```

**JSON Response Format:**

```json
{
  "success": true,
  "data": {
    "chart_id": 1,
    "datapoints": [
      {
        "x_pixel": 100,
        "y_pixel": 250,
        "datetime": "1980-01-01T00:00:00",
        "temperature": 12.5,
        "confidence": 0.95
      }
    ],
    "validation": {
      "overall_confidence": 0.87,
      "needs_review": true,
      "issues": [
        {"type": "sudden_jump", "index": 45, "message": "..."}
      ]
    },
    "transform": {
      "forward": [[...], [...], [...]],
      "inverse": [[...], [...], [...]]
    }
  },
  "error": null
}
```

**Tauri Command:**

```rust
#[tauri::command]
async fn process_chart(
    image_path: String,
    format: String,
    app_handle: tauri::AppHandle
) -> Result<ProcessingResult, String> {
    let sidecar = app_handle.shell().sidecar("thermogram-backend")?;

    let output = sidecar
        .args(["process", "--image", &image_path, "--format", &format])
        .output()
        .await?;

    let result: ProcessingResult = serde_json::from_slice(&output.stdout)?;
    Ok(result)
}
```

---

## Implementation Milestones

### Milestone 1: Foundation (Week 1)
- [ ] Tauri + React project initialization
- [ ] Python backend folder structure
- [ ] Basic sidecar test (hello world)
- [ ] SQLite database setup

**Deliverable:** App opens, Python sidecar can be called

### Milestone 2: Core Pipeline (Week 2-3)
- [ ] Preprocessor implementation
- [ ] Dewarper implementation (most critical)
- [ ] Basic tests with sample images

**Deliverable:** Image can be loaded and dewarped

### Milestone 3: Full Pipeline (Week 4)
- [ ] Calibrator implementation
- [ ] Segmenter implementation
- [ ] Digitizer implementation
- [ ] Validator implementation

**Deliverable:** Data points extracted from image

### Milestone 4: Basic UI (Week 5)
- [ ] Image upload component
- [ ] Image viewer with zoom/pan
- [ ] Processing trigger
- [ ] Overlay visualization

**Deliverable:** User can upload image and see results

### Milestone 5: Edit & Review (Week 6)
- [ ] Point selection
- [ ] Edit mode (move/add/delete)
- [ ] Undo/redo
- [ ] Save to database

**Deliverable:** User can edit points

### Milestone 6: Export & Polish (Week 7)
- [ ] CSV/JSON export
- [ ] Settings panel
- [ ] Error handling improvements
- [ ] UI polish

**Deliverable:** Fully working application

### Milestone 7: Distribution (Week 8)
- [ ] macOS build & test
- [ ] Windows build & test
- [ ] Installer creation
- [ ] Documentation

**Deliverable:** Ready for distribution

---

## Testing Strategy

### Unit Tests
```
backend/tests/
├── test_preprocessor.py
├── test_dewarper.py
├── test_calibrator.py
├── test_segmenter.py
├── test_digitizer.py
└── test_validator.py
```

### Integration Tests
- Full pipeline on sample images
- Database CRUD operations
- Sidecar communication

### Manual Test Cases
1. Daily chart (clean scan) -> Expected: High confidence, no edits needed
2. Daily chart (with stamp) -> Expected: Low confidence in stamped region
3. 4-day chart -> Expected: Correct time mapping (96 hours)
4. Weekly chart -> Expected: Correct time mapping (168 hours)
5. Skewed scan -> Expected: Dewarp corrects alignment
6. Faded curve -> Expected: Partial extraction, flags for review

### Test Images
```
Test Set 1 (Daily):
  /TERMOGRAM-1_ORNEK_DATA/1980/GUNLUK/OCAK/TERMOGRAM_1/1980_OCAK-01.tif

Test Set 2 (4-day):
  /TERMOGRAM-1_ORNEK_DATA/1940/4 GUNLUK/.../

Test Set 3 (Weekly):
  /TERMOGRAM-1_ORNEK_DATA/1940/HAFTALIK/.../
```

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Dewarping accuracy low | High | High | Iterative development, switch to TPS, manual fallback |
| Thin curve not detected | Medium | High | Multi-threshold, morphological tuning |
| Grid-curve intersection | High | Medium | Inpainting, gap filling algorithm |
| Cross-platform build issues | Medium | Medium | Early CI/CD setup, platform-specific testing |
| Large image memory | Low | Medium | Lazy loading, downscaled preview |

---

## Decisions Log

| Decision | Choice | Reason |
|----------|--------|--------|
| Desktop framework | Tauri | Lightweight, fast, modern |
| Frontend | React + TypeScript | Large ecosystem, team experience |
| Backend | Python sidecar | OpenCV/NumPy ecosystem, rapid development |
| Database | SQLite | Single file, no setup required |
| CV approach | Classical CV | Simple for start, can add ML later |
| Dewarping | Homography + TPS fallback | Sufficient for most cases |
| Sampling | 1 point per grid line | User preference |
| Dual curves | Extract one | MVP scope |
| Grid colors | Auto detect | Reduce user burden |

---

## Next Steps

1. User approves plan
2. Start with Milestone 1
3. Demo and feedback after each milestone
4. Iterative development continues
