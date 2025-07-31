import subprocess
import sys
import argparse
import concurrent.futures
from pathlib import Path
import threading
import time
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn
from rich.text import Text
from rich.layout import Layout
import webbrowser

def build_with_tidy(target, tidy, status_lock, status, log_lines, output_lines):
    with status_lock:
        log_lines.append(f"[STARTED] {target}")
        status['running'].add(target)
    cmd = ["bazel", "build", target]
    if tidy:
        cmd.append("--config=tidy")
    # Stream output live to output_lines
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = f"==== {target} ====\n"
    for line in process.stdout:
        with status_lock:
            output_lines.append(line.rstrip())
        output += line
    process.wait()
    if process.returncode == 0:
        output += f"Build succeeded for {target}\n"
        with status_lock:
            output_lines.append(f"Build succeeded for {target}")
    else:
        output += f"Build failed for {target}\n"
        with status_lock:
            output_lines.append(f"Build failed for {target}")
    with status_lock:
        status['running'].remove(target)
        status['done'] += 1
        log_lines.append(f"[FINISHED] {target} ({status['done']}/{status['total']})")
    return output

def main():
    parser = argparse.ArgumentParser(description="Build Bazel targets with or without --config=tidy.")
    parser.add_argument("--build-only", action="store_true", help="Build without --config=tidy")
    parser.add_argument("--output", type=str, default="build_output.log", help="Output file to collate results")
    args = parser.parse_args()

    tidy = not args.build_only
    targets = [line.strip() for line in sys.stdin if line.strip()]

    status = {'done': 0, 'total': len(targets), 'running': set()}
    status_lock = threading.Lock()
    log_lines = []
    output_lines = []

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("{task.completed}/{task.total}"),
    )
    build_task = progress.add_task("Building targets", total=len(targets))

    def render_layout():
        with status_lock:
            log_text = "\n".join(log_lines[-30:])  # Show last 30 lines
            output_text = "\n".join(output_lines[-30:])  # Show last 30 outputs (now live)
        log_panel = Panel(Text(log_text), title="Build Log", border_style="blue", height=20)
        output_panel = Panel(Text(output_text), title="Build Output (Live)", border_style="green", height=20)
        layout = Layout()
        layout.split_row(
            Layout(log_panel, name="log", ratio=1),
            Layout(output_panel, name="output", ratio=1)
        )
        # Place the progress bar at the bottom using a vertical split
        root_layout = Layout()
        root_layout.split_column(
            Layout(layout, name="main", ratio=4),
            Layout(progress, name="progress", ratio=1)
        )
        return root_layout

    def status_reporter(live):
        while True:
            with status_lock:
                done = status['done']
                total = status['total']
            if done >= total:
                progress.update(build_task, completed=total)
                live.update(render_layout())
                break
            live.update(render_layout())
            time.sleep(0.2)

    outputs = []
    with Live(render_layout(), refresh_per_second=10, screen=True) as live:
        reporter_thread = threading.Thread(target=status_reporter, args=(live,), daemon=True)
        reporter_thread.start()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_target = {
                executor.submit(build_with_tidy, target, tidy, status_lock, status, log_lines, output_lines): target
                for target in targets
            }
            for future in concurrent.futures.as_completed(future_to_target):
                outputs.append(future.result())
                with status_lock:
                    progress.update(build_task, advance=1)
        reporter_thread.join(timeout=1)
    # Prevent clearing the screen after Live context ends
    print("\nBuild finished. See log and output panels above for details.")
    # Open the output file in the default web browser
    output_path = Path(args.output).resolve()
    webbrowser.open(f"file://{output_path}")

    output_path = Path(args.output)
    with output_path.open("w") as f:
        for out in outputs:
            f.write(out)
            f.write("\n")

if __name__ == "__main__":
    main()
