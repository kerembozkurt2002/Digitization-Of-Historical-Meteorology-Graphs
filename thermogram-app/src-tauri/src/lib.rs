use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager};

/// Tracks every rotated temp PNG we wrote in this session so we can sweep
/// them on new-image load and on app shutdown.
#[derive(Default)]
struct TempFileTracker {
    files: Mutex<HashSet<PathBuf>>,
}

impl TempFileTracker {
    fn record(&self, path: &Path) {
        if let Ok(mut set) = self.files.lock() {
            set.insert(path.to_path_buf());
        }
    }

    /// Delete every tracked file and forget them. Errors per file are ignored
    /// — the file may already be gone or the user may not have permission.
    fn purge(&self) {
        if let Ok(mut set) = self.files.lock() {
            for path in set.drain() {
                let _ = std::fs::remove_file(&path);
            }
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PreviewResponse {
    pub success: bool,
    pub error: Option<String>,
    pub vertical_lines: Option<i32>,
    pub horizontal_lines: Option<i32>,
    pub preview_image: Option<String>,
    pub output_path: Option<String>,
    // Line positions for client-side rendering
    pub vertical_line_positions: Option<Vec<i32>>,
    pub horizontal_line_positions: Option<Vec<i32>>,
    pub image_height: Option<i32>,
    pub image_width: Option<i32>,
    // Curve coefficients: x = a*y² + b*y + x0
    pub curve_coeff_a: Option<f64>,
    pub curve_coeff_b: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DetectTemplateResponse {
    pub success: bool,
    pub error: Option<String>,
    pub template_id: Option<String>,
    pub chart_type: Option<String>,
    pub confidence: Option<f64>,
    pub period: Option<String>,
    pub grid_color: Option<String>,
    pub all_scores: Option<std::collections::HashMap<String, f64>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CalibrationPoint {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CalibrationDerived {
    pub top_point: CalibrationPoint,
    pub bottom_point: CalibrationPoint,
    pub curve_center_y: f64,
    pub curve_coeff_a: f64,
    // These fields are optional - not always present in calibration files
    pub line_slope: Option<f64>,
    pub line_mid_x: Option<f64>,
    pub line_mid_y: Option<f64>,
    pub line_spacing: f64,
    pub line_positions: Vec<f64>,
    // Horizontal data
    pub horizontal_spacing: Option<f64>,
    pub horizontal_positions: Option<Vec<f64>>,
    pub horizontal_top_temp: Option<i32>,
    pub horizontal_top_y: Option<f64>,
    // Reference values for alignment mode
    pub reference_hour: Option<i32>,
    pub reference_minute: Option<i32>,
    pub reference_temp: Option<i32>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SaveCalibrationResponse {
    pub success: bool,
    pub error: Option<String>,
    pub template_id: Option<String>,
    pub calibrated_at: Option<String>,
    pub line_spacing: Option<f64>,
    pub curve_coeff_a: Option<f64>,
    pub curve_coeff_b: Option<f64>,
    pub curve_center_y: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GetCalibrationResponse {
    pub success: bool,
    pub error: Option<String>,
    pub exists: Option<bool>,
    pub template_id: Option<String>,
    pub calibrated_at: Option<String>,
    pub image_dimensions: Option<std::collections::HashMap<String, i32>>,
    pub derived: Option<CalibrationDerived>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CurvePointData {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ExtractCurveResponse {
    pub success: bool,
    pub error: Option<String>,
    pub points: Option<Vec<CurvePointData>>,
    pub num_points: Option<i32>,
    pub message: Option<String>,
}

/// Resolve the directory we store mutable calibrations in. Lives under the
/// platform's app data dir so the bundled (read-only) backend binary doesn't
/// need write access to its own install location.
fn calibrations_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let base = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("app_data_dir resolve failed: {}", e))?;
    let dir = base.join("calibrations");
    std::fs::create_dir_all(&dir)
        .map_err(|e| format!("Failed to create calibrations dir: {}", e))?;
    Ok(dir)
}

/// Copy any bundled default calibrations into the user's data dir on first run.
/// Existing files are left untouched so user edits survive across launches.
fn seed_default_calibrations(app: &AppHandle) {
    let Ok(dest) = calibrations_dir(app) else { return };
    let Ok(resource_dir) = app.path().resource_dir() else { return };
    let src = resource_dir.join("resources").join("calibrations");
    let Ok(entries) = std::fs::read_dir(&src) else { return };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let Some(name) = path.file_name() else { continue };
        let target = dest.join(name);
        if !target.exists() {
            let _ = std::fs::copy(&path, &target);
        }
    }
}

/// Resolve the bundled backend executable. Lives next to the app resources;
/// dev builds fall back to the PyInstaller dist next to the repo's backend dir.
fn backend_executable(app: &AppHandle) -> Result<PathBuf, String> {
    let res = app
        .path()
        .resource_dir()
        .map_err(|e| format!("resource_dir resolve failed: {}", e))?;
    let exe_name = if cfg!(windows) { "backend.exe" } else { "backend" };
    let candidate = res.join("resources").join("backend").join(exe_name);
    if candidate.exists() {
        return Ok(candidate);
    }
    let dev = res.join("backend").join(exe_name);
    if dev.exists() {
        return Ok(dev);
    }
    Err(format!("Backend executable not found at {}", candidate.display()))
}

/// One live Python backend process and its stdio handles.
struct BackendProcess {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

/// Holds a single long-lived backend worker that we send NDJSON requests to.
/// First call spawns it; if it ever dies (write fails, EOF on read), we drop
/// the handle and the next call lazily respawns.
#[derive(Default)]
struct BackendManager {
    proc: Mutex<Option<BackendProcess>>,
}

impl BackendManager {
    fn ensure_spawned(&self, app: &AppHandle) -> Result<(), String> {
        let mut guard = self.proc.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            return Ok(());
        }
        let exe = backend_executable(app)?;
        let cal_dir = calibrations_dir(app)?;
        let mut child = Command::new(&exe)
            .arg("serve")
            .env("THERMOGRAM_CALIBRATIONS_DIR", &cal_dir)
            // Force UTF-8 across stdio + filesystem so non-ASCII filenames
            // (Turkish characters, Mac-origin NFD paths, …) survive the pipe
            // under Windows' default cp1252 locale.
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("Failed to spawn backend: {}", e))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "backend stdin missing".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "backend stdout missing".to_string())?;
        *guard = Some(BackendProcess {
            child,
            stdin,
            stdout: BufReader::new(stdout),
        });
        Ok(())
    }

    /// Send a single command, return the raw JSON response line (with trailing newline).
    fn call(
        &self,
        app: &AppHandle,
        cmd: &str,
        args: serde_json::Value,
    ) -> Result<String, String> {
        self.ensure_spawned(app)?;

        let req = serde_json::json!({"cmd": cmd, "args": args}).to_string() + "\n";
        let mut guard = self.proc.lock().map_err(|e| e.to_string())?;

        let io_result: std::io::Result<String> = (|| {
            let proc = guard.as_mut().expect("ensure_spawned must have set this");
            proc.stdin.write_all(req.as_bytes())?;
            proc.stdin.flush()?;
            let mut response = String::new();
            let n = proc.stdout.read_line(&mut response)?;
            if n == 0 {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::UnexpectedEof,
                    "backend closed stdout",
                ));
            }
            Ok(response)
        })();

        match io_result {
            Ok(r) => Ok(r),
            Err(e) => {
                // Tear down the dead worker so the next call respawns.
                if let Some(mut p) = guard.take() {
                    let _ = p.child.kill();
                    let _ = p.child.wait();
                }
                Err(format!("Backend IO failed: {}", e))
            }
        }
    }

    fn shutdown(&self) {
        if let Ok(mut guard) = self.proc.lock() {
            if let Some(mut p) = guard.take() {
                // Closing stdin lets the Python `for line in sys.stdin` loop end
                // cleanly; kill is a safety net in case the worker is stuck.
                drop(p.stdin);
                let _ = p.child.kill();
                let _ = p.child.wait();
            }
        }
    }
}

/// Send a JSON-encoded command to the persistent backend and parse the reply.
fn run_backend<T: serde::de::DeserializeOwned>(
    app: &AppHandle,
    cmd: &str,
    args: serde_json::Value,
) -> Result<T, String> {
    let mgr = app.state::<BackendManager>();
    let raw = mgr.call(app, cmd, args)?;
    serde_json::from_str(raw.trim())
        .map_err(|e| format!("Failed to parse backend response: {} (raw: {})", e, raw.trim()))
}

#[tauri::command]
fn preview_grid(app: AppHandle, image_path: String, algorithm: Option<i32>, output_path: Option<String>, curvature: Option<f64>) -> Result<PreviewResponse, String> {
    run_backend(
        &app,
        "preview",
        serde_json::json!({
            "image": image_path,
            "algorithm": algorithm.unwrap_or(1),
            "output": output_path,
            "curvature": curvature,
        }),
    )
}

#[tauri::command]
fn detect_template(app: AppHandle, image_path: String) -> Result<DetectTemplateResponse, String> {
    run_backend(
        &app,
        "detect-template",
        serde_json::json!({ "image": image_path }),
    )
}

/// Write a rotated/normalized image to the OS temp directory and return its path.
#[tauri::command]
fn save_rotated_image(
    image_path: String,
    base64_png: String,
    tracker: tauri::State<'_, TempFileTracker>,
) -> Result<String, String> {
    use base64::Engine;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(base64_png.as_bytes())
        .map_err(|e| format!("Bad base64: {}", e))?;
    let src = Path::new(&image_path);
    let stem = src
        .file_stem()
        .ok_or_else(|| "Source image has no filename stem".to_string())?
        .to_string_lossy()
        .to_string();
    let mut out = std::env::temp_dir();
    out.push(format!("{}_rotated.png", stem));
    std::fs::write(&out, &bytes)
        .map_err(|e| format!("Failed to write rotated image: {}", e))?;
    tracker.record(&out);
    Ok(out.to_string_lossy().to_string())
}

/// Delete every rotated temp file we created in this session. Called by the
/// frontend before loading a new image and again on app shutdown.
#[tauri::command]
fn cleanup_rotated_temp_files(tracker: tauri::State<'_, TempFileTracker>) -> Result<(), String> {
    tracker.purge();
    Ok(())
}

/// Open a file with the OS default handler (so CSV opens in the user's preferred app).
#[tauri::command]
fn open_file_path(path: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let mut cmd = Command::new("open");
    #[cfg(target_os = "windows")]
    let mut cmd = {
        let mut c = Command::new("cmd");
        c.args(["/C", "start", ""]);
        c
    };
    #[cfg(target_os = "linux")]
    let mut cmd = Command::new("xdg-open");

    cmd.arg(&path);
    cmd.spawn()
        .map(|_| ())
        .map_err(|e| format!("Failed to open path: {}", e))
}

/// Reveal a file in the OS file manager, selecting it when possible.
#[tauri::command]
fn reveal_file_in_folder(path: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .args(["-R", &path])
            .spawn()
            .map(|_| ())
            .map_err(|e| format!("Failed to reveal in Finder: {}", e))
    }
    #[cfg(target_os = "windows")]
    {
        Command::new("explorer")
            .arg(format!("/select,{}", path))
            .spawn()
            .map(|_| ())
            .map_err(|e| format!("Failed to reveal in Explorer: {}", e))
    }
    #[cfg(target_os = "linux")]
    {
        // No reliable cross-DE way to select; open the parent directory instead.
        let parent = Path::new(&path)
            .parent()
            .ok_or_else(|| "Path has no parent directory".to_string())?;
        Command::new("xdg-open")
            .arg(parent)
            .spawn()
            .map(|_| ())
            .map_err(|e| format!("Failed to open folder: {}", e))
    }
}

/// Write a CSV file next to the source image.
#[tauri::command]
fn write_csv_next_to_image(image_path: String, csv_content: String) -> Result<String, String> {
    let path = Path::new(&image_path);
    let parent = path
        .parent()
        .ok_or_else(|| "Image has no parent directory".to_string())?;
    let stem = path
        .file_stem()
        .ok_or_else(|| "Image has no filename stem".to_string())?;
    let csv_path = parent.join(format!("{}.csv", stem.to_string_lossy()));
    std::fs::write(&csv_path, csv_content)
        .map_err(|e| format!("Failed to write CSV: {}", e))?;
    Ok(csv_path.to_string_lossy().to_string())
}

#[tauri::command]
fn get_calibration(app: AppHandle, template_id: String) -> Result<GetCalibrationResponse, String> {
    run_backend(
        &app,
        "get-calibration",
        serde_json::json!({ "template_id": template_id }),
    )
}

#[tauri::command]
fn save_calibration_simple(
    app: AppHandle,
    template_id: String,
    // Horizontal (for rotation) - steps 1-3
    horizontal_top: CalibrationPoint,
    horizontal_end_point: CalibrationPoint,
    horizontal_top_temp: i32,
    horizontal_spacing: f64,
    rotation_angle: f64,
    // Vertical - steps 4-7
    vertical_line1_top: CalibrationPoint,
    vertical_line1_bottom: CalibrationPoint,
    vertical_line1_hour: String,
    center_y: f64,
    curvature: f64,
    vertical_spacing: f64,
    // Image
    image_width: i32,
    image_height: i32,
) -> Result<SaveCalibrationResponse, String> {
    // Build JSON object with simplified calibration data
    let calibration_data = serde_json::json!({
        "template_id": template_id,
        "horizontal": {
            "top": horizontal_top,
            "end_point": horizontal_end_point,
            "top_temp": horizontal_top_temp,
            "spacing": horizontal_spacing,
            "rotation_angle": rotation_angle
        },
        "vertical": {
            "line1_top": vertical_line1_top,
            "line1_bottom": vertical_line1_bottom,
            "line1_hour": vertical_line1_hour,
            "center_y": center_y,
            "curvature": curvature,
            "spacing": vertical_spacing
        },
        "image_width": image_width,
        "image_height": image_height
    });

    run_backend(
        &app,
        "save-calibration-simple",
        serde_json::json!({ "data": calibration_data.to_string() }),
    )
}

#[tauri::command]
fn extract_curve(app: AppHandle, image_path: String, template_id: String, sample_interval: Option<i32>, x_min: Option<i32>, x_max: Option<i32>, y_hint: Option<i32>, y_hint_end: Option<i32>, y_min: Option<i32>, y_max: Option<i32>) -> Result<ExtractCurveResponse, String> {
    run_backend(
        &app,
        "extract-curve",
        serde_json::json!({
            "image": image_path,
            "template_id": template_id,
            "sample_interval": sample_interval.unwrap_or(5),
            "x_min": x_min,
            "x_max": x_max,
            "y_hint": y_hint,
            "y_hint_end": y_hint_end,
            "y_min": y_min,
            "y_max": y_max,
        }),
    )
}

#[tauri::command]
fn snap_drawing_to_curve(
    app: AppHandle,
    image_path: String,
    template_id: String,
    drawn_points: Vec<CurvePointData>,
    snap_band: Option<i32>,
    sample_interval: Option<i32>,
) -> Result<ExtractCurveResponse, String> {
    let points_json = serde_json::to_string(&drawn_points)
        .map_err(|e| format!("Failed to serialize points: {}", e))?;
    run_backend(
        &app,
        "snap-drawing",
        serde_json::json!({
            "image": image_path,
            "template_id": template_id,
            "points": points_json,
            "snap_band": snap_band.unwrap_or(15),
            "sample_interval": sample_interval.unwrap_or(1),
        }),
    )
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(TempFileTracker::default())
        .manage(BackendManager::default())
        .setup(|app| {
            seed_default_calibrations(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            preview_grid,
            detect_template,
            save_rotated_image,
            cleanup_rotated_temp_files,
            write_csv_next_to_image,
            open_file_path,
            reveal_file_in_folder,
            get_calibration,
            save_calibration_simple,
            extract_curve,
            snap_drawing_to_curve
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            // Sweep any rotated temp files we wrote during the session.
            handle.state::<TempFileTracker>().purge();
            // Stop the persistent backend worker so it doesn't outlive the GUI.
            handle.state::<BackendManager>().shutdown();
        }
    });
}
