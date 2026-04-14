import subprocess
import sys
from pathlib import Path


def main():
    # AMSB v1.2.3 - The Vantage Protocol Shim (Python version)
    # Delegates 'kit vantage ...' to the Vantage CLI binary
    
    vantage_base = Path(r"E:\DEV\opensource_contrib\Vantage")
    vantage_exe_release = vantage_base / "target" / "release" / "vantage.exe"
    vantage_exe_debug = vantage_base / "target" / "debug" / "vantage.exe"
    
    args = sys.argv[1:]
    
    # Handle command routing
    if vantage_exe_release.exists():
        engine = str(vantage_exe_release)
    elif vantage_exe_debug.exists():
        engine = str(vantage_exe_debug)
    else:
        print("[kit-vantage] Error: Vantage binary not found.")
        print(f"Please build it: cd {vantage_base / 'cli'} & cargo build --release")
        sys.exit(1)

    if args and args[0] == "verify":
        # Check if legacy split binary exists
        v_verify_release = vantage_base / "target" / "release" / "vantage-verify.exe"
        v_verify_debug = vantage_base / "target" / "debug" / "vantage-verify.exe"
        
        if v_verify_release.exists():
            run_args = [str(v_verify_release)] + args[1:]
        elif v_verify_debug.exists():
            run_args = [str(v_verify_debug)] + args[1:]
        else:
            # v1.2.4-LOCK: New unified binary handles 'verify' command directly
            run_args = [engine] + args
    else:
        # Standard engine command
        run_args = [engine] + args

    try:
        result = subprocess.run(run_args)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"[kit-vantage] Runtime error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
