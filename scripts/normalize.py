import json
import subprocess
import os
import sqlite3
from kit.api import learn, get_brain

# Target: v1.2.4 Normalization Script
# Preserves Historical Integrity via Audit Overlays

def main():
    # Step 1: Run canonical audit to get backlog
    audit_script = os.path.join('scripts', 'audit.py')
    res = subprocess.run([sys.executable, audit_script], capture_output=True, text=True, encoding='utf-8')
    if res.returncode != 0:
        print(f"Audit failed: {res.stderr}")
        return

    try:
        report = json.loads(res.stdout)
    except Exception as e:
        print(f"Failed to parse audit output: {e}")
        return

    backlog = report.get('friction_backlog', [])
    print(f"Backlog size: {len(backlog)}")

    # Step 2: Define Taxonomy Mapping
    def classify(content):
        content_lc = content.lower()
        if 'python' in content_lc or 'venv' in content_lc or 'yaml' in content_lc:
            return 'ENVIRONMENT', 'CRITICAL'
        if 'recursion' in content_lc or 'executor' in content_lc:
            return 'EXECUTION', 'CRITICAL'
        if 'duplicate' in content_lc or 'sprawl' in content_lc:
            return 'SKILL', 'HIGH'
        if 'search' in content_lc or 'timestamp' in content_lc:
            return 'SEARCH', 'HIGH'
        return 'MEMORY', 'MED'

    # Step 3: Create Overlays
    count = 0
    for item in backlog:
        # Check if audit already exists
        brain = get_brain()
        with brain.get_connection() as conn:
            # We look for an audit record that relates to this ID
            exists = conn.execute('SELECT 1 FROM observations WHERE tag = ? AND content LIKE ?', 
                                 ('audit', f'%"relates_to": {item["id"]}%')).fetchone()
            if exists:
                continue
        
        domain, severity = classify(item['content'])
        
        audit_data = {
            'relates_to': item['id'],
            'domain': domain,
            'severity': severity,
            'resolution_status': 'unresolved',
            'root_cause': 'Legacy v1.2.3 debt'
        }
        
        print(f"Creating audit for ID {item['id']} ({domain}, {severity})")
        
        learn(
            content=json.dumps(audit_data),
            tag='decision',
            kind='observation',
            uid=f'audit_{item["id"]}_{item["source"]}',
            layer='episodic'
        )
        count += 1
    
    print(f"Created {count} new Audit Overlay records.")

if __name__ == "__main__":
    import sys
    main()
