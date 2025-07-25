#!/usr/bin/env python3

import os
import yaml
import json
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from typing import Dict, List, Any

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class YAMLManager:
    def __init__(self):
        self.master_config_path = Path.home() / ".config" / "av_core" / "av_param.yaml"
        self.root_directory = None

    def set_root_directory(self, root_path: str) -> bool:
        """Set and validate the root directory"""
        try:
            path = Path(root_path)
            if path.exists() and path.is_dir():
                self.root_directory = path
                logging.info(f"Root directory set to {self.root_directory}")
                return True
            logging.warning(f"Invalid root directory path: {root_path}")
            return False
        except Exception as e:
            logging.error(f"Error setting root directory: {e}")
            return False

    def scan_yaml_files(self) -> List[Dict[str, Any]]:
        """Scan for YAML files in the robot_launch/params/default/nodes directory"""
        if not self.root_directory:
            logging.warning("Root directory not set, cannot scan for YAML files")
            return []

        params_nodes_path = (
            self.root_directory / "robot_launch" / "params" / "default" / "nodes"
        )
        if not params_nodes_path.exists():
            logging.warning(f"Directory not found: {params_nodes_path}")
            return []

        yaml_files = []
        logging.info(f"Scanning for YAML files in {params_nodes_path}")
        for yaml_file in params_nodes_path.rglob("*.yaml"):
            try:
                relative_path = yaml_file.relative_to(params_nodes_path)
                yaml_files.append(
                    {
                        "path": str(yaml_file),
                        "relative_path": str(relative_path),
                        "name": yaml_file.name,
                        "size": yaml_file.stat().st_size,
                    }
                )
            except Exception as e:
                logging.error(f"Error processing YAML file {yaml_file}: {e}")
                continue

        logging.info(f"Found {len(yaml_files)} YAML files")
        return sorted(yaml_files, key=lambda x: x["relative_path"])

    def load_yaml_content(self, file_path: str) -> Dict[str, Any]:
        """Load and parse YAML file content"""
        logging.info(f"Loading YAML content from: {file_path}")
        try:
            with open(file_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.error(f"Error loading YAML file {file_path}: {e}")
            return {"error": str(e)}

    def load_master_config(self) -> Dict[str, Any]:
        """Load the master configuration file"""
        logging.info(f"Loading master config from: {self.master_config_path}")
        try:
            if self.master_config_path.exists():
                with open(self.master_config_path, "r") as f:
                    return yaml.safe_load(f) or {}
            logging.warning("Master config file not found")
            return {}
        except Exception as e:
            logging.error(f"Error loading master config: {e}")
            return {}

    def check_duplicates(self, new_content: Dict[str, Any]) -> List[str]:
        """Check for duplicate keys in master config"""
        logging.info("Checking for duplicate keys in master config")
        master_config = self.load_master_config()
        duplicates = []

        def check_nested_keys(new_dict, master_dict, path=""):
            for key, value in new_dict.items():
                current_path = f"{path}.{key}" if path else key

                if key in master_dict:
                    if isinstance(value, dict) and isinstance(master_dict[key], dict):
                        check_nested_keys(value, master_dict[key], current_path)
                    else:
                        logging.warning(f"Duplicate key found: {current_path}")
                        duplicates.append(current_path)

        check_nested_keys(new_content, master_config)
        return duplicates

    def merge_yaml_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """Merge multiple YAML files and check for conflicts"""
        logging.info(f"Merging {len(file_paths)} YAML files")
        merged_content = {}
        conflicts = []

        for file_path in file_paths:
            logging.info(f"Processing file: {file_path}")
            content = self.load_yaml_content(file_path)
            if "error" in content:
                logging.warning(f"Skipping file due to error: {file_path}")
                continue

            file_conflicts = self.check_duplicates(content)
            if file_conflicts:
                conflict_details = [
                    f"{Path(file_path).name}: {conflict}" for conflict in file_conflicts
                ]
                logging.warning(f"Conflicts found in {file_path}: {conflict_details}")
                conflicts.extend(conflict_details)

            self._deep_merge(merged_content, content)

        logging.info("YAML file merging complete")
        return {"content": merged_content, "conflicts": conflicts}

    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge two dictionaries"""
        for key, value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def save_to_master(self, content: Dict[str, Any]) -> bool:
        """Append content to master configuration"""
        logging.info("Saving content to master configuration")
        try:
            # Ensure directory exists
            self.master_config_path.parent.mkdir(parents=True, exist_ok=True)

            master_config = self.load_master_config()
            self._deep_merge(master_config, content)

            with open(self.master_config_path, "w") as f:
                yaml.dump(master_config, f, default_flow_style=False, indent=2)

            logging.info("Master configuration saved successfully")
            return True
        except Exception as e:
            logging.error(f"Error saving to master config: {e}")
            return False


yaml_manager = YAMLManager()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/set_root", methods=["POST"])
def set_root():
    data = request.json
    root_path = data.get("root_path", "")

    if yaml_manager.set_root_directory(root_path):
        return jsonify({"success": True, "message": "Root directory set successfully"})
    else:
        return jsonify({"success": False, "message": "Invalid root directory path"})


@app.route("/api/scan_files")
def scan_files():
    files = yaml_manager.scan_yaml_files()
    return jsonify({"files": files})


@app.route("/api/preview_file")
def preview_file():
    file_path = request.args.get("path")
    if not file_path:
        return jsonify({"error": "No file path provided"})

    content = yaml_manager.load_yaml_content(file_path)
    return jsonify({"content": content})


@app.route("/api/merge_files", methods=["POST"])
def merge_files():
    data = request.json
    file_paths = data.get("file_paths", [])

    if not file_paths:
        return jsonify({"error": "No files selected"})

    result = yaml_manager.merge_yaml_files(file_paths)
    return jsonify(result)


@app.route("/api/save_merged", methods=["POST"])
def save_merged():
    data = request.json
    content = data.get("content", {})

    if yaml_manager.save_to_master(content):
        return jsonify({"success": True, "message": "Configuration saved successfully"})
    else:
        return jsonify({"success": False, "message": "Failed to save configuration"})


@app.route("/api/master_config")
def get_master_config():
    config = yaml_manager.load_master_config()
    return jsonify({"config": config})


if __name__ == "__main__":
    logging.info("Starting Flask server")
    app.run(debug=True, host="127.0.0.1", port=5000)
