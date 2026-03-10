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
            match_template
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
