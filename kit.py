import os
import sys
import subprocess

def main():
    # v1.2.4-TITANIUM: Smart Venv Redirector
    # Ensures the kit always runs in its deterministic substrate.
    
    root = os.path.dirname(os.path.abspath(__file__))
    if sys.platform == "win32":
        venv_python = os.path.join(root, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(root, ".venv", "bin", "python")

    # If the local venv exists and we're not already running in it...
    if os.path.exists(venv_python) and sys.executable != venv_python:
        # Re-exec using the venv python
        args = [venv_python, "-m", "kit"] + sys.argv[1:]
        sys.exit(subprocess.call(args))
    
    # Fallback/Direct execution if already in venv or no venv found
    from kit.cli.main import main as kit_main
    kit_main()

if __name__ == "__main__":
    main()
