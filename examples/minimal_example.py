#!/usr/bin/env python3
"""
Minimal example for memory_share_kit v1.2.4

This script demonstrates basic import and initialization of the kit API.
"""

from kit.api import resolve_paths

# Resolve paths to demonstrate functionality
global_db, project_db, local_db = resolve_paths()

print("Kit minimal example executed successfully.")
print(f"Global DB: {global_db}")
print(f"Project DB: {project_db}")
print(f"Local DB: {local_db}")