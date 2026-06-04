# Thermogram Digitization

A desktop application that converts scanned historical thermogram charts from the
**Kandilli Observatory** archive into machine-readable temperature time series.

The Kandilli archive holds roughly **1,682 TIFF scans** of paper thermograms
covering **1940–1990** across three chart formats (Daily, 4-day, Weekly) and nine
visually distinct templates. This project turns each scan into a clean
`(datetime, temperature °C)` CSV using a classical computer-vision pipeline plus
a focused human-in-the-loop editing UI.

The application is the CMPE 492 senior project of Ahmet Selçuk Ersoy and Kerem
Bozkurt, advised by H. Birkan Yılmaz.

---

## Architecture

```
┌─────────────────┐    invoke    ┌──────────────────┐   spawn   ┌──────────────────┐
│  React frontend │ ───────────► │  Rust (Tauri)    │ ────────► │  Python backend  │
│   (TypeScript)  │ ◄─────────── │  host process    │ ◄──────── │   (CLI sidecar)  │
└─────────────────┘   IPC JSON   └──────────────────┘   stdout  └──────────────────┘
        ▲                                                                │
        │                                                                ▼
        │                                                       calibrations/*.json
        └───── direct write ────────────────────────────────►   CSVs (next to image)
```

- **Frontend** (`thermogram-app/src/`): React 19 + TypeScript + Vite. Four Zustand
  stores (`imageStore`, `calibrationStore`, `curveStore`, `dataStore`) hold
  per-session state. Components are organized under `Workspace/`, `Sidebar/`,
  `CalibrationModal/`, and `ExportModal/`.
- **Host** (`thermogram-app/src-tauri/`): Rust + Tauri 2. Exposes eleven IPC
  commands and owns a temp-file tracker that sweeps rotated PNGs on new-image
  load and on app exit.
- **Backend** (`thermogram-app/backend/`): Python 3.11+ with OpenCV 4 and NumPy.
  Single CLI entry point (`main.py`) with seven subcommands. Six pipeline modules
  under `pipeline/`.

---

## Pipeline

End-to-end processing happens in six logical stages:

1. **Preprocess** (`pipeline/preprocessor.py`) — normalize color space and bit
   depth, bilateral denoise, CLAHE in LAB, optional ROI detection.
2. **Template detect** (`pipeline/template_detector.py`) — extract a 150-feature
   vector (aspect ratio, vertical-line density via Sobel+FFT, edge variance, hue
   histogram, etc.) and match against pre-computed signatures for the nine
   templates.
3. **Calibrate** (`pipeline/calibration_processor.py`) — interactive 7-step
   modal in the UI; persists a JSON per template under `backend/calibrations/`.
   The vertical grid is modeled as a cylindrical parabola
   `x = x_ref + a · (y − c_y)²` to account for drum distortion.
4. **Segment** (`pipeline/segmenter.py`) — per-template RGB color rules build a
   binary curve mask; a sliding window walks columns left-to-right, taking the
   median of mask pixels within a tight band around an expected `y`.
5. **Refine** (`pipeline/segmenter.py`) — wide-window reference curve, MAD-based
   outlier removal, moving-median + Gaussian smoothing; clamp to grid bounds.
6. **Export** — frontend converts pixel coordinates to time (via the curvature-
   corrected vertical mapping) and temperature (linear interpolation between
   horizontal lines), writes CSV next to the source image.

The 6-stage architecture is documented in detail in `roadmap.md`.

---

## Project layout

