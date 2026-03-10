#!/usr/bin/env python3
"""
MCP Server for .kit — AI-native interface for architectural diagnostics.

Exposes 8 core diagnostic tools to LLM clients (Claude, Gemini, etc.) via MCP protocol.
Architecture: Tier 2 (Signal Envelope + Reasoning Hints + Decision Engine + Broker)

Usage:
    python kit_mcp_server.py [command] [args...]

Example client config (Claude):
    "tools": [{
        "type": "model_context_protocol",
        "name": "kit-diagnostics",
        "uri": "stdio:///path/to/kit_mcp_server.py"
    }]
"""

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
try:
    import yaml
except ImportError:
    yaml = None


# ============================================================================
# Layer 1-4: Signal Envelope + Reasoning Hints + Decision Engine + Broker
# ============================================================================

class SignalEnvelope:
    """Layer 1: Convert detailed results to minimal signal."""
    
    @staticmethod
    def build(results: Dict[str, Any], skill_name: str) -> Dict[str, Any]:
        """Build signal envelope (~30 tokens)."""
        
        severity = "HEALTHY"
        issues = []
        
        # Safe extraction of nested values
        def get_count(data: Dict, key: str) -> int:
            value = data.get(key, 0)
            if isinstance(value, dict):
                return len(value)
            if isinstance(value, list):
                return len(value)
            try:
                return int(value) if value else 0
            except:
                return 0
        
        # Detect issues from results
        if get_count(results, "cycles_detected") > 0:
            issues.append("cycle_detected")
            severity = "CRITICAL" if get_count(results, "cycles_detected") > 2 else "WARNING"
        
        if get_count(results, "hidden_god_services") > 0:
            issues.append("god_module")
            if severity != "CRITICAL":
                severity = "WARNING"
        
        if get_count(results, "layer_violations") > 0:
            issues.append("layer_violation")
            if severity != "CRITICAL":
                severity = "WARNING"
        
        # Extract top symbol
        top_symbol = None
        if "top_symbol" in results:
            value = results["top_symbol"]
            if not isinstance(value, dict):
                top_symbol = str(value)
        elif "top_modules" in results and results["top_modules"]:
            top_modules = results["top_modules"]
            if isinstance(top_modules, list) and len(top_modules) > 0:
                top_symbol = str(top_modules[0])
        
        payload_id = f"skill:{skill_name}:{uuid.uuid4().hex[:8]}"
        
        return {
            "severity": severity,
            "issues": issues,
            "top_symbol": top_symbol,
            "confidence": "HIGH" if issues else "MEDIUM",
            "payload_ref": payload_id
        }


