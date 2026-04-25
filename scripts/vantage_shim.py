import subprocess
import sys
from pathlib import Path


def main():
    # AMSB v1.2.4 - The Vantage Protocol Shim (Robust)
    # Delegates 'kit vantage ...' to the Vantage CLI binary
    
    cwd = Path.cwd()
    repo_root = None
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            repo_root = parent
            break
            
    # Try sibling repo first
    vantage_base = repo_root.parent / "Vantage" if repo_root else Path("../../Vantage")
    
    # Candidates for the real binary
    candidates = [
        vantage_base / "kit-vantage.exe",
        vantage_base / "kit-vantage",
        vantage_base / "target" / "release" / "vantage.exe",
        vantage_base / "target" / "release" / "vantage",
        Path("kit-vantage.exe"), # Root of current repo
        Path("kit-vantage"),
    ]
    
    engine = None
    for cand in candidates:
        if cand.exists() and cand.is_file():
            engine = str(cand)
            break
            
    if not engine:
        import shutil
        resolved = shutil.which("vantage") or shutil.which("kit-vantage")
        if resolved:
            engine = resolved
            
    args = sys.argv[1:]
    
    if not engine:
        print("\n❌ Vantage runtime not found.")
        print("\nVantage is required for structural verification and integrity enforcement.")
        print("\nInstall Vantage:")
        print("  Windows: winget install vantage")
        print("  Mac:     brew install vantage")
        print("  Linux:   cargo install vantage-cli")
        print("\nDocs: https://github.com/so-sai/Vantage")
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
