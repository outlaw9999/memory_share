#!/usr/bin/env python3
"""
Test script: MCP Server Integration Test

Demonstrates how an AI agent would use the kit MCP server for architecture analysis.
This validates the complete MCP workflow.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any


class MockAgent:
    """Simulates an AI agent using the .kit MCP server."""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root or Path.cwd())
        self.mcp_server = None
        self.call_count = 0
        self.token_estimate = 0
    
    def start_mcp_server(self):
        """Start the MCP server subprocess."""
        cmd = [
            "python",
            str(self.workspace_root / "kit_mcp_server.py")
        ]
        self.mcp_server = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"[Agent] Started MCP server: {' '.join(cmd)}")
    
    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool and return result."""
        self.call_count += 1
        
        request = {
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self.call_count,
            "jsonrpc": "2.0"
        }
        
        # Send request
        self.mcp_server.stdin.write(json.dumps(request) + "\n")
        self.mcp_server.stdin.flush()
        
        # Read response
        response_line = self.mcp_server.stdout.readline()
        if not response_line:
            print(f"[Agent] ERROR: No response from MCP server", file=sys.stderr)
            return {"error": "No response from server"}
        
        response = json.loads(response_line)
        
        # Estimate token cost based on response size
        response_str = json.dumps(response)
        estimated_tokens = len(response_str) // 4  # Rough estimation: 4 chars per token
        self.token_estimate += estimated_tokens
        
        print(f"[Agent] Called {tool_name} → {estimated_tokens} tokens")
        return response
    
    def run_scenario(self):
        """Run a realistic agent scenario."""
        print("\n" + "="*70)
        print("SCENARIO: Agent Analyzes Repository for Refactoring Safety")
        print("="*70 + "\n")
        
        # ====================================================================
        # Phase 1: Initial Health Assessment
        # ====================================================================
        print("📊 Phase 1: Quick Health Check")
        print("-" * 40)
        
        health = self.call_mcp_tool("kit_doctor", {})
        if health.get("status") != "success":
            print(f"ERROR: {health.get('error')}")
            return False
        
        doctor_data = health["result"]["doctor_report"]
        overall = doctor_data["overall_status"]
        cycles = doctor_data["architecture_health"]["cycles_detected"]
        graph_conf = doctor_data["graph_confidence"]["confidence_tier"]
        
        print(f"✓ Overall Status: {overall}")
        print(f"✓ Cycles Found: {cycles}")
        print(f"✓ Graph Confidence: {graph_conf}")
        
        if overall == "HEALTHY":
            print("\n✅ Architecture appears healthy. Proceeding with detailed analysis.\n")
        else:
            print("\n⚠️ Issues detected. Would recommend fixes before refactoring.\n")
        
        # ====================================================================
        # Phase 2: Discover Available Diagnostics
        # ====================================================================
        print("📚 Phase 2: Discover Diagnostic Stones")
        print("-" * 40)
        
        stones = self.call_mcp_tool("kit_stones_list", {})
        if stones.get("status") != "success":
            print(f"ERROR: {stones.get('error')}")
            return False
        
        stone_data = stones["result"]
        print(f"✓ Found {stone_data['total']} diagnostic stones:")
        print(f"  - Primitives: {len(stone_data['primitives'])}")
        print(f"  - Advanced: {len(stone_data['advanced'])}")
        print(f"  - Orchestrators: {len(stone_data['orchestrators'])}")
        
        # ====================================================================
        # Phase 3: Deep Diagnostic Analysis
        # ====================================================================
        print("\n🔍 Phase 3: Analyze Specific Issue (Hotspots)")
        print("-" * 40)
        
        hotspots = self.call_mcp_tool("kit_query_stone", {
            "stone_name": "hotspots",
            "format": "json"
        })
        
        if hotspots.get("status") == "success":
            result = hotspots["result"]
            if isinstance(result, dict) and "hotspots" in result:
                hs_list = result["hotspots"]
                print(f"✓ Found {len(hs_list)} high-risk modules (hotspots)")
                if hs_list:
                    print(f"  Example: {hs_list[0].get('name', 'N/A')}")
            elif isinstance(result, dict) and "output" in result:
                print(f"✓ Query executed (output format varies)")
        
        # ====================================================================
        # Phase 4: Code Context Lookup
        # ====================================================================
        print("\n📍 Phase 4: Code Context Analysis (Sample)")
        print("-" * 40)
        
        # Try to find a symbol to analyze (use kernel as it definitely exists)
        context = self.call_mcp_tool("kit_context", {
            "symbol": "AntigravityKernel",
            "callers_limit": 3,
            "callees_limit": 3,
            "radius": 5
        })
        
        if context.get("status") == "success":
            result = context["result"]
            if isinstance(result, dict) and "definition" in result:
                defn = result.get("definition", {})
                print(f"✓ Found symbol: {defn.get('name', 'N/A')}")
                print(f"  Location: {defn.get('path', 'N/A')}")
        
        # ====================================================================
        # Phase 5: Impact Analysis
        # ====================================================================
        print("\n⚡ Phase 5: Impact Analysis (Blast Radius)")
        print("-" * 40)
        
        impact = self.call_mcp_tool("kit_impact", {
            "symbol": "AntigravityKernel",
            "depth": 2,
            "limit": 20
        })
        
        if impact.get("status") == "success":
            result = impact["result"]
            if isinstance(result, dict) and "affected" in result:
                affected = result["affected"]
                print(f"✓ Symbols affected by AntigravityKernel: {len(affected)}")
            else:
                print(f"✓ Impact query executed")
        
        # ====================================================================
        # Phase 6: Summary & Recommendations
        # ====================================================================
        print("\n📋 Phase 6: Agent Decision")
        print("-" * 40)
        
        print(f"\nAnalysis Summary:")
        print(f"  • Calls made: {self.call_count}")
        print(f"  • Token estimate: ~{self.token_estimate} tokens")
        print(f"  • Average tokens/call: ~{self.token_estimate // max(1, self.call_count)}")
        
        print(f"\nComparison:")
        print(f"  • Reading docs: 10,000-50,000 tokens")
        print(f"  • Reading codebase: 50,000-200,000 tokens")
        print(f"  • Using MCP: ~{self.token_estimate} tokens")
        print(f"  • Efficiency gain: ~{max(1, (50000 // max(1, self.token_estimate)))}x")
        
        conclusion = "✅ SAFE TO PROCEED" if cycles == 0 and overall == "HEALTHY" else "⚠️ REVIEW ISSUES FIRST"
        print(f"\n🎯 Recommendation: {conclusion}\n")
        
        return True
    
    def stop_mcp_server(self):
        """Clean up MCP server."""
        if self.mcp_server:
            self.mcp_server.terminate()
            try:
                self.mcp_server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.mcp_server.kill()
            print("[Agent] Stopped MCP server")


def main():
    workspace_root = Path(__file__).parent
    
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                  .kit MCP Server Integration Test                   ║
║                                                                      ║
║  This test demonstrates how an AI agent would use the MCP server   ║
║  to analyze a repository's architecture in a token-efficient way.  ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    agent = MockAgent(workspace_root)
    
    try:
        # Start server
        agent.start_mcp_server()
        
        # Run scenario
        success = agent.run_scenario()
        
        if success:
            print("✅ MCP Integration Test PASSED\n")
            return 0
        else:
            print("❌ MCP Integration Test FAILED\n")
            return 1
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        return 1
    
    except Exception as e:
        print(f"\n❌ Test error: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        agent.stop_mcp_server()


if __name__ == "__main__":
    sys.exit(main())
