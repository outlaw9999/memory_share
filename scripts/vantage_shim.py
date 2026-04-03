import sys
import subprocess
import os
from pathlib import Path

def main():
    # AMSB v1.2.3 - The Vantage Protocol Shim (Python version)
    # Delegates 'kit vantage ...' to the Vantage CLI binary
    
    # Define paths (matching the .bat file logic)
    vantage_base = Path(r"E:\DEV\opensource_contrib\Vantage")
    vantage_exe_release = vantage_base / "target" / "release" / "vantage.exe"
    vantage_verify_release = vantage_base / "target" / "release" / "vantage-verify.exe"
    vantage_exe_debug = vantage_base / "target" / "debug" / "vantage.exe"
    vantage_verify_debug = vantage_base / "target" / "debug" / "vantage-verify.exe"

    args = sys.argv[1:]
    
    if len(args) > 0 and args[0] == "verify":
        # Handle verification mode
        if vantage_verify_release.exists():
            cmd = str(vantage_verify_release)
        elif vantage_verify_debug.exists():
            cmd = str(vantage_verify_debug)
        else:
            print("[kit-vantage] Error: Vantage-verify binary not found.")
            print(f"Please build it: cd {vantage_base / 'cli'} & cargo build --release")
            sys.exit(1)
        
        # Shift args for verify (first arg was 'verify')
        run_args = [cmd] + args[1:]
    else:
        # Handle normal mode
        if vantage_exe_release.exists():
            cmd = str(vantage_exe_release)
        elif vantage_exe_debug.exists():
            cmd = str(vantage_exe_debug)
        else:
            print("[kit-vantage] Error: Vantage binary not found.")
            print(f"Please build it: cd {vantage_base / 'cli'} & cargo build --release")
            sys.exit(1)
            
        run_args = [cmd] + args

    try:
        result = subprocess.run(run_args)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"[kit-vantage] Runtime error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
