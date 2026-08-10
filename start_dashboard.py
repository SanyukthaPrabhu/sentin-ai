"""
start_dashboard.py
==================
Sentin-AI Orchestrator. Starts both the FastAPI backend and Vite frontend dev server.

Run:
  python start_dashboard.py
"""

import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    print("=" * 60)
    print("[*] Sentin-AI: Launching React Dashboard & REST API")
    print("=" * 60)

    # 1. Start FastAPI Backend
    print("[API] Starting FastAPI backend on http://127.0.0.1:8000...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app",
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Give uvicorn a second to print startup lines or bind port
    time.sleep(1.5)

    # Check if backend failed immediately
    if backend_proc.poll() is not None:
        print("[ERR] FastAPI backend failed to start. Logs:")
        out, _ = backend_proc.communicate()
        print(out)
        sys.exit(1)
    else:
        print("[OK] FastAPI backend is running.")

    # 2. Start React Dev Server
    print("[UI] Starting Vite React dev server on http://localhost:5173...")
    frontend_proc = subprocess.Popen(
        ["npm.cmd", "run", "dev"],
        cwd=str(ROOT / "frontend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Give Vite a second to output port info
    time.sleep(1.5)

    if frontend_proc.poll() is not None:
        print("[ERR] Vite React frontend failed to start. Logs:")
        out, _ = frontend_proc.communicate()
        print(out)
        backend_proc.terminate()
        sys.exit(1)
    else:
        print("[OK] Vite React frontend is running.")

    print("\n[GO] Dashboard online! Open http://localhost:5173 in your browser.")
    print("     Press Ctrl+C to terminate both servers safely.\n")

    try:
        # Stream logs in real-time
        import threading
        def stream_logs(proc, prefix):
            for line in iter(proc.stdout.readline, ''):
                if line.strip():
                    print(f"[{prefix}] {line.strip()}")

        t1 = threading.Thread(target=stream_logs, args=(backend_proc, "API"), daemon=True)
        t2 = threading.Thread(target=stream_logs, args=(frontend_proc, "Vite"), daemon=True)
        t1.start()
        t2.start()

        # Keep parent alive until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n[*] Terminating Sentin-AI servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        backend_proc.wait()
        frontend_proc.wait()
        print("[OK] Servers shut down successfully. Goodbye!")

if __name__ == "__main__":
    main()
