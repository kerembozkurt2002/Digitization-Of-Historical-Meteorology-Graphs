use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
pub struct DewarpResponse {
    pub success: bool,
    pub message: Option<String>,
    pub error: Option<String>,
    pub grid_lines_detected: Option<i32>,
    pub original_image: Option<String>,
    pub straightened_image: Option<String>,
    pub forward_transform: Option<Vec<Vec<f64>>>,
    pub inverse_transform: Option<Vec<Vec<f64>>>,
    pub output_path: Option<String>,
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
pub struct HealthResponse {
    pub success: bool,
    pub message: String,
    pub version: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FlattenedResponse {
    pub success: bool,
    pub message: Option<String>,
    pub error: Option<String>,
    pub vertical_lines: Option<i32>,
    pub horizontal_lines: Option<i32>,
    pub flattened_image: Option<String>,
    pub output_path: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StraightenedGridResponse {
    pub success: bool,
    pub message: Option<String>,
    pub error: Option<String>,
    pub vertical_lines: Option<i32>,
    pub horizontal_lines: Option<i32>,
    pub straightened_grid_image: Option<String>,
    pub output_path: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MatchBox {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MatchTemplateResponse {
    pub success: bool,
    pub message: Option<String>,
    pub error: Option<String>,
    pub match_count: Option<i32>,
    pub boxes: Option<Vec<MatchBox>>,
    pub match_image: Option<String>,
    pub output_path: Option<String>,
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
pub struct HasCalibrationResponse {
    pub success: bool,
    pub error: Option<String>,
    pub template_id: Option<String>,
    pub exists: Option<bool>,
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
fn health_check() -> Result<HealthResponse, String> {
    let output = run_python_command(vec!["health"])?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn dewarp_image(image_path: String, output_path: Option<String>) -> Result<DewarpResponse, String> {
    let mut args = vec!["dewarp", "--image", &image_path];

    let output_path_str;
    if let Some(ref path) = output_path {
        output_path_str = path.clone();
        args.push("--output");
        args.push(&output_path_str);
    }

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {} - Output: {}", e, output))
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
fn flattened_grid(image_path: String, output_path: Option<String>) -> Result<FlattenedResponse, String> {
    let mut args = vec!["flattened", "--image", &image_path];

    let output_path_str;
    if let Some(ref path) = output_path {
        output_path_str = path.clone();
        args.push("--output");
        args.push(&output_path_str);
    }

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn straightened_grid(image_path: String, output_path: Option<String>) -> Result<StraightenedGridResponse, String> {
    let mut args = vec!["straightened-grid", "--image", &image_path];

    let output_path_str;
    if let Some(ref path) = output_path {
        output_path_str = path.clone();
        args.push("--output");
        args.push(&output_path_str);
    }

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn match_template(image_path: String, output_path: Option<String>) -> Result<MatchTemplateResponse, String> {
    let mut args = vec!["match-template", "--image", &image_path];

    let output_path_str;
    if let Some(ref path) = output_path {
        output_path_str = path.clone();
        args.push("--output");
        args.push(&output_path_str);
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
fn save_calibration(
    template_id: String,
    top_point: CalibrationPoint,
    bottom_point: CalibrationPoint,
    center_y: f64,
    curvature: f64,
    image_width: i32,
    image_height: i32
) -> Result<SaveCalibrationResponse, String> {
    // Convert points to JSON strings
    let top_point_json = serde_json::to_string(&top_point)
        .map_err(|e| format!("Failed to serialize top_point: {}", e))?;
    let bottom_point_json = serde_json::to_string(&bottom_point)
        .map_err(|e| format!("Failed to serialize bottom_point: {}", e))?;

    let center_y_str = center_y.to_string();
    let curvature_str = curvature.to_string();
    let width_str = image_width.to_string();
    let height_str = image_height.to_string();

    let args = vec![
        "save-calibration",
        "--template-id", &template_id,
        "--top-point", &top_point_json,
        "--bottom-point", &bottom_point_json,
        "--center-y", &center_y_str,
        "--curvature", &curvature_str,
        "--image-width", &width_str,
        "--image-height", &height_str
    ];

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
fn has_calibration(template_id: String) -> Result<HasCalibrationResponse, String> {
    let args = vec!["has-calibration", "--template-id", &template_id];

    let output = run_python_command(args)?;
    serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
fn save_calibration_full(
    template_id: String,
    // Vertical calibration
    vertical_line1_top: CalibrationPoint,
    vertical_line1_bottom: CalibrationPoint,
    vertical_line1_hour: String,
    vertical_line2_top: CalibrationPoint,
    vertical_line2_hour: String,
    vertical_last_top: CalibrationPoint,
    center_y: f64,
    curvature: f64,
    vertical_spacing_adjust: f64,
    // Horizontal calibration
    horizontal_top: CalibrationPoint,
    horizontal_top_temp: i32,
    horizontal_second: CalibrationPoint,
    horizontal_bottom: CalibrationPoint,
    horizontal_spacing_adjust: f64,
    // Image dimensions
    image_width: i32,
    image_height: i32,
) -> Result<SaveCalibrationResponse, String> {
    // Build a JSON object with all calibration data
    let calibration_data = serde_json::json!({
        "template_id": template_id,
        "vertical": {
            "line1_top": vertical_line1_top,
            "line1_bottom": vertical_line1_bottom,
            "line1_hour": vertical_line1_hour,
            "line2_top": vertical_line2_top,
            "line2_hour": vertical_line2_hour,
            "last_top": vertical_last_top,
            "center_y": center_y,
            "curvature": curvature,
            "spacing_adjust": vertical_spacing_adjust
        },
        "horizontal": {
            "top": horizontal_top,
            "top_temp": horizontal_top_temp,
            "second": horizontal_second,
            "bottom": horizontal_bottom,
            "spacing_adjust": horizontal_spacing_adjust
        },
        "image_width": image_width,
        "image_height": image_height
    });

    let calibration_json = calibration_data.to_string();

    let args = vec![
        "save-calibration-full",
        "--data", &calibration_json
    ];

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
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            health_check,
            dewarp_image,
            preview_grid,
            flattened_grid,
            straightened_grid,
            match_template,
            detect_template,
            save_calibration,
            get_calibration,
            has_calibration,
            save_calibration_full,
            save_calibration_simple
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
