//! Config — mirrors the Python config.json so existing configs load unchanged.
//!
//! Pure std + serde; no Win32. Bounding-box coords are f64 because the Python
//! tool wrote them as floats (e.g. 1452.0).

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BBox {
    pub left: f64,
    pub top: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Config {
    #[serde(default)]
    pub log_file: String,
    #[serde(default)]
    pub default_guy: String,
    #[serde(default)]
    pub ch_binding: String,
    #[serde(default = "def_ch_threshold")]
    pub ch_threshold: f32,
    #[serde(default)]
    pub heal_threshold: f32,
    #[serde(default = "def_duck_check")]
    pub heal_duck_check_time: f32,
    #[serde(default)]
    pub heal_binding: String,
    #[serde(default)]
    pub bounding_boxes: HashMap<String, BBox>,
    #[serde(default)]
    pub match_words: Vec<String>,
    #[serde(default)]
    pub word_bindings: HashMap<String, String>,
    #[serde(default = "def_stop_heal")]
    pub stop_heal_log: String,
    #[serde(default)]
    pub verbose: bool,
}

fn def_ch_threshold() -> f32 {
    90.0
}
fn def_duck_check() -> f32 {
    2.0
}
fn def_stop_heal() -> String {
    "has been slain".to_string()
}

impl Default for Config {
    fn default() -> Self {
        Config {
            log_file: String::new(),
            default_guy: String::new(),
            ch_binding: String::new(),
            ch_threshold: def_ch_threshold(),
            heal_threshold: 0.0,
            heal_duck_check_time: def_duck_check(),
            heal_binding: String::new(),
            bounding_boxes: HashMap::new(),
            match_words: Vec::new(),
            word_bindings: HashMap::new(),
            stop_heal_log: def_stop_heal(),
            verbose: false,
        }
    }
}

/// config.json location: CLERIC_CONFIG env var, else `config.json` in the
/// current working directory.
pub fn config_path() -> PathBuf {
    std::env::var_os("CLERIC_CONFIG")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("config.json"))
}

pub fn load() -> Config {
    let path = config_path();
    match std::fs::read_to_string(&path) {
        Ok(text) => match serde_json::from_str::<Config>(&text) {
            Ok(cfg) => cfg,
            Err(e) => {
                eprintln!("[config] {} parse error: {e} -- using defaults", path.display());
                Config::default()
            }
        },
        Err(_) => {
            eprintln!("[config] {} not found -- using defaults", path.display());
            Config::default()
        }
    }
}

#[allow(dead_code)]
pub fn save(cfg: &Config) -> std::io::Result<()> {
    let text = serde_json::to_string_pretty(cfg).expect("serialize config");
    std::fs::write(config_path(), text)
}
