import json
from typing import Dict, Any

class ReportGenerator:
    """
    Utility helper that formats the full StateGraph workflow output into
    standardized JSON dictionaries and markdown files.
    """

    @staticmethod
    def to_json(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a structured JSON dictionary including plan reasoning,
        agent summaries, verification notes, and final recommendations for API responses.
        """
        plan = state.get("plan") or {}
        agent_outputs = state.get("agent_outputs") or {}
        reasoning = state.get("reasoning") or {}
        verification = state.get("verification") or {}
        recommendation = state.get("recommendation") or {}

        return {
            "query": state.get("query", ""),
            "symbol": state.get("symbol", ""),
            "correlation_id": state.get("correlation_id", ""),
            "plan": {
                "selected_agents": plan.get("selected_agents", []),
                "reasoning": plan.get("reasoning", "")
            },
            "agent_summaries": {
                name: summary for name, summary in agent_outputs.items() if summary
            },
            "reasoning_synthesis": {
                "synthesis": reasoning.get("synthesis", ""),
                "supporting_evidence": reasoning.get("supporting_evidence", []),
                "conflicts_noted": reasoning.get("conflicts_noted", [])
            },
            "verifier_audit": {
                "is_supported": verification.get("is_supported", True),
                "confidence_adjustment": verification.get("confidence_adjustment", 0.0),
                "notes": verification.get("notes", "")
            },
            "recommendation": {
                "action": recommendation.get("action", "hold"),
                "confidence": recommendation.get("confidence", 0.0),
                "supporting_evidence": recommendation.get("supporting_evidence", []),
                "risks": recommendation.get("risks", [])
            },
            "report_status": state.get("report", {}).get("status", "unknown")
        }

    @staticmethod
    def to_markdown(state: Dict[str, Any]) -> str:
        """
        Generate a premium Markdown report compiling the entire analysis session.
        """
        data = ReportGenerator.to_json(state)
        
        md = []
        md.append(f"# Sentinel AI Analysis Report")
        md.append(f"**Query**: {data['query']}")
        md.append(f"**Symbol**: {data['symbol']}")
        md.append(f"**Correlation ID**: {data['correlation_id']}")
        md.append(f"**Status**: {data['report_status'].upper()}")
        md.append("\n---")
        
        # 1. Plan Section
        md.append("## 1. Orchestration Plan")
        md.append(f"**Plan Reasoning**: {data['plan']['reasoning']}")
        md.append(f"**Selected Agents**: {', '.join(data['plan']['selected_agents']) if data['plan']['selected_agents'] else 'None'}")
        md.append("\n---")
        
        # 2. Agent Summaries
        md.append("## 2. Research Agent Summaries")
        if not data["agent_summaries"]:
            md.append("*No agent summaries executed.*")
        for agent, summary in data["agent_summaries"].items():
            md.append(f"### {agent.replace('_', ' ').title()}")
            md.append(f"```json\n{json.dumps(summary, indent=2)}\n```")
            md.append("")
        md.append("\n---")
        
        # 3. Reasoning Synthesis
        md.append("## 3. Analyst Synthesis Reasoning")
        md.append(f"**Synthesis**: {data['reasoning_synthesis']['synthesis']}")
        
        md.append("\n**Supporting Evidence**:")
        if data['reasoning_synthesis']['supporting_evidence']:
            for ev in data['reasoning_synthesis']['supporting_evidence']:
                md.append(f"- {ev}")
        else:
            md.append("- None compiled.")
            
        md.append("\n**Conflicts/Contradictions Noted**:")
        if data['reasoning_synthesis']['conflicts_noted']:
            for conf in data['reasoning_synthesis']['conflicts_noted']:
                md.append(f"- {conf}")
        else:
            md.append("- None noted.")
        md.append("\n---")
        
        # 4. Verifier Audit
        md.append("## 4. Risk & Verification Officer Audit")
        md.append(f"**Supported**: {data['verifier_audit']['is_supported']}")
        md.append(f"**Confidence Adjustment**: {data['verifier_audit']['confidence_adjustment']:.2f}")
        md.append(f"**Audit Notes**: {data['verifier_audit']['notes']}")
        md.append("\n---")
        
        # 5. Recommendation
        md.append("## 5. Final Recommendation")
        md.append(f"### ACTION: **{data['recommendation']['action'].upper()}**")
        md.append(f"**Confidence Score**: {data['recommendation']['confidence']:.2f} (0.0 to 1.0)")
        
        md.append("\n**Supporting Evidence**:")
        if data['recommendation']['supporting_evidence']:
            for ev in data['recommendation']['supporting_evidence']:
                md.append(f"- {ev}")
        else:
            md.append("- None compiled.")
            
        md.append("\n**Identified Risks**:")
        if data['recommendation']['risks']:
            for risk in data['recommendation']['risks']:
                md.append(f"- {risk}")
        else:
            md.append("- None noted.")
            
        return "\n".join(md)
