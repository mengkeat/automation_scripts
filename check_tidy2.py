"""
check_tidy2.py

A script to batch-run clang-tidy on a list of C/C++ source files, with live progress and logging.

Features:
- Accepts a list of files (one per line) via stdin.
- For each file:
    - Locates the nearest parent directory containing a .clang-tidy configuration.
    - Locates the corresponding raw_compile_commands.json for Bazel-based builds.
    - Runs clang-tidy with the correct configuration and compile commands.
    - Collects and displays results, errors, and logs in a live updating terminal UI using Rich.
- Processes files in parallel using a thread pool for efficiency.
- Writes a summary of results to an output log file and opens it in the default web browser.

Intended for use in large Bazel-based C++ codebases to automate static analysis and code quality checks.
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path
import threading
import time
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn
from rich.text import Text
from rich.layout import Layout
import webbrowser


def find_clang_tidy_dir(path):
    """
    Find the first parent directory containing a .clang-tidy file.

    Args:
        path: Path to start the search from

    Returns:
        Path object to the directory containing .clang-tidy or None if not found
    """
    current = Path(path).resolve()

    while current != current.parent:  # Stop at root directory
        if (current / ".clang-tidy").exists():
            return current
        current = current.parent

    return None


def extract_target_stem(target):
    """
    Extract the stem (filename without extension) from a target path.

    Args:
        target: The target path string

    Returns:
        The stem of the target file
    """
    return Path(target).stem


def find_compile_commands(clang_tidy_dir, target_stem):
    """
    Find the raw_compile_commands.json file for the given target.

    Args:
        clang_tidy_dir: Directory containing .clang-tidy file
        target_stem: Stem of the target filename

    Returns:
        Path to the raw_compile_commands.json file or None if not found
    """
    # Look for bazel-bin directory
    bazel_bin_dir = clang_tidy_dir / "bazel-bin"

    if not bazel_bin_dir.exists():
        return None

    # Search for raw_compile_commands.json files
    for root, _, files in os.walk(bazel_bin_dir):
        for file in files:
            if file == "raw_compile_commands.json" and target_stem in str(Path(root)):
                return Path(root) / file

    return None


def run_clang_tidy(target_file, compile_commands_path):
    """
    Run clang-tidy-19 on the target file.

    Args:
        target_file: Path to the file to analyze
        compile_commands_path: Path to the raw_compile_commands.json file

    Returns:
        Output of the clang-tidy command
    """
    cmd = [
        "clang-tidy-20",
        str(target_file),
        f"-p={compile_commands_path}",
    ]
    print("Running command:", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout + ("\n" + result.stderr if result.stderr else "")
    except subprocess.SubprocessError as e:
        return f"Error running clang-tidy: {str(e)}"


def process_target(target, status_lock, status, log_lines, output_lines):
    """
    Process a target by running clang-tidy on it.

    Args:
        target: Target file path
        status_lock: Lock for thread safety
        status: Status dictionary
        log_lines: List for logging messages
        output_lines: List for output messages

    Returns:
        Output string with clang-tidy results
    """
    with status_lock:
        log_lines.append(f"[PROCESSING] {target}")
        status["running"].add(target)

    target_path = Path(target).resolve()
    output = f"==== {target} ====\n"

    # Step 1: Find directory with .clang-tidy
    clang_tidy_dir = find_clang_tidy_dir(target_path)
    if not clang_tidy_dir:
        error_msg = f"No .clang-tidy file found for {target}"
        output += error_msg + "\n"

        with status_lock:
            output_lines.append(error_msg)
            status["running"].remove(target)
            status["done"] += 1
            log_lines.append(f"[ERROR] {target} ({status['done']}/{status['total']})")

        return output

    # Step 2: Extract target stem
    target_stem = extract_target_stem(target)

    # Step 3: Find compile commands
    compile_commands = find_compile_commands(clang_tidy_dir, target_stem)
    if not compile_commands:
        error_msg = f"No raw_compile_commands.json found for {target_stem}"
        output += error_msg + "\n"

        with status_lock:
            output_lines.append(error_msg)
            status["running"].remove(target)
            status["done"] += 1
            log_lines.append(f"[ERROR] {target} ({status['done']}/{status['total']})")

        return output

    # Step 4: Run clang-tidy
    log_message = (
        f"Running clang-tidy on {target} with compile commands from {compile_commands}"
    )
    with status_lock:
        log_lines.append(log_message)

    clang_output = run_clang_tidy(target_path, compile_commands)
    output += clang_output + "\n"

    # Log completion
    with status_lock:
        if clang_output.strip():
            output_lines.append(f"Found issues in {target}")
        else:
            output_lines.append(f"No issues found in {target}")

        status["running"].remove(target)
        status["done"] += 1
        log_lines.append(f"[FINISHED] {target} ({status['done']}/{status['total']})")

    return output


def main():
    parser = argparse.ArgumentParser(description="Process Bazel targets.")
    parser.add_argument(
        "--output",
        type=str,
        default="processing_output.log",
        help="Output file to collate results",
    )
    args = parser.parse_args()

    targets = [line.strip() for line in sys.stdin if line.strip()]

    status = {"done": 0, "total": len(targets), "running": set()}
    status_lock = threading.Lock()
    log_lines = []
    output_lines = []

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("{task.completed}/{task.total}"),
    )
    process_task = progress.add_task("Processing targets", total=len(targets))

    def render_layout():
        with status_lock:
            log_text = "\n".join(log_lines[-30:])  # Show last 30 lines
            output_text = "\n".join(
                output_lines[-30:]
            )  # Show last 30 outputs (now live)
        log_panel = Panel(
            Text(log_text), title="Processing Log", border_style="blue", height=20
        )
        output_panel = Panel(
            Text(output_text),
            title="Processing Output",
            border_style="green",
            height=20,
        )
        layout = Layout()
        layout.split_row(
            Layout(log_panel, name="log", ratio=1),
            Layout(output_panel, name="output", ratio=1),
        )
        # Place the progress bar at the bottom using a vertical split
        root_layout = Layout()
        root_layout.split_column(
            Layout(layout, name="main", ratio=4),
            Layout(progress, name="progress", ratio=1),
        )
        return root_layout

    def status_reporter(live):
        while True:
            with status_lock:
                done = status["done"]
                total = status["total"]
            if done >= total:
                progress.update(process_task, completed=total)
                live.update(render_layout())
                break
            live.update(render_layout())
            time.sleep(0.2)

    outputs = []
    with Live(render_layout(), refresh_per_second=10, screen=True) as live:
        reporter_thread = threading.Thread(
            target=status_reporter, args=(live,), daemon=True
        )
        reporter_thread.start()

        # Process targets in a thread pool
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_target = {
                executor.submit(
                    process_target, target, status_lock, status, log_lines, output_lines
                ): target
                for target in targets
            }
            for future in concurrent.futures.as_completed(future_to_target):
                outputs.append(future.result())
                with status_lock:
                    progress.update(process_task, advance=1)

        reporter_thread.join(timeout=1)

    # Prevent clearing the screen after Live context ends
    print("\nProcessing finished. See log and output panels above for details.")

    # Output results to file
    output_path = Path(args.output)
    with output_path.open("w") as f:
        for out in outputs:
            f.write(out)
            f.write("\n")

    # Open the output file in the default web browser
    output_path = output_path.resolve()
    print(f"Results written to {output_path}")
    webbrowser.open(f"file://{output_path}")


if __name__ == "__main__":
    main()
