// Prevents additional console window on Windows in release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

// Service state management
struct ServiceState {
    process: Mutex<Option<Child>>,
    port: Mutex<u16>,
}

#[derive(serde::Serialize)]
struct ServiceStatus {
    running: bool,
    port: u16,
}

#[derive(serde::Deserialize)]
struct StartServiceArgs {
    port: u16,
}

#[derive(serde::Serialize)]
struct Stats {
    total: u32,
    success: u32,
    error: u32,
    success_rate: f32,
}

#[derive(serde::Serialize)]
struct SystemInfo {
    cpu: f32,
    memory: f32,
    uptime: String,
}

// Start the Python service
#[tauri::command]
async fn start_service(
    args: StartServiceArgs,
    state: State<'_, ServiceState>,
) -> Result<(), String> {
    let mut process_lock = state.process.lock().map_err(|e| e.to_string())?;
    let mut port_lock = state.port.lock().map_err(|e| e.to_string())?;

    // Stop existing service if running
    if let Some(mut child) = process_lock.take() {
        let _ = child.kill();
    }

    // Get the current executable directory
    let exe_dir = std::env::current_exe()
        .map_err(|e| e.to_string())?
        .parent()
        .ok_or("Could not get exe directory")?
        .to_path_buf();

    // Path to Python script (relative to exe)
    let script_path = exe_dir.join("main.py");

    // Check if main.py exists
    if !script_path.exists() {
        // Try current working directory
        let cwd_script = std::env::current_dir()
            .map_err(|e| e.to_string())?
            .join("main.py");

        if !cwd_script.exists() {
            return Err(format!("Could not find main.py at {:?} or {:?}", script_path, cwd_script));
        }

        // Start Python service from cwd
        let child = Command::new("python")
            .arg("-m")
            .arg("uvicorn")
            .arg("main:app")
            .arg("--host")
            .arg("0.0.0.0")
            .arg("--port")
            .arg(args.port.to_string())
            .spawn()
            .map_err(|e| format!("Failed to start service: {}", e))?;

        *process_lock = Some(child);
    } else {
        // Start Python service from exe directory
        let child = Command::new("python")
            .current_dir(&exe_dir)
            .arg("-m")
            .arg("uvicorn")
            .arg("main:app")
            .arg("--host")
            .arg("0.0.0.0")
            .arg("--port")
            .arg(args.port.to_string())
            .spawn()
            .map_err(|e| format!("Failed to start service: {}", e))?;

        *process_lock = Some(child);
    }

    *port_lock = args.port;
    Ok(())
}

// Stop the Python service
#[tauri::command]
async fn stop_service(state: State<'_, ServiceState>) -> Result<(), String> {
    let mut process_lock = state.process.lock().map_err(|e| e.to_string())?;

    if let Some(mut child) = process_lock.take() {
        child.kill().map_err(|e| e.to_string())?;
    }

    Ok(())
}

// Get service status
#[tauri::command]
async fn get_service_status(state: State<'_, ServiceState>) -> Result<ServiceStatus, String> {
    let process_lock = state.process.lock().map_err(|e| e.to_string())?;
    let port_lock = state.port.lock().map_err(|e| e.to_string())?;

    let running = process_lock.is_some();
    let port = *port_lock;

    Ok(ServiceStatus { running, port })
}

// Get stats (mock for now)
#[tauri::command]
async fn get_stats() -> Result<Stats, String> {
    Ok(Stats {
        total: 0,
        success: 0,
        error: 0,
        success_rate: 100.0,
    })
}

// Get system info (mock for now)
#[tauri::command]
async fn get_system_info() -> Result<SystemInfo, String> {
    Ok(SystemInfo {
        cpu: 0.0,
        memory: 0.0,
        uptime: "00:00:00".to_string(),
    })
}

// Get OAuth credentials
#[tauri::command]
async fn get_oauth_creds() -> Result<serde_json::Value, String> {
    let creds_path = dirs::home_dir()
        .ok_or("Could not get home directory")?
        .join(".iflow")
        .join("oauth_creds.json");

    if creds_path.exists() {
        let content = std::fs::read_to_string(&creds_path).map_err(|e| e.to_string())?;
        let creds: serde_json::Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
        Ok(creds)
    } else {
        Ok(serde_json::json!(null))
    }
}

// Start OAuth flow
#[tauri::command]
async fn start_oauth() -> Result<serde_json::Value, String> {
    // Get the current executable directory
    let exe_dir = std::env::current_exe()
        .map_err(|e| e.to_string())?
        .parent()
        .ok_or("Could not get exe directory")?
        .to_path_buf();

    // Try to find the OAuth CLI script
    let script_path = exe_dir.join("iflow_oauth_cli.py");
    let cwd_script = std::env::current_dir()
        .map_err(|e| e.to_string())?
        .join("iflow_oauth_cli.py");

    let (cmd, args) = if script_path.exists() {
        ("python", vec![script_path.to_string_lossy().to_string()])
    } else if cwd_script.exists() {
        ("python", vec![cwd_script.to_string_lossy().to_string()])
    } else {
        return Err("Could not find iflow_oauth_cli.py".to_string());
    };

    // Run OAuth flow
    let output = Command::new(cmd)
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to run OAuth: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    // Parse the last JSON line from output
    let last_line = stdout.lines().last().unwrap_or("{}");
    let result: serde_json::Value = serde_json::from_str(last_line)
        .map_err(|e| format!("Failed to parse OAuth result: {} | Output: {}", e, stdout))?;

    if result.get("status") == Some(&serde_json::json!("success")) {
        Ok(result)
    } else {
        Err(format!("OAuth failed: {}", result.get("message").unwrap_or(&serde_json::json!(stderr))))
    }
}

// Delete OAuth credentials
#[tauri::command]
async fn delete_oauth_creds() -> Result<(), String> {
    let creds_path = dirs::home_dir()
        .ok_or("Could not get home directory")?
        .join(".iflow")
        .join("oauth_creds.json");

    if creds_path.exists() {
        std::fs::remove_file(&creds_path).map_err(|e| e.to_string())?;
    }

    Ok(())
}

// Get config
#[tauri::command]
async fn get_config() -> Result<serde_json::Value, String> {
    // Read from config file
    let config_path = dirs::home_dir()
        .ok_or("Could not get home directory")?
        .join(".iflow")
        .join("gui_config.json");

    if config_path.exists() {
        let content = std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?;
        let config: serde_json::Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
        Ok(config)
    } else {
        // Return default config
        Ok(serde_json::json!({
            "port": 8000,
            "baseUrl": "https://apis.iflow.cn/v1",
            "retry": 3,
            "timeout": 60,
            "theme": "dark",
            "language": "zh-CN"
        }))
    }
}

// Save config
#[tauri::command]
async fn save_config(config: serde_json::Value) -> Result<(), String> {
    let config_dir = dirs::home_dir()
        .ok_or("Could not get home directory")?
        .join(".iflow");

    std::fs::create_dir_all(&config_dir).map_err(|e| e.to_string())?;

    let config_path = config_dir.join("gui_config.json");
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(&config_path, content).map_err(|e| e.to_string())?;

    Ok(())
}

fn main() {
    let service_state = ServiceState {
        process: Mutex::new(None),
        port: Mutex::new(0),
    };

    tauri::Builder::default()
        .manage(service_state)
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            start_service,
            stop_service,
            get_service_status,
            get_stats,
            get_system_info,
            get_config,
            save_config,
            get_oauth_creds,
            start_oauth,
            delete_oauth_creds,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