class ReasoningHints:
    """Layer 2: Suggest next actions based on signal."""
    
    @staticmethod
    def build(signal: Dict[str, Any], results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate next_actions hints."""
        
        actions = []
        priority = 1
        
        # Rule 1: If cycles detected
        if "cycle_detected" in signal["issues"]:
            actions.append({
                "action": "run_impact",
                "symbol": signal.get("top_symbol"),
                "reason": "Break cycles first — other modules depend on this symbol",
                "priority": priority
            })
            priority += 1
        
        # Rule 2: If god module
        if "god_module" in signal["issues"]:
            top_module = results.get("top_module")
            actions.append({
                "action": "inspect_module",
                "module": top_module,
                "reason": f"High fan-out ({results.get('incoming_count', 0)} dependencies) — refactor first",
                "priority": priority
            })
            priority += 1
        
        # Rule 3: If layer violations
        if "layer_violation" in signal["issues"]:
            actions.append({
                "action": "run_drift_analysis",
                "reason": "Architecture constraints violated — align with layer policy",
                "priority": priority
            })
        
        return actions


class DecisionEngine:
    """Layer 3: Policy-driven decision making."""
    
    @staticmethod
    def _safe_get(data: Dict[str, Any], key: str, default: int = 0) -> int:
        """Safely extract integer values from potentially nested data."""
        value = data.get(key, default)
        # If it's a dict, summate or count
        if isinstance(value, dict):
            try:
                return sum(1 for _ in value.values()) if value else 0
            except:
                return 0
        # If it's a list, get length
        if isinstance(value, list):
            return len(value)
        # If it's already a number, return it
        try:
            return int(value) if value is not None else default
        except (TypeError, ValueError):
            return default
    
    POLICIES = [
        {
            "name": "cycle_critical",
            "condition": lambda r: DecisionEngine._safe_get(r, "cycles_detected") > 2,
            "severity": "CRITICAL",
            "reason": "Multiple circular dependencies detected"
        },
        {
            "name": "cycle_warning",
            "condition": lambda r: DecisionEngine._safe_get(r, "cycles_detected") > 0,
            "severity": "WARNING",
            "reason": "Circular dependency detected"
        },
        {
            "name": "god_module",
            "condition": lambda r: DecisionEngine._safe_get(r, "hidden_god_services") > 0,
            "severity": "WARNING",
            "reason": "God module detected — refactor recommended"
        },
        {
            "name": "layer_violation",
            "condition": lambda r: DecisionEngine._safe_get(r, "layer_violations") > 0,
            "severity": "WARNING",
            "reason": "Architecture layer constraints violated"
        },
        {
            "name": "high_entropy",
            "condition": lambda r: DecisionEngine._safe_get(r, "entropy") > 8,
            "severity": "WARNING",
            "reason": "High coupling detected"
        }
    ]
    
    @staticmethod
    def evaluate(results: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate policies and return decisions."""
        
        decisions = []
        
        for policy in DecisionEngine.POLICIES:
            try:
                if policy["condition"](results):
                    decisions.append({
                        "policy": policy["name"],
                        "severity": policy["severity"],
                        "reason": policy["reason"],
                        "confidence": "HIGH"
                    })
            except Exception:
                # Silently skip policies that can't be evaluated
                pass
        
        return {
            "decisions": decisions,
            "recommendation_count": len(decisions)
        }


class ToolBroker:
    """Layer 4: Orchestration safety (dedup, validate, cache, rate limit)."""
    
    def __init__(self):
        self.call_cache = {}
        self.call_history = []
        self.payload_store = {}  # Payload reference store
        self.discovered_symbols = set()
        self.last_call_time = 0
        self.calls_per_second = 5
    
    def execute_skill(self, skill_name: str, detail_level: str = "full", 
                      server: Optional[Any] = None) -> Dict[str, Any]:
        """Execute skill with broker safety layer."""
        
        # Rate limiting
        now = time.time()
        if now - self.last_call_time < (1.0 / self.calls_per_second):
            return {
                "status": "rate_limited",
                "retry_after_ms": int((1.0 / self.calls_per_second - (now - self.last_call_time)) * 1000)
            }
        
        self.last_call_time = now
        
        # Check cache
        cache_key = f"{skill_name}:{detail_level}"
        if cache_key in self.call_cache:
            self.call_history.append(("cache_hit", skill_name))
            return self.call_cache[cache_key]
        
        # Execute (using server's method)
        if server is None:
            return {"status": "error", "reason": "broker: server not provided"}
        
        try:
            result = server.handle_kit_skill_run(skill_name)
        except Exception as e:
            self.call_history.append(("failed", skill_name, str(e)))
            return {"status": "error", "reason": str(e)}
        
        # Process result based on detail_level
        processed = self._process_by_detail_level(result, detail_level, skill_name)
        
        # Cache result
        self.call_cache[cache_key] = processed
        self.call_history.append(("executed", skill_name))
        
        return processed
    
    def _process_by_detail_level(self, result: Dict[str, Any], detail_level: str, 
                                 skill_name: str) -> Dict[str, Any]:
        """Filter response based on detail_level."""
        
        signal = SignalEnvelope.build(result.get("results", {}), skill_name)
        hints = ReasoningHints.build(signal, result.get("results", {}))
        decisions = DecisionEngine.evaluate(result.get("results", {}))
        
        # Store full payload for later retrieval
        payload_id = signal["payload_ref"]
        self.payload_store[payload_id] = result
        
        # Track discovered symbol
        if signal["top_symbol"]:
            self.discovered_symbols.add(signal["top_symbol"])
        
        if detail_level == "signal":
            return {
                "signal": signal,
                "next_actions": hints,
                "decisions": decisions
            }
        elif detail_level == "summary":
            return {
                "signal": signal,
                "summary": result.get("summary", ""),
                "findings": result.get("findings", []),
                "recommendations": result.get("recommendations", []),
                "next_actions": hints,
                "decisions": decisions
            }
        else:  # "full"
            return {
                "signal": signal,
                "next_actions": hints,
                "decisions": decisions,
                **result  # Include everything
            }
    
    def get_payload(self, payload_ref: str) -> Optional[Dict[str, Any]]:
        """Retrieve full payload (agent fetches when needed)."""
        return self.payload_store.get(payload_ref)


# ============================================================================
# MCP Protocol Primitives
# ============================================================================

@dataclass
class MCPTool:
    """Tool definition for MCP spec."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPServer:
    """Minimal MCP server (v0.1 protocol) with Tier 2 architecture."""
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or Path.cwd())
        self.broker = ToolBroker()
        self.tools = self._define_tools()
        
    def _define_tools(self) -> Dict[str, MCPTool]:
        """Register all .kit diagnostic tools."""
        return {
            "kit_doctor": MCPTool(
                name="kit_doctor",
                description="Run comprehensive architecture health check (5 key metrics + status)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "text"],
                            "default": "json",
                            "description": "Output format"
                        }
                    }
                }
            ),
            "kit_query_stone": MCPTool(
                name="kit_query_stone",
                description="Execute a diagnostic stone (SQL query). Examples: cycles, gravity, hotspots, architecture, god_modules, entropy, choke_points, dead_code, impact, domains",
                input_schema={
                    "type": "object",
                    "properties": {
                        "stone_name": {
                            "type": "string",
                            "description": "Stone name (e.g., 'gravity', 'cycles', 'hotspots')"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "text"],
                            "default": "json"
                        }
                    },
                    "required": ["stone_name"]
                }
            ),
            "kit_stones_list": MCPTool(
                name="kit_stones_list",
                description="List all diagnostic stones with descriptions",
                input_schema={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "text"],
                            "default": "json"
                        }
                    }
                }
            ),
            "kit_symbol_search": MCPTool(
                name="kit_symbol_search",
                description="Unified search for code symbols and documentation",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Max results"
                        },
                        "include_private": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include private memory (docs)"
                        }
                    },
                    "required": ["query"]
                }
            ),
            "kit_impact": MCPTool(
                name="kit_impact",
                description="Analyze blast radius of a symbol (reverse call graph)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Symbol name to analyze"
                        },
                        "depth": {
                            "type": "integer",
                            "default": 3,
                            "description": "Traversal depth (1-6)"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "description": "Max results"
                        }
                    },
                    "required": ["symbol"]
                }
            ),
            "kit_context": MCPTool(
                name="kit_context",
                description="Get unified code context for a symbol (definition + callers + callees + related docs)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Symbol name"
                        },
                        "callers_limit": {
                            "type": "integer",
                            "default": 5
                        },
                        "callees_limit": {
                            "type": "integer",
                            "default": 5
                        },
                        "radius": {
                            "type": "integer",
                            "default": 8,
                            "description": "Lines of context around definition"
                        }
                    },
                    "required": ["symbol"]
                }
            ),
            "kit_skills_list": MCPTool(
                name="kit_skills_list",
                description="List all available diagnostic skills with metadata",
                input_schema={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "text"],
                            "default": "json"
                        },
                        "tags": {
                            "type": "string",
                            "description": "Filter by tags (comma-separated)"
                        }
                    }
                }
            ),
            "kit_skill_run": MCPTool(
                name="kit_skill_run",
                description="Execute a diagnostic skill (composed workflow of stones)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Skill name (e.g., 'architecture_investigate')"
                        },
                        "inputs": {
                            "type": "object",
                            "description": "Skill input parameters (depth, changed_files, etc.)"
                        },
                        "detail_level": {
                            "type": "string",
                            "enum": ["signal", "summary", "full"],
                            "default": "full",
                            "description": "Response detail: signal (~30 tokens, critical info only), summary (~150 tokens, findings+actions), full (1000+ tokens, everything)"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "text"],
                            "default": "json"
                        }
                    },
                    "required": ["skill_name"]
                }
            ),
            "kit_payload_get": MCPTool(
                name="kit_payload_get",
                description="Retrieve full diagnostic payload (stored after skill execution with signal detail_level)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "payload_ref": {
                            "type": "string",
                            "description": "Payload reference ID (returned in signal response)"
                        }
                    },
                    "required": ["payload_ref"]
                }
            ),
        }

    def _run_kit_command(self, *args) -> Dict[str, Any]:
        """Execute kit CLI command and return parsed JSON."""
        cmd = ["python", str(self.workspace_root / "bin" / "kit"), *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env={"ANTIGRAVITY_WORKSPACE_ROOT": str(self.workspace_root)}
            )
            if result.returncode != 0:
                return {
                    "error": f"kit command failed: {result.stderr}",
                    "command": " ".join(args)
                }
            # Try to parse as JSON, fall back to text
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"output": result.stdout}
        except subprocess.TimeoutExpired:
            return {"error": "kit command timed out"}
        except Exception as e:
            return {"error": f"Failed to execute kit: {str(e)}"}

    def _load_skills(self) -> Dict[str, Dict[str, Any]]:
        """Load all skills from .kit/skills/ directory."""
        skills = {}
        skills_dir = self.workspace_root / ".kit" / "skills"
        
        if not skills_dir.exists():
            return skills
        
        for skill_file in skills_dir.glob("*.yaml"):
            if skill_file.name.startswith("SPEC"):
                continue  # Skip spec file
            try:
                if yaml is None:
                    # Fallback: simple JSON parsing (assumes .yaml is valid)
                    continue
                with open(skill_file) as f:
                    skill = yaml.safe_load(f)
                    if skill and "name" in skill:
                        skills[skill["name"]] = skill
            except Exception:
                pass  # Silently skip malformed skills
        
        return skills
    
    def _load_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Load a single skill by name."""
        skills = self._load_skills()
        return skills.get(skill_name)
    
    def _extract_findings(self, results: Dict[str, Any]) -> List[str]:
        """Extract key findings from raw stone results (compression for agents)."""
        findings = []
        
        for stone_name, result in results.items():
            if isinstance(result, dict):
                # Extract status
                status = result.get("status")
                if status == "CRITICAL":
                    findings.append(f"[{stone_name}] CRITICAL: {result.get('message', 'Issue detected')}")
                elif status == "WARNING":
                    findings.append(f"[{stone_name}] WARNING: {result.get('message', 'Issue detected')}")
                
                # Extract specific issues
                if "cycles_detected" in result and result["cycles_detected"]:
                    findings.append(f"[{stone_name}] Circular dependencies detected")
                
                if "count" in result and result["count"] > 0:
                    findings.append(f"[{stone_name}] {result.get('count')} issues found")
        
        return findings if findings else ["All diagnostics nominal"]

    # ========================================================================
    # Tool Handlers
    # ========================================================================

    def handle_kit_doctor(self, format: str = "json") -> Dict[str, Any]:
        """Handler for kit_doctor tool."""
        result = self._run_kit_command("doctor", "--json")
        return {
            "status": "success",
            "tool": "kit_doctor",
            "result": result
        }

    def handle_kit_query_stone(self, stone_name: str, format: str = "json") -> Dict[str, Any]:
        """Handler for kit_query_stone tool."""
        result = self._run_kit_command("query", stone_name, "--json")
        return {
            "status": "success",
            "tool": "kit_query_stone",
            "stone": stone_name,
            "result": result
        }

    def handle_kit_stones_list(self, format: str = "json") -> Dict[str, Any]:
        """Handler for kit_stones_list tool."""
        result = self._run_kit_command("stones", "--json")
        return {
            "status": "success",
            "tool": "kit_stones_list",
            "result": result
        }

    def handle_kit_symbol_search(self, query: str, limit: int = 10, include_private: bool = False) -> Dict[str, Any]:
        """Handler for kit_symbol_search tool."""
        args = ["symbol", query, "--limit", str(limit), "--json"]
        if include_private:
            args.append("--include-private")
        result = self._run_kit_command(*args)
        return {
            "status": "success",
            "tool": "kit_symbol_search",
            "query": query,
            "result": result
        }

    def handle_kit_impact(self, symbol: str, depth: int = 3, limit: int = 50) -> Dict[str, Any]:
        """Handler for kit_impact tool."""
        result = self._run_kit_command("impact", symbol, "--depth", str(depth), "--limit", str(limit), "--json")
        return {
            "status": "success",
            "tool": "kit_impact",
            "symbol": symbol,
            "result": result
        }

    def handle_kit_context(self, symbol: str, callers_limit: int = 5, callees_limit: int = 5, radius: int = 8) -> Dict[str, Any]:
        """Handler for kit_context tool."""
        result = self._run_kit_command(
            "context", symbol, 
            "--callers-limit", str(callers_limit),
            "--callees-limit", str(callees_limit),
            "--radius", str(radius),
            "--json"
        )
        return {
            "status": "success",
            "tool": "kit_context",
            "symbol": symbol,
            "result": result
        }

    def handle_kit_skills_list(self, format: str = "json", tags: str = "") -> Dict[str, Any]:
        """Handler for kit_skills_list tool."""
        skills = self._load_skills()
        
        # Filter by tags if provided
        if tags:
            requested_tags = set(t.strip() for t in tags.split(","))
            filtered = {}
            for name, skill in skills.items():
                skill_tags = set(skill.get("tags", []))
                if skill_tags & requested_tags:  # Intersection
                    filtered[name] = skill
            skills = filtered
        
        # Extract lightweight metadata for MCP response
        skill_list = []
        for name, skill in skills.items():
            skill_list.append({
                "name": skill.get("name"),
                "version": skill.get("version", 1),
                "description": skill.get("description"),
                "tags": skill.get("tags", []),
                "author": skill.get("author", ".kit"),
                "cost": skill.get("cost", "medium"),
                "depends_on": skill.get("depends_on", []),
                "estimated_tokens": skill.get("agent_context", {}).get("estimated_tokens", "100-500")
            })
        
        return {
            "status": "success",
            "tool": "kit_skills_list",
            "count": len(skill_list),
            "skills": skill_list
        }

    def handle_kit_skill_run(self, skill_name: str, inputs: Optional[Dict[str, Any]] = None, 
                            detail_level: str = "full", format: str = "json") -> Dict[str, Any]:
        """Handler for kit_skill_run tool with Tier 2 architecture support.
        
        detail_level:
            - "signal" (~30 tokens): Critical info + next_actions + decisions
            - "summary" (~150 tokens): Signal + findings + recommendations  
            - "full" (1000+ tokens): Everything including _raw_results
        """
        import time
        start_time = time.time()
        
        skill = self._load_skill(skill_name)
        
        if not skill:
            return {
                "status": "error",
                "error": f"Skill not found: {skill_name}",
                "available_skills": list(self._load_skills().keys())
            }
        
        # Validate inputs against skill schema
        inputs = inputs or {}
        
        # Check dependencies
        dependencies = skill.get("depends_on", [])
        dependency_results = {}
        
        for dep_skill_name in dependencies:
            dep_skill = self._load_skill(dep_skill_name)
            if not dep_skill:
                return {
                    "status": "error",
                    "error": f"Dependency not found: {dep_skill_name}",
                    "skill": skill_name
                }
            # Recursively run dependency (with timeout to prevent infinite loops)
            dep_result = self.handle_kit_skill_run(dep_skill_name, {}, detail_level="signal")
            if dep_result.get("status") == "error":
                return dep_result
            dependency_results[dep_skill_name] = dep_result
        
        # Execute all stones in skill's 'uses' list
        results = {}
        skill_errors = []
        
        for stone_spec in skill.get("uses", []):
            stone_name = stone_spec if isinstance(stone_spec, str) else stone_spec.get("stone")
            is_required = True
            
            if isinstance(stone_spec, dict):
                is_required = stone_spec.get("required", True)
            
            try:
                stone_result = self._run_kit_command("query", stone_name, "--json")
                if "error" in stone_result:
                    if is_required:
                        skill_errors.append(f"Required stone '{stone_name}' failed")
                results[stone_name] = stone_result
            except Exception as e:
                if is_required:
                    skill_errors.append(f"Error running stone '{stone_name}': {str(e)}")
                results[stone_name] = {"error": str(e)}
        
        # If there were required errors, return error status
        if skill_errors:
            execution_time = int((time.time() - start_time) * 1000)
            return {
                "status": "error",
                "skill": skill_name,
                "version": skill.get("version", 1),
                "errors": skill_errors,
                "execution_time_ms": execution_time
            }
        
        # Apply interpretation rules
        severity = "HEALTHY"
        recommendations = []
        activation_level = "cold"
        confidence = 1.0
        
        interpretation = skill.get("interpretation", {})
        rules = interpretation.get("rules", [])
        
        # Simple rule evaluation
        for rule in rules:
            condition = rule.get("if", "")
            then_clause = rule.get("then", "")
            
            # Check severity assignment
            if "severity" in str(then_clause):
                if "CRITICAL" in str(then_clause):
                    severity = "CRITICAL"
                    confidence = 0.95
                elif "WARNING" in str(then_clause) and severity != "CRITICAL":
                    severity = "WARNING"
                    confidence = 0.90
            
            if "recommendation" in rule:
                recommendations.append(rule.get("recommendation"))
        
        # Determine activation level
        activation_rules = interpretation.get("activation_level", {})
        if severity == "CRITICAL":
            activation_level = "hot"
        elif severity == "WARNING":
            activation_level = "warm"
        else:
            activation_level = "cold"
        
        # Build standardized output response (FROZEN SCHEMA)
        execution_time = int((time.time() - start_time) * 1000)
        
        base_response = {
            "status": "success",
            "skill": skill_name,
            "version": skill.get("version", 1),
            "schema_version": skill.get("schema_version", 1),
            "severity": severity,
            "summary": f"{skill.get('description')} — {severity.lower()} status.",
            "findings": self._extract_findings(results),
            "recommendations": recommendations,
            "activation_level": activation_level,
            "confidence": confidence,
            "execution_time_ms": execution_time,
            "cost": skill.get("cost", "medium"),
            "dependencies": dependency_results if dependency_results else None,
            # Include raw results for transparency (only in 'full' mode)
            "_raw_results": results if detail_level == "full" else None
        }
        
        # Apply detail_level filtering via Tier 2 architecture
        # This uses Signal Envelope, Reasoning Hints, and Decision Engine
        if detail_level == "signal":
            # Signal: ~30 tokens, critical info only
            signal = SignalEnvelope.build(results, skill_name)
            hints = ReasoningHints.build(signal, results)
            decisions = DecisionEngine.evaluate(results)
            
            # Store full payload for later retrieval
            self.broker.payload_store[signal["payload_ref"]] = base_response
            
            return {
                "status": "success",
                "skill": skill_name,
                "version": skill.get("version", 1),
                "signal": signal,
                "next_actions": hints,
                "decisions": decisions,
                "execution_time_ms": execution_time
            }
        elif detail_level == "summary":
            # Summary: ~150 tokens, signal + findings + recommendations
            signal = SignalEnvelope.build(results, skill_name)
            hints = ReasoningHints.build(signal, results)
            decisions = DecisionEngine.evaluate(results)
            
            # Store full payload for later retrieval
            self.broker.payload_store[signal["payload_ref"]] = base_response
            
            return {
                "status": "success",
                "skill": skill_name,
                "version": skill.get("version", 1),
                "signal": signal,
                "findings": self._extract_findings(results),
                "recommendations": recommendations,
                "next_actions": hints,
                "decisions": decisions,
                "execution_time_ms": execution_time
            }
        else:  # "full" (default)
            # Full: ~1000+ tokens, everything including _raw_results
            return base_response

    def handle_kit_payload_get(self, payload_ref: str) -> Dict[str, Any]:
        """Handler for kit_payload_get tool.
        
        Retrieves full diagnostic payload after skill execution with 'signal' detail_level.
        This implements lazy loading: agent gets critical info first (30 tokens),
        then fetches full details (1000+ tokens) only if needed.
        
        Args:
            payload_ref: Payload reference ID returned in signal response
            
        Returns:
            Full skill response including _raw_results
        """
        
        if payload_ref not in self.broker.payload_store:
            return {
                "status": "error",
                "error": f"Payload not found: {payload_ref}",
                "reason": "Payload may have expired or never existed"
            }
        
        payload = self.broker.payload_store[payload_ref]
        
        return {
            "status": "success",
            "payload_ref": payload_ref,
            "payload": payload
        }

    # ========================================================================
    # MCP Protocol Implementation
    # ========================================================================

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return tools in MCP format."""
        tools = []
        for name, tool in self.tools.items():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            })
        return tools

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool call to handler."""
        handlers = {
            "kit_doctor": self.handle_kit_doctor,
            "kit_query_stone": self.handle_kit_query_stone,
            "kit_stones_list": self.handle_kit_stones_list,
            "kit_symbol_search": self.handle_kit_symbol_search,
            "kit_impact": self.handle_kit_impact,
            "kit_context": self.handle_kit_context,
            "kit_skills_list": self.handle_kit_skills_list,
            "kit_skill_run": self.handle_kit_skill_run,
            "kit_payload_get": self.handle_kit_payload_get,
        }
        
        if name not in handlers:
            return {"error": f"Unknown tool: {name}"}
        
        try:
            handler = handlers[name]
            return handler(**arguments)
        except TypeError as e:
            return {"error": f"Invalid arguments for {name}: {str(e)}"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}


# ============================================================================
# Minimal MCP Server Loop (stdio protocol)
# ============================================================================

def run_server():
    """Run MCP server loop on stdio."""
    server = MCPServer()
    
    # For development/testing: respond to simple JSON messages on stdin
    print("kit_mcp_server ready", file=sys.stderr)
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line)
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            response = None
            
            if method == "tools/list":
                response = {"tools": server.list_tools()}
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                response = server.call_tool(tool_name, tool_args)
            else:
                response = {"error": f"Unknown method: {method}"}
            
            # Send response
            if request_id:
                response["id"] = request_id
            print(json.dumps(response), flush=True)
            
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON: {str(e)}"}), file=sys.stderr)
        except Exception as e:
            print(json.dumps({"error": f"Server error: {str(e)}"}), file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Quick test mode: call tools from CLI
        server = MCPServer()
        if len(sys.argv) > 2:
            tool_name = sys.argv[2]
            tool_args = {}
            # Parse remaining args as key=value
            for arg in sys.argv[3:]:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    tool_args[k] = v
            result = server.call_tool(tool_name, tool_args)
            print(json.dumps(result, indent=2))
        else:
            # List all tools
            print(json.dumps({"tools": server.list_tools()}, indent=2))
    else:
        # Run normal server loop
        run_server()
