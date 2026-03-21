import sys
import os
from pathlib import Path
# Force local kit to be first in path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import time
import subprocess
import unittest
from unittest.mock import patch
from kit.api import reflect_check

class TestPhase1Resilience(unittest.TestCase):
    @patch("subprocess.check_output")
    def test_reflect_check_timeout(self, mock_git):
        # Mock git diff to sleep for 10 seconds (exceeding 3s timeout)
        def slow_git(*args, **kwargs):
            time.sleep(10)
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 3.0))
        
        mock_git.side_effect = slow_git
        
        start_time = time.time()
        # reflect_check should return within ~3 seconds
        result = reflect_check()
        duration = time.time() - start_time
        
        print(f"\n[PHASE 1] reflect_check duration with hanging git: {duration:.2f}s")
        
        # Verify it returns a valid (empty) result instead of crashing
        self.assertIn("issues", result)
        self.assertEqual(result["issues"], [])
        self.assertLess(duration, 5.0, "reflect_check took too long! Timeout failed.")

    @patch("subprocess.check_output")
    def test_reflect_check_error_degradation(self, mock_git):
        # Mock git diff to fail with non-zero exit code
        mock_git.side_effect = subprocess.CalledProcessError(1, "git diff")
        
        result = reflect_check()
        
        # Verify it degrades gracefully to empty issues
        self.assertIn("issues", result)
        self.assertEqual(result["issues"], [])

if __name__ == "__main__":
    unittest.main()
