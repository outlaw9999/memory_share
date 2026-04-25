import sqlite3
import shutil
import os
import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import Field
from kit.skills.base import BaseSkill, SkillInput, SkillOutput
from kit.skills.registry import register_skill

logger = logging.getLogger("kit.skills.migrate")

class BrainMigrationInput(SkillInput):
    """Parameters for brain migration."""
    old_db_path: str = Field(..., description="Path to the legacy brain.db")
    new_db_path: str = Field(..., description="Path to the current titanium brain.db (template/target)")
    output_db_path: str = Field(..., description="Path where the merged database will be written")

@register_skill
class BrainMigrationSkill(BaseSkill[BrainMigrationInput]):
    """
    Cognitive Migration Skill (CMS).
    Bridges legacy memory schemas into Titanium (v1.2.4) deterministic structure.
    """
    name = "migrate_brain"
    version = "1.2.4"
    input_model = BrainMigrationInput

    def run(self, input_data: BrainMigrationInput, context: list = None) -> SkillOutput:
        """Execute the migration logic."""
        try:
            migrate_and_merge(
                input_data.old_db_path,
                input_data.new_db_path,
                input_data.output_db_path
            )
            return SkillOutput(
                status="SUCCESS",
                results={"message": f"Successfully migrated {input_data.old_db_path} to {input_data.output_db_path}"}
            )
        except Exception as e:
            return SkillOutput(status="FAILED", results={"error": str(e)})

def migrate_and_merge(old_db_path, new_db_path, output_db_path):
    print(f"Starting Migration: {old_db_path} -> {new_db_path}")
    
    # 1. Backups
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for db in [old_db_path, new_db_path]:
        if os.path.exists(db):
            shutil.copy2(db, f"{db}.{timestamp}.bak")
            print(f"Backup created: {db}.{timestamp}.bak")

    # 2. Setup output database (start with a copy of the new schema)
    if os.path.exists(output_db_path):
        os.remove(output_db_path)
    shutil.copy2(new_db_path, output_db_path)
    print(f"Output target initialized: {output_db_path}")

    target_conn = sqlite3.connect(output_db_path)
    source_conn = sqlite3.connect(old_db_path)
    
    target_conn.row_factory = sqlite3.Row
    source_conn.row_factory = sqlite3.Row

    try:
        # Get schemas
        target_cols = [row[1] for row in target_conn.execute("PRAGMA table_info(observations)").fetchall()]
        source_cols = [row[1] for row in source_conn.execute("PRAGMA table_info(observations)").fetchall()]
        
        print(f"Schema Sense: Target has {len(target_cols)} columns, Source has {len(source_cols)} columns.")

        # Read all from source
        source_records = source_conn.execute("SELECT * FROM observations").fetchall()
        print(f"Found {len(source_records)} records in source.")

        # Read existing structural hashes in target for deduplication
        target_hashes = set()
        if "structural_hash" in target_cols:
            rows = target_conn.execute("SELECT structural_hash FROM observations").fetchall()
            target_hashes = {row['structural_hash'] for row in rows if row['structural_hash']}
        
        # Alternative dedupe: content + symbol
        target_keys = set()
        rows = target_conn.execute("SELECT content, symbol FROM observations").fetchall()
        for row in rows:
            target_keys.add((row['content'], row['symbol']))

        new_inserts = 0
        skipped = 0

        for record in source_records:
            # Check for duplicates
            if record['structural_hash'] and record['structural_hash'] in target_hashes:
                skipped += 1
                continue
            
            if (record['content'], record['symbol']) in target_keys:
                skipped += 1
                continue

            # Map fields
            new_data = {}
            for col in target_cols:
                if col in source_cols:
                    new_data[col] = record[col]
                else:
                    # Default values for Titanium schema
                    if col == 'is_baked': new_data[col] = 1
                    elif col == 'is_active': new_data[col] = 1
                    elif col == 'is_canonical': new_data[col] = 0
                    elif col == 'symbol_locked': new_data[col] = 0
                    elif col == 'symbol_confidence': new_data[col] = 1.0
                    elif col == 'symbol_source': new_data[col] = 'migration'
                    elif col == 'id': new_data[col] = None # Let SQLite auto-increment
                    else: new_data[col] = None

            # Insert
            if 'id' in new_data:
                del new_data['id']
            cols_str = ", ".join(new_data.keys())
            placeholders = ", ".join(["?"] * len(new_data))
            target_conn.execute(f"INSERT INTO observations ({cols_str}) VALUES ({placeholders})", list(new_data.values()))
            new_inserts += 1

        target_conn.commit()
        print(f"Migration Complete: {new_inserts} new records merged, {skipped} duplicates skipped.")
        
        # Verify count
        final_count = target_conn.execute("SELECT count(*) FROM observations").fetchone()[0]
        print(f"Final Record Count: {final_count}")

    except Exception as e:
        target_conn.rollback()
        print(f"Error during migration: {e}")
        raise

    finally:
        source_conn.close()
        target_conn.close()

if __name__ == "__main__":
    old_db = ".kit/brain.db"
    new_db = ".kit/local_brain.db"
    merged_db = ".kit/brain_merged.db"
    
    migrate_and_merge(old_db, new_db, merged_db)