```
.
├── README.md                       (this file)
├── Project Report Template.tex     CMPE 492 final report (LaTeX)
├── Project Report Template.pdf     Compiled report
├── references.bib                  Bibliography for the report
├── roadmap.md                      Detailed pipeline + architecture notes
├── styles/                         FBE thesis style stub (replace with official)
├── figures/                        Report figures (UI screenshots)
└── thermogram-app/
    ├── package.json
    ├── vite.config.ts
    ├── src/                        React frontend
    │   ├── App.tsx                 Top-level layout, view state, IPC orchestration
    │   ├── components/
    │   │   ├── Workspace/          ImageViewer + GridOverlay + CurveOverlay
    │   │   ├── Sidebar/            UploadPanel + TemplateSelector
    │   │   ├── CalibrationModal/   7-step calibration UI
    │   │   └── ExportModal/        CSV export configuration
    │   ├── stores/                 Zustand stores
    │   ├── hooks/                  useImageLoader, useProcessing, useZoomPan
    │   ├── utils/                  exportCurve, gridLineData, imageRotation, …
    │   └── types/                  Shared TypeScript types
    ├── src-tauri/                  Rust host (Tauri 2)
    │   ├── Cargo.toml
    │   ├── tauri.conf.json
    │   └── src/
    │       ├── main.rs
    │       └── lib.rs              All 11 IPC commands
    └── backend/                    Python sidecar
        ├── main.py                 CLI entry point (7 subcommands)
        ├── pipeline/
        │   ├── preprocessor.py
        │   ├── template_detector.py
        │   ├── calibration_processor.py
        │   ├── color_profiles.py   Per-template RGB rules
        │   ├── segmenter.py
        │   └── dewarper.py         Grid overlay generator (used by preview)
        ├── calibrations/           One JSON per calibrated template
        ├── configs/                Default chart-format configs
        ├── utils/                  image_utils, grid_utils
        ├── scripts/                Batch comparison tooling
        ├── tests/                  pytest suite (15 files, 66 cases)
        └── requirements.txt
```

---

## Installing

### Prerequisites

- **Node.js** 18+ and **npm**
- **Rust** 1.78+ (`rustup install stable`)
- **Python** 3.11+ available as `python3` on the PATH
- macOS or Windows (Linux likely works but is not tested)

### Setup

```bash
# Python backend
cd thermogram-app/backend
pip install -r requirements.txt

# Frontend + Tauri host
cd ..
npm install
```

### Run in development

```bash
cd thermogram-app
npm run tauri dev
```

The first launch builds the Rust host (slow); subsequent launches are fast.

### Build a release binary

```bash
cd thermogram-app
npm run tauri build
```

Output:
- macOS: a `.app` bundle under `src-tauri/target/release/bundle/macos/`
- Windows: an MSI installer under `src-tauri/target/release/bundle/msi/`

The release binary bundles the Python backend source under `Resources/`; the user
needs a working `python3` on the PATH, but no virtualenv or PIP installs are
required after install.

---

## Usage

1. **Drop a scan** (TIFF, PNG, or JPEG) onto the application window, or click
   *Upload* in the sidebar.
2. The application auto-detects the template and reloads the previous
   calibration if one exists for that template.
3. If the template is **uncalibrated**, the *Calibrate* button in the header
   turns yellow. Click it and follow the 7-step modal: three horizontal steps
   (top line, rotation pivot, top temperature + spacing) and four vertical
   steps (reference line top, bottom, hour, curvature + spacing).
4. Switch to **View 2 (Curve)**. The application extracts the curve
   automatically and overlays it on the scan.
5. *Optional refinements:*
   - **Set Starting Points** to constrain extraction to specific x ranges.
   - **Edit Curve** to freehand-draw a correction; the segmenter snaps the
     drawing to the local ink.
   - **Select Area to Refine** to re-extract a rectangular region only.
   - Drag, multi-select, and delete individual points directly on the canvas.
   - Undo/redo with `Cmd/Ctrl+Z` and `Cmd/Ctrl+Shift+Z`.
6. **Export CSV** writes `(id, time, temperature, xValue, yValue, isEdited?)`
   next to the source image and opens a *Reveal in Finder* / *Open* toast.

### Keyboard shortcuts

