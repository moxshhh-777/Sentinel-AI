import logging
from typing import TypedDict, Optional, List, Dict, Any, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver

from app.registry.planning import PlanningModule
from app.agents import market_agent_node, news_agent_node, risk_agent_node

# Set up graph structured logger
logger = logging.getLogger("sentinel.graph")

def merge_outputs(left: dict, right: dict) -> dict:
    """
    State reducer that merges dictionaries from fanned-out parallel agents.
    Prevents key collisions by ensuring each agent populates its own sub-key.
    """
    new_dict = dict(left) if left else {}
    if right:
        new_dict.update(right)
    return new_dict


class SentinelState(TypedDict):
    query: str
    symbol: str
    correlation_id: str
    plan: Optional[dict]
    agent_outputs: Annotated[dict, merge_outputs]
    reasoning: Optional[dict]
    verification: Optional[dict]
    recommendation: Optional[dict]
    report: Optional[dict]


# 1. Supervisor / Planner Node
async def supervisor_node(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    query = state.get("query", "")
    
    logger.info(f"[{correlation_id}] Entering node: supervisor")
    
    if not query or len(query.strip()) < 3:
        logger.warning(f"[{correlation_id}] Query is empty or invalid. Short-circuiting execution.")
        logger.info(f"[{correlation_id}] Exiting node: supervisor")
        return {
            "plan": {
                "selected_agents": [],
                "reasoning": "Query is empty or invalid."
            }
        }
        
    planner = PlanningModule()
    try:
        plan_obj = await planner.create_plan(query)
        plan = plan_obj.model_dump()
    except Exception as e:
        logger.error(f"[{correlation_id}] Planning module failed: {e}")
        plan = {
            "selected_agents": [],
            "reasoning": f"Planning failed: {str(e)}"
        }

    # Heuristic parsing of ticker symbol from query
    words = [w.strip("?,.!") for w in query.split()]
    symbol = "AAPL"  # default fallback
    for w in words:
        if w.isupper() and len(w) >= 2 and len(w) <= 5:
            symbol = w
            break
    else:
        query_lower = query.lower()
        if "gold" in query_lower:
            symbol = "GC=F"
        elif "oil" in query_lower:
            symbol = "CL=F"
        elif "bitcoin" in query_lower:
            symbol = "BTC-USD"
            
    logger.info(f"[{correlation_id}] Supervisor node completed. Plan: selected_agents={plan['selected_agents']}, symbol={symbol}")
    logger.info(f"[{correlation_id}] Exiting node: supervisor")
    return {"plan": plan, "symbol": symbol}


# 2. Agent Wrapper Nodes (Convert AgentState to SentinelState output mapping)
async def market_agent_wrapper(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: market_agent")
    
    result = await market_agent_node(state)
    
    logger.info(f"[{correlation_id}] Exiting node: market_agent")
    return {"agent_outputs": {"market_agent": result.get("market_summary")}}


async def news_agent_wrapper(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: news_agent")
    
    result = await news_agent_node(state)
    
    logger.info(f"[{correlation_id}] Exiting node: news_agent")
    return {"agent_outputs": {"news_agent": result.get("news_summary")}}


async def risk_agent_wrapper(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: risk_agent")
    
    # Access news summary context from fanned-in/previous agent state outputs
    outputs = state.get("agent_outputs") or {}
    news_out = outputs.get("news_agent")
    
    state_copy = dict(state)
    if news_out:
        state_copy["news_summary"] = news_out
        
    result = await risk_agent_node(state_copy)
    
    logger.info(f"[{correlation_id}] Exiting node: risk_agent")
    return {"agent_outputs": {"risk_agent": result.get("risk_summary")}}


# 3. Router Edge (Parallel Send logic)
def route_to_agents(state: SentinelState):
    correlation_id = state.get("correlation_id", "unknown-id")
    plan = state.get("plan")
    selected = plan.get("selected_agents", []) if plan else []
    
    if not selected:
        logger.warning(f"[{correlation_id}] Router edge: No agents selected, routing to failure_node.")
        return "failure_node"
        
    sends = []
    for agent in selected:
        if agent in ["market_agent", "news_agent", "risk_agent"]:
            sends.append(Send(agent, state))
            
    if not sends:
        logger.warning(f"[{correlation_id}] Router edge: Selected agents invalid or empty. Routing to failure_node.")
        return "failure_node"
        
    logger.info(f"[{correlation_id}] Router edge: Fanning out in parallel to {len(sends)} agents: {selected}")
    return sends


# 4. Fan-in Collect Results Node
def collect_results_node(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: collect_results")
    logger.info(f"[{correlation_id}] Aggregated agent outputs: {list(state.get('agent_outputs', {}).keys())}")
    logger.info(f"[{correlation_id}] Exiting node: collect_results")
    return {}


# 5. Degraded Conditional Edge
def check_degraded_status(state: SentinelState):
    correlation_id = state.get("correlation_id", "unknown-id")
    plan = state.get("plan")
    selected = plan.get("selected_agents", []) if plan else []
    outputs = state.get("agent_outputs") or {}
    
    if not selected:
        return "failure_node"
        
    all_degraded = True
    for agent in selected:
        out = outputs.get(agent)
        if not out or not out.get("degraded"):
            all_degraded = False
            break
            
    if all_degraded:
        logger.warning(f"[{correlation_id}] All selected agents falled back to degraded status. Routing to failure_node.")
        return "failure_node"
        
    logger.info(f"[{correlation_id}] Valid data received from agents. Routing to reasoning_stub.")
    return "reasoning_stub"


# 6. Failure & Stubs Nodes
def failure_node(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: failure_node")
    logger.info(f"[{correlation_id}] Exiting node: failure_node")
    return {
        "report": {
            "status": "failed",
            "message": "insufficient data to complete analysis"
        }
    }


def reasoning_stub(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: reasoning_stub")
    logger.info(f"[{correlation_id}] Exiting node: reasoning_stub")
    return {"reasoning": {"status": "skipped", "message": "Phase 6 stub"}}


def verification_stub(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: verification_stub")
    logger.info(f"[{correlation_id}] Exiting node: verification_stub")
    return {"verification": {"status": "skipped", "message": "Phase 6 stub"}}


def recommendation_stub(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: recommendation_stub")
    logger.info(f"[{correlation_id}] Exiting node: recommendation_stub")
    return {"recommendation": {"status": "skipped", "message": "Phase 6 stub"}}


def report_stub(state: SentinelState) -> Dict[str, Any]:
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Entering node: report_stub")
    logger.info(f"[{correlation_id}] Exiting node: report_stub")
    return {"report": {"status": "success", "message": "Phase 6 stub completed"}}


# Build StateGraph
workflow = StateGraph(SentinelState)

# Add Nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("market_agent", market_agent_wrapper)
workflow.add_node("news_agent", news_agent_wrapper)
workflow.add_node("risk_agent", risk_agent_wrapper)
workflow.add_node("collect_results", collect_results_node)
workflow.add_node("failure_node", failure_node)
workflow.add_node("reasoning_stub", reasoning_stub)
workflow.add_node("verification_stub", verification_stub)
workflow.add_node("recommendation_stub", recommendation_stub)
workflow.add_node("report_stub", report_stub)

# Set Entrance
workflow.add_edge(START, "supervisor")

# Configure Fan-Out Edge
workflow.add_conditional_edges(
    "supervisor",
    route_to_agents,
    ["market_agent", "news_agent", "risk_agent", "failure_node"]
)

# Wire parallel agents to convergence node
workflow.add_edge("market_agent", "collect_results")
workflow.add_edge("news_agent", "collect_results")
workflow.add_edge("risk_agent", "collect_results")

# Fan-in Conditional Edge
workflow.add_conditional_edges(
    "collect_results",
    check_degraded_status,
    ["failure_node", "reasoning_stub"]
)

# Failure Node Exit
workflow.add_edge("failure_node", END)

# Happy Path Flow
workflow.add_edge("reasoning_stub", "verification_stub")
workflow.add_edge("verification_stub", "recommendation_stub")
workflow.add_edge("recommendation_stub", "report_stub")
workflow.add_edge("report_stub", END)

# Compile with checkpoint memory saver
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)
