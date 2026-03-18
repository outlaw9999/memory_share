import sys
import os

# Add the current directory to sys.path to ensure kit_agent is importable
sys.path.append(os.getcwd())

from kit_agent.cli.main import main

if __name__ == "__main__":
    main()