| Key                              | Action                       |
| -------------------------------- | ---------------------------- |
| `0` / `1` / `2`                  | Image / Grid / Curve view    |
| `Cmd/Ctrl + +` / `-` / `0`       | Zoom in / out / reset        |
| `Cmd/Ctrl + Z`                   | Undo (curve edits)           |
| `Cmd/Ctrl + Shift + Z`           | Redo (curve edits)           |
| `Delete` / `Backspace`           | Delete selected curve points |

---

## CSV output

The exporter writes one row per sampled point:

```csv
id,time,temperature,xValue,yValue,isEdited
1,1980-01-01T07:30:00,18.234,612.50,341.20,no
2,1980-01-01T07:35:00,18.512,617.40,338.10,yes
```

The `isEdited` column is only emitted when at least one point has been moved,
inserted, or deleted relative to the raw extraction. Pixel coordinates
(`xValue`, `yValue`) are in the image's natural (un-zoomed) coordinate system,
so downstream code can always re-derive the curve from the original scan.

Full schema is in Appendix A of the project report.

---

## Templates and calibration

The classifier recognizes nine templates:

| Template     | Format  | Period      | Grid color    |
| ------------ | ------- | ----------- | ------------- |
| `gunluk-1`   | Daily   | 1990s       | yellow/cream  |
| `gunluk-2`   | Daily   | 1980        | green/olive   |
| `gunluk-3`   | Daily   | 1980s       | orange        |
| `haftalik-1` | Weekly  | 1940s       | orange        |
| `haftalik-2` | Weekly  | 1970s       | orange/pink   |
| `4_gunluk-1` | 4-day   | 1940s       | orange        |
| `4_gunluk-2` | 4-day   | 1955        | orange        |
| `4_gunluk-3` | 4-day   | 1945–1950s  | orange        |
| `4_gunluk-4` | 4-day   | 1950s       | orange/red    |

Each calibrated template has one JSON file under `thermogram-app/backend/calibrations/`.
The schema is documented in Appendix B of the project report.

The color rules used by the curve segmenter live in
`thermogram-app/backend/pipeline/color_profiles.py`. The default profile targets
the pinkish/reddish ink common to most `haftalik` and `4_gunluk` scans;
`gunluk-1/2/3` and `haftalik-2` have per-template overrides. The full parameter
table is in Appendix C of the project report.

---

## Testing

The backend ships a synthetic-data pytest suite under
`thermogram-app/backend/tests/`:

```bash
cd thermogram-app/backend
python3 -m pytest tests/
```

15 test files, 66 cases, runs in under a second. Coverage spans the
preprocessor, color profiles, segmenter (color mask, end-to-end extract, MAD
outliers, snap-drawing), template detector, calibration processor, grid utils,
and image utils. All fixtures are constructed from synthetic data, so the suite
has no runtime dependency on real thermogram scans.

Interactive testing on real scans plus the batch comparison scripts under
`thermogram-app/backend/scripts/` cover what unit tests cannot — regressions
that only manifest on a particular template's grid color or ink fading.

---

## Project report

The CMPE 492 final report is at the repository root:

- `Project Report Template.tex` — LaTeX source
- `references.bib` — Bibliography
- `Project Report Template.pdf` — Compiled PDF

To recompile:

```bash
pdflatex "Project Report Template.tex"
bibtex   "Project Report Template"
pdflatex "Project Report Template.tex"
pdflatex "Project Report Template.tex"
```

`styles/fbe_tez.sty` and `styles/fbe_tez_v11.bst` are minimal stubs of the
Boğaziçi FBE thesis style; replace them with the official files before final
submission.

---

## Authors

- **Ahmet Selçuk Ersoy** — desktop host (Tauri/Rust), React UI, Zustand stores,
  CSV export, image rotation utilities
- **Kerem Bozkurt** — Python pipeline core, template detector, color profiles,
  calibration processor, segmenter algorithms

Advised by **H. Birkan Yılmaz**, Boğaziçi University Department of Computer
Engineering.

---

## License

See `LICENSE`.
