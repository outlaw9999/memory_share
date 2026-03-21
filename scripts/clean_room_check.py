# scripts/clean_room_check.py
# v1.2.3 Production Gatekeeper: Clean Room Reproducibility Audit

import os
import sys
import shutil
import tempfile
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class AuditReport:
    step: str
    status: bool
    error: str | None = None

class CleanRoomAuditor:
    def __init__(self) -> None:
        self.root: Path = Path(__file__).parent.parent.resolve()
        self.sandbox: Path = Path(tempfile.gettempdir()) / f"kit_clean_room_{os.getpid()}_{int(time.time())}"
        self.python: str = sys.executable
        
        # --- ISOLATION PARAMETERS ---
        # Inherit base env (USERPROFILE, HOMEDRIVE, etc.) but override isolation keys
        self.env: dict[str, str] = os.environ.copy()
        self.env.update({
            "PYTHONPATH": str(self.sandbox),
            "KIT_HOME": str(self.sandbox / ".kit_home"),
            "PYTHONUTF8": "1"
        })

    def _run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.python, "-m", "kit.cli.main"] + args,
            capture_output=True, 
            text=True, 
            cwd=cwd, 
            env=self.env, 
            timeout=10.0
        )

    def execute_audit(self) -> None:
        print("--- CLEAN ROOM REPRODUCIBILITY AUDIT (v1.2.3 FINAL GATE) ---")
        print("-" * 60)

        try:
            print("Step 1: Syncing clean source...", end=" ", flush=True)
            if self.sandbox.exists(): 
                shutil.rmtree(self.sandbox, ignore_errors=True)
            self.sandbox.mkdir(parents=True)
            
            for item in ["kit"]:
                src = self.root / item
                if src.is_dir():
                    shutil.copytree(src, self.sandbox / item)
                elif src.is_file():
                    shutil.copy2(src, self.sandbox / item)
            print("DONE")

            print("Step 2: Isolated Init...", end=" ", flush=True)
            res_init = self._run(["--isolated", "init"], cwd=self.sandbox)
            if res_init.returncode != 0:
                raise RuntimeError(f"Init Failed:\nSTDOUT: {res_init.stdout}\nSTDERR: {res_init.stderr}")
            
            if not (self.sandbox / ".kit" / "brain.db").exists():
                raise RuntimeError("Invariant Violation: brain.db not found in Sandbox!")
            print("PASS")

            print("Step 3: Cold Start Ingestion...", end=" ", flush=True)
            learn_payload = "OBSERVATION: This is a sterile test fact."
            # We don't use --auto here to ensure strictly LOCAL ingestion for isolation testing
            res_learn = self._run(["learn", "--content", learn_payload, "--importance", "0.5"], cwd=self.sandbox)
            
            output_combined = res_learn.stdout + res_learn.stderr
            if res_learn.returncode != 0 or "Learned" not in output_combined:
                raise RuntimeError(f"Learn Failed:\nSTDOUT: {res_learn.stdout}\nSTDERR: {res_learn.stderr}")
            print("PASS")

            print("Step 4: Consistency Recall...", end=" ", flush=True)
            # Query for 'sterile' to find the fact learned in Step 3
            res_recall = self._run(["recall", "sterile"], cwd=self.sandbox)
            if "sterile test fact" not in res_recall.stdout:
                raise RuntimeError(f"Data loss detected! Output:\n{res_recall.stdout}")
            print("PASS")

            print("Step 5: Hygiene Audit...", end=" ", flush=True)
            forbidden_extensions = [".db-wal", ".db-shm", ".log"]
            leakage = []
            for root, dirs, files in os.walk(self.sandbox):
                for f in files:
                    if any(f.endswith(ext) for ext in forbidden_extensions):
                        # Expected paths: .kit/ and .kit_home/
                        rel_path = Path(os.path.join(root, f)).relative_to(self.sandbox)
                        if not (str(rel_path).startswith(".kit") or str(rel_path).startswith(".kit_home")):
                            leakage.append(str(rel_path))
            
            if leakage:
                raise RuntimeError(f"Artifact leakage detected in Sandbox: {leakage}")
            print("PASS")

            print("-" * 60)
            print("FINAL RESULT: v1.2.3 MET PACKAGING STANDARDS!")
            print(f"Sandbox: {self.sandbox}")

        except Exception as e:
            print(f"\nAUDIT FAILED: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            pass

if __name__ == "__main__":
    CleanRoomAuditor().execute_audit()
