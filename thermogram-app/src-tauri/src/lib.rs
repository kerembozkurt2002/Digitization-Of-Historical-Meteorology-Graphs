use serde::{Deserialize, Serialize};
use std::process::Command;
use std::fs;
use std::path::Path;

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

/// Get the path to the Python backend
fn get_backend_path() -> String {
    // In development, use relative path from src-tauri
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
        .unwrap_or_else(|_| ".".to_string());
    format!("{}/backend/main.py", manifest_dir.replace("/src-tauri", ""))
}

/// Run Python backend command and return output
fn run_python_command(args: Vec<&str>) -> Result<String, String> {
    let backend_path = get_backend_path();

    let mut cmd_args = vec![&backend_path[..]];
    cmd_args.extend(args);

    let output = Command::new("python3")
        .args(&cmd_args)
        .current_dir(std::path::Path::new(&backend_path).parent().unwrap())
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    if output.status.success() {
        String::from_utf8(output.stdout)
            .map_err(|e| format!("Failed to parse output: {}", e))
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        Err(format!("Python error: {} {}", stderr, stdout))
    }
}

#[tauri::command]
fn preview_grid(image_path: String, algorithm: Option<i32>, output_path: Option<String>, curvature: Option<f64>) -> Result<PreviewResponse, String> {
    let algo_str = algorithm.unwrap_or(1).to_string();
    let mut args = vec!["preview", "--image", &image_path, "--algorithm", &algo_str];

    let output_path_str;
    if let Some(ref path) = output_path {
        output_path_str = path.clone();
        args.push("--output");
        args.push(&output_path_str);
    }

    let curvature_str;
    if let Some(curv) = curvature {
        curvature_str = curv.to_string();
        args.push("--curvature");
        args.push(&curvature_str);
    }

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn detect_template(image_path: String) -> Result<DetectTemplateResponse, String> {
    let args = vec!["detect-template", "--image", &image_path];

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn get_calibration(template_id: String) -> Result<GetCalibrationResponse, String> {
    let args = vec!["get-calibration", "--template-id", &template_id];

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn save_calibration_simple(
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

    let calibration_json = calibration_data.to_string();

    let args = vec![
        "save-calibration-simple",
        "--data", &calibration_json
    ];

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn extract_curve(image_path: String, template_id: String, sample_interval: Option<i32>, x_min: Option<i32>, x_max: Option<i32>, y_hint: Option<i32>, y_hint_end: Option<i32>, y_min: Option<i32>, y_max: Option<i32>) -> Result<ExtractCurveResponse, String> {
    let interval_str = sample_interval.unwrap_or(5).to_string();
    let x_min_str = x_min.map(|v| v.to_string());
    let x_max_str = x_max.map(|v| v.to_string());
    let y_hint_str = y_hint.map(|v| v.to_string());
    let y_hint_end_str = y_hint_end.map(|v| v.to_string());
    let y_min_str = y_min.map(|v| v.to_string());
    let y_max_str = y_max.map(|v| v.to_string());

    let mut args = vec![
        "extract-curve",
        "--image", &image_path,
        "--template-id", &template_id,
        "--sample-interval", &interval_str,
    ];

    if let Some(ref v) = x_min_str {
        args.push("--x-min");
        args.push(v);
    }
    if let Some(ref v) = x_max_str {
        args.push("--x-max");
        args.push(v);
    }
    if let Some(ref v) = y_hint_str {
        args.push("--y-hint");
        args.push(v);
    }
    if let Some(ref v) = y_hint_end_str {
        args.push("--y-hint-end");
        args.push(v);
    }
    if let Some(ref v) = y_min_str {
        args.push("--y-min");
        args.push(v);
    }
    if let Some(ref v) = y_max_str {
        args.push("--y-max");
        args.push(v);
    }

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SaveAnnotationResponse {
    pub success: bool,
    pub error: Option<String>,
    pub path: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StrokeData {
    pub id: i32,
    pub label: String,
    pub num_points: usize,
    pub points: Vec<CurvePointData>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CleanAnnotationResponse {
    pub success: bool,
    pub error: Option<String>,
}

#[tauri::command]
fn save_curve_annotation(
    image_path: String,
    template_id: String,
    points: Vec<CurvePointData>,
    strokes: Option<Vec<StrokeData>>,
) -> Result<SaveAnnotationResponse, String> {
    let annotations_dir = {
        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
            .unwrap_or_else(|_| ".".to_string());
        let base = manifest_dir.replace("/src-tauri", "");
        format!("{}/annotations", base)
    };

    if let Err(e) = fs::create_dir_all(&annotations_dir) {
        return Ok(SaveAnnotationResponse {
            success: false,
            error: Some(format!("Failed to create annotations directory: {}", e)),
            path: None,
        });
    }

    let stem = Path::new(&image_path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("unknown");

    let annotation_path = format!("{}/{}.json", annotations_dir, stem);

    let now = chrono::Local::now().to_rfc3339();

    let mut annotation = serde_json::json!({
        "image_path": image_path,
        "template_id": template_id,
        "annotated_at": now,
        "num_points": points.len(),
        "points": points,
    });

    if let Some(ref s) = strokes {
        annotation["strokes"] = serde_json::to_value(s).unwrap_or_default();
    }

    match fs::write(&annotation_path, serde_json::to_string_pretty(&annotation).unwrap()) {
        Ok(_) => Ok(SaveAnnotationResponse {
            success: true,
            error: None,
            path: Some(annotation_path),
        }),
        Err(e) => Ok(SaveAnnotationResponse {
            success: false,
            error: Some(format!("Failed to write annotation file: {}", e)),
            path: None,
        }),
    }
}

#[tauri::command]
fn clean_annotation(file_path: String) -> Result<CleanAnnotationResponse, String> {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
        .unwrap_or_else(|_| ".".to_string());
    let base = manifest_dir.replace("/src-tauri", "");
    let utils_path = format!("{}/backend/annotation_utils.py", base);
    let backend_dir = format!("{}/backend", base);

    let output = Command::new("python3")
        .args(&[&utils_path, "clean", "--file", &file_path])
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    if output.status.success() {
        Ok(CleanAnnotationResponse {
            success: true,
            error: None,
        })
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Ok(CleanAnnotationResponse {
            success: false,
            error: Some(format!("Cleaning failed: {}", stderr)),
        })
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            preview_grid,
            detect_template,
            get_calibration,
            save_calibration_simple,
            extract_curve,
            save_curve_annotation,
            clean_annotation
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
