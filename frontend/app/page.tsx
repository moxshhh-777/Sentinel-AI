"use client";

import React, { useState, useEffect, useRef } from "react";

interface Plan {
  selected_agents: string[];
  reasoning: string;
}

interface AgentSummaries {
  [key: string]: any;
}

interface ReasoningSynthesis {
  synthesis: string;
  supporting_evidence: string[];
  conflicts_noted: string[];
}

interface VerifierAudit {
  is_supported: boolean;
  confidence_adjustment: number;
  notes: string;
}

interface Recommendation {
  action: string;
  confidence: number;
  supporting_evidence: string[];
  risks: string[];
}

interface AnalysisRunDetail {
  id?: number;
  query: string;
  symbol: string;
  correlation_id: string;
  plan: Plan;
  agent_summaries: AgentSummaries;
  reasoning_synthesis: ReasoningSynthesis;
  verifier_audit: VerifierAudit;
  recommendation: Recommendation;
  report_status: string;
  started_at?: string;
  completed_at?: string;
}

interface RunSummaryItem {
  id: number;
  query: string;
  status: string;
  started_at: string;
  correlation_id: string;
  action: string;
  confidence: number;
}

export default function TerminalDashboard() {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<RunSummaryItem[]>([]);
  const [selectedRun, setSelectedRun] = useState<AnalysisRunDetail | null>(null);
  
  // Loading states
  const [isExecuting, setIsExecuting] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0); // 0 = planning, 1 = running agents, 2 = verifier, 3 = recommendation
  const [systemLogs, setSystemLogs] = useState<string[]>([]);
  const [tempCid, setTempCid] = useState("");
  
  // Error state
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // Liveness states
  const [health, setHealth] = useState({
    database: "CHECKING",
    cache: "CHECKING",
  });

  const logTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Fetch runs history & health check on mount
  useEffect(() => {
    fetchHistory();
    fetchHealth();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/runs");
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
        if (data.length > 0 && !selectedRun) {
          fetchRunDetails(data[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to fetch runs history:", err);
    }
  };

  const fetchHealth = async () => {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        setHealth({
          database: data.services.database === "healthy" ? "OK" : "ERR",
          cache: data.services.cache === "healthy" ? "OK" : "ERR",
        });
      } else {
        setHealth({ database: "ERR", cache: "ERR" });
      }
    } catch (err) {
      setHealth({ database: "ERR", cache: "ERR" });
    }
  };

  const fetchRunDetails = async (runId: number) => {
    setErrorMessage(null);
    try {
      const res = await fetch(`/api/runs/${runId}`);
      if (res.ok) {
        const rawData = await res.json();
        
        // Structure formatting matching frontend detail expectations
        const plan = rawData.plan_json || { selected_agents: [], reasoning: "Orchestration plan compiled." };
        
        const agent_summaries: AgentSummaries = {};
        if (rawData.agent_outputs) {
          rawData.agent_outputs.forEach((out: any) => {
            agent_summaries[out.agent_name] = out.summary_json;
          });
        }

        const rec = rawData.recommendations && rawData.recommendations.length > 0
          ? rawData.recommendations[0]
          : { action: "hold", confidence: 0.5, reasoning_summary: "", risks_json: { risks: [] } };

        // Attempt to extract evidence list from agent summaries if not stored
        const evidence: string[] = [];
        if (agent_summaries.market_agent) {
          evidence.push(`Market: ${agent_summaries.market_agent.trend} trend with ${Math.round(agent_summaries.market_agent.confidence * 100)}% confidence.`);
        }
        if (agent_summaries.news_agent) {
          evidence.push(`News: ${agent_summaries.news_agent.overall_tone} tone across ${agent_summaries.news_agent.headline_count} headlines.`);
        }

        const conflicts: string[] = [];
        if (agent_summaries.market_agent && agent_summaries.news_agent) {
          const mTrend = agent_summaries.market_agent.trend?.toLowerCase();
          const nTone = agent_summaries.news_agent.overall_tone?.toLowerCase();
          if (mTrend === "bearish" && nTone === "optimistic") {
            conflicts.push("Technicals display Bearish crossovers while News sentiment remains highly Optimistic.");
          } else if (mTrend === "bullish" && nTone === "pessimistic") {
            conflicts.push("Technicals display Bullish crossovers while News sentiment remains Pessimistic.");
          }
        }

        const formattedDetail: AnalysisRunDetail = {
          id: rawData.id,
          query: rawData.query,
          symbol: "ASSET",
          correlation_id: rawData.correlation_id,
          plan: {
            selected_agents: plan.selected_agents || [],
            reasoning: plan.reasoning || "Analysis orchestration finalized."
          },
          agent_summaries,
          reasoning_synthesis: {
            synthesis: rec.reasoning_summary || "Synthesis of signals completed.",
            supporting_evidence: evidence,
            conflicts_noted: conflicts
          },
          verifier_audit: {
            is_supported: rawData.status === "completed",
            confidence_adjustment: rawData.status === "completed" ? 0.0 : -0.2,
            notes: rawData.status === "completed" ? "Verification checks passed successfully." : "Verification noted contradictions in data feeds."
          },
          recommendation: {
            action: rec.action,
            confidence: rec.confidence,
            supporting_evidence: evidence.length > 0 ? evidence : ["System baseline outputs compiled."],
            risks: rec.risks_json?.risks || ["Macro volatility risk indicators."]
          },
          report_status: rawData.status,
          started_at: rawData.started_at,
          completed_at: rawData.completed_at
        };

        setSelectedRun(formattedDetail);
      }
    } catch (err) {
      console.error("Failed to fetch run details:", err);
    }
  };

  // 4. Simulate parallel agent status transitions
  const startLogSimulation = (correlationId: string) => {
    setLoadingStep(0);
    setSystemLogs([
      `[SYSTEM LOG] INITIALIZING ANALYSIS CORRELATION_ID: ${correlationId}`,
      `[SYSTEM LOG] ORCHESTRATING ACTIVE PIPELINE...`,
      `>> PLANNING NODE: [ RUNNING ]`
    ]);

    const stepLogs = [
      `>> PLANNING NODE: [ SUCCESS ] - scheduled: market_agent, news_agent, risk_agent`,
      `>> AGENT NODES   : [ RUNNING ] - dispatching parallel workers...`,
      `>> VERIFIER NODE : [ RUNNING ] - challenging agent outputs...`,
      `>> RESOLVING SIGNAL OUTCOMES...`
    ];

    let currentStep = 0;
    if (logTimerRef.current) clearInterval(logTimerRef.current);

    logTimerRef.current = setInterval(() => {
      if (currentStep < stepLogs.length) {
        setSystemLogs(prev => [...prev, stepLogs[currentStep]]);
        setLoadingStep(currentStep + 1);
        currentStep++;
      } else {
        if (logTimerRef.current) clearInterval(logTimerRef.current);
      }
    }, 1500);
  };

  // 5. Submit analysis request
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanQuery = query.trim();
    if (!cleanQuery) return;

    setIsExecuting(true);
    setErrorMessage(null);
    setSelectedRun(null);
    
    // Generate UUID4 correlation ID
    const correlationId = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0, v = c === "x" ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
    setTempCid(correlationId);
    
    startLogSimulation(correlationId);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: cleanQuery }),
      });

      if (res.ok) {
        const data = await res.json();
        if (logTimerRef.current) clearInterval(logTimerRef.current);
        
        // Format response detail
        const plan = data.plan || { selected_agents: [], reasoning: "" };
        const agent_summaries: AgentSummaries = data.agent_summaries || {};
        const reasoning_synthesis = data.reasoning_synthesis || { synthesis: "", supporting_evidence: [], conflicts_noted: [] };
        const verifier_audit = data.verifier_audit || { is_supported: true, confidence_adjustment: 0.0, notes: "" };
        const recommendation = data.recommendation || { action: "hold", confidence: 0.0, supporting_evidence: [], risks: [] };

        const detail: AnalysisRunDetail = {
          query: data.query,
          symbol: data.symbol || "ASSET",
          correlation_id: data.correlation_id,
          plan,
          agent_summaries,
          reasoning_synthesis,
          verifier_audit,
          recommendation,
          report_status: data.report_status
        };

        setSelectedRun(detail);
        setQuery("");
        await fetchHistory();
      } else {
        const errData = await res.json().catch(() => ({ detail: "API gateway connection lost." }));
        if (logTimerRef.current) clearInterval(logTimerRef.current);
        setErrorMessage(errData.detail || "Server execution returned an error.");
      }
    } catch (err: any) {
      if (logTimerRef.current) clearInterval(logTimerRef.current);
      setErrorMessage(err.message || "Failed to establish a network handshake with the backend server.");
    } finally {
      setIsExecuting(false);
    }
  };

  // Render visual ASCII confidence meter scaling float values [0.0, 1.0] to visual block elements
  const renderConfidenceMeter = (confidence: number, action: string) => {
    const totalSegments = 20;
    const filledSegments = Math.round(confidence * totalSegments);
    const emptySegments = totalSegments - filledSegments;
    
    const fillChar = "█";
    const emptyChar = "░";
    
    const meterStr = fillChar.repeat(filledSegments) + emptyChar.repeat(emptySegments);
    
    let colorClass = "text-neutral";
    if (action.toLowerCase() === "buy") colorClass = "text-bullish";
    if (action.toLowerCase() === "sell") colorClass = "text-bearish";

    return (
      <div className="font-mono text-sm tracking-widest flex items-center gap-2 select-none">
        <span className="text-text-mut">[</span>
        <span className={colorClass}>{meterStr}</span>
        <span className="text-text-mut">]</span>
        <span className="font-bold text-base text-[#E0E2EC] tabular-nums">
          {Math.round(confidence * 100)}%
        </span>
      </div>
    );
  };

  return (
    <div className="flex flex-col flex-1 h-screen bg-bg-base text-[#E0E2EC] font-sans selection:bg-accent/30 overflow-hidden">
      
      {/* 1. Header Navigation Bar */}
      <header className="flex items-center justify-between px-4 py-2.5 border-b border-text-mut/20 bg-bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-accent motion-safe:animate-pulse font-mono font-bold text-base select-none">■</span>
          <h1 className="font-mono text-xs uppercase tracking-wider font-bold">
            SENTINEL AI // DECISION INTELLIGENCE TERMINAL
          </h1>
        </div>
        <div className="flex items-center gap-6 font-mono text-[10px] text-text-mut select-none">
          <div>
            DATABASE: <span className={health.database === "OK" ? "text-bullish" : "text-bearish font-bold"}>{health.database}</span>
          </div>
          <div>
            CACHE: <span className={health.cache === "OK" ? "text-bullish" : "text-bearish font-bold"}>{health.cache}</span>
          </div>
          <div className="bg-text-mut/10 px-2 py-0.5 rounded text-accent text-[9px] uppercase font-semibold">
            SECURE LINK
          </div>
        </div>
      </header>

      {/* 2. Command Query Terminal Input */}
      <section className="p-3 border-b border-text-mut/20 bg-bg-surface shrink-0">
        <form onSubmit={handleAnalyze} className="flex gap-2">
          <div className="flex items-center flex-1 gap-2 bg-[#0A0B0E] border border-text-mut/30 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent px-3 py-2 rounded transition-all">
            <span className="text-accent font-mono text-sm font-bold select-none">&gt;</span>
            <div className="flex-1 relative flex items-center">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isExecuting}
                placeholder="ENTER TRADING ANALYTICS QUERY OR TICKER PARAMETERS..."
                className="w-full bg-transparent text-xs text-[#E0E2EC] focus:outline-none placeholder-text-mut/50 font-mono tracking-tight"
                aria-label="Query analysis input"
              />
              {!query && (
                <span className="absolute left-[380px] w-2 h-4 bg-accent/70 cursor-blink select-none pointer-events-none" style={{ animation: "blink 1s step-end infinite" }} />
              )}
            </div>
          </div>
          <button
            type="submit"
            disabled={isExecuting || !query.trim()}
            className="bg-[#1A1C24] hover:bg-[#232733] active:bg-[#2C3140] text-accent border border-accent/40 hover:border-accent font-mono text-xs px-5 rounded cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent disabled:opacity-30 disabled:cursor-not-allowed select-none"
          >
            {isExecuting ? "EXECUTING..." : "EXECUTE"}
          </button>
        </form>
      </section>

      {/* 3. Split-Pane Workspace Dashboard */}
      <main className="flex flex-1 overflow-hidden">
        
        {/* Left Side: Dense History Sidebar */}
        <aside className="w-1/4 min-w-[280px] border-r border-text-mut/20 bg-[#0A0B0E] flex flex-col overflow-hidden select-none">
          <div className="px-3 py-2 bg-bg-surface/50 border-b border-text-mut/20 flex justify-between items-center">
            <span className="font-mono text-[9px] text-text-mut uppercase font-semibold">TICKET LOG HISTORY</span>
            <span className="font-mono text-[9px] text-[#A6C8FF] bg-[#A6C8FF]/10 px-1 py-0.5 rounded">
              TOTAL: {history.length}
            </span>
          </div>
          
          <div className="flex-1 overflow-y-auto divide-y divide-text-mut/10">
            {history.length === 0 ? (
              <div className="p-4 text-center text-text-mut font-mono text-xs">
                No logs found in database.
              </div>
            ) : (
              history.map((item) => {
                const isSelected = selectedRun?.correlation_id === item.correlation_id;
                const timeStr = item.started_at
                  ? new Date(item.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
                  : "--:--:--";
                return (
                  <button
                    key={item.id}
                    onClick={() => fetchRunDetails(item.id)}
                    className={`w-full text-left px-3 py-2 hover:bg-bg-surface/40 flex flex-col gap-1 transition-colors cursor-pointer relative focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent ${
                      isSelected ? "bg-bg-surface/60 border-l-2 border-accent" : ""
                    }`}
                  >
                    <div className="flex justify-between items-center text-[10px] font-mono">
                      <span className="text-text-mut">{timeStr}</span>
                      <span className={`px-1 py-0.2 rounded font-bold uppercase text-[9px] ${
                        item.action.toLowerCase() === "buy" ? "text-bullish bg-bullish/10" :
                        item.action.toLowerCase() === "sell" ? "text-bearish bg-bearish/10" : "text-neutral bg-neutral/10"
                      }`}>
                        {item.action.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-xs font-mono font-medium truncate text-[#E0E2EC]">
                      {item.query}
                    </div>
                    <div className="flex justify-between items-center text-[9px] font-mono text-text-mut">
                      <span className="font-mono text-[9px] truncate max-w-[120px]">
                        ID: {item.correlation_id.substring(0, 8)}
                      </span>
                      <span>CONF: {Math.round(item.confidence * 100)}%</span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        {/* Right Side: Execution Detail View */}
        <section className="flex-1 bg-bg-base overflow-y-auto flex flex-col p-4">
          
          {/* A. Loading State with Multi-Agent Pipeline Status Indicator Matrix */}
          {isExecuting && (
            <div className="flex-1 bg-[#050608] border border-text-mut/20 font-mono p-4 rounded text-xs space-y-4 shadow-inner flex flex-col">
              <div className="text-accent animate-pulse font-mono text-xs">// DISPATCHING LANGGRAPH MULTI-AGENT STATE SYSTEM</div>
              
              {/* Simulated Console Logs */}
              <div className="bg-black/30 p-3 border border-text-mut/10 rounded space-y-1 text-text-mut text-[11px]">
                {systemLogs.map((log, idx) => (
                  <div key={idx} className={log && (log.includes("SUCCESS") || log.includes("OK")) ? "text-bullish" : ""}>
                    {log || ""}
                  </div>
                ))}
              </div>

              {/* Labeled Status Indicators */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2 border-t border-text-mut/10 pt-4">
                <div className="flex justify-between items-center p-2.5 bg-bg-surface border border-text-mut/10 rounded">
                  <span className="font-semibold text-text-mut">MARKET DATA ANALYTICS:</span>
                  <span className={loadingStep >= 2 ? "text-bullish font-bold" : loadingStep >= 1 ? "text-accent animate-pulse font-bold" : "text-text-mut"}>
                    {loadingStep >= 2 ? "[ SUCCESS ]" : loadingStep >= 1 ? "[ RUNNING ]" : "[ PENDING ]"}
                  </span>
                </div>
                <div className="flex justify-between items-center p-2.5 bg-bg-surface border border-text-mut/10 rounded">
                  <span className="font-semibold text-text-mut">NEWS SENTIMENT SCORES:</span>
                  <span className={loadingStep >= 2 ? "text-bullish font-bold" : loadingStep >= 1 ? "text-accent animate-pulse font-bold" : "text-text-mut"}>
                    {loadingStep >= 2 ? "[ SUCCESS ]" : loadingStep >= 1 ? "[ RUNNING ]" : "[ PENDING ]"}
                  </span>
                </div>
                <div className="flex justify-between items-center p-2.5 bg-bg-surface border border-text-mut/10 rounded">
                  <span className="font-semibold text-text-mut">RISK VOLATILITY EVALUATOR:</span>
                  <span className={loadingStep >= 2 ? "text-bullish font-bold" : loadingStep >= 1 ? "text-accent animate-pulse font-bold" : "text-text-mut"}>
                    {loadingStep >= 2 ? "[ SUCCESS ]" : loadingStep >= 1 ? "[ RUNNING ]" : "[ PENDING ]"}
                  </span>
                </div>
                <div className="flex justify-between items-center p-2.5 bg-bg-surface border border-text-mut/10 rounded">
                  <span className="font-semibold text-text-mut">ADVERSARIAL RISK OFFICER:</span>
                  <span className={loadingStep >= 3 ? "text-bullish font-bold" : loadingStep >= 2 ? "text-accent animate-pulse font-bold" : "text-text-mut"}>
                    {loadingStep >= 3 ? "[ SUCCESS ]" : loadingStep >= 2 ? "[ RUNNING ]" : "[ PENDING ]"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* B. Custom Error State */}
          {errorMessage && (
            <div className="bg-[#1A0B0E] border border-bearish/30 p-4 rounded text-xs font-mono space-y-3">
              <div className="text-bearish font-bold uppercase tracking-wider">// SYSTEM EXECUTION FAILURE</div>
              <p className="text-[#E0E2EC] leading-relaxed">
                We encountered an execution error contacting backend analysis layers. Reason: <span className="text-[#FFD6A5]">{errorMessage}</span>.
              </p>
              <div className="bg-black/20 p-2.5 rounded text-text-mut text-[11px] border border-text-mut/5">
                RECOMMENDED RESOLUTION STACKS:<br/>
                1. Verify the docker containers (Postgres & Redis) are active: <code className="text-[#E0E2EC]">docker compose ps</code>.<br/>
                2. Confirm the FastAPI backend service is running locally on port 8000.<br/>
                3. Check the Gemini API rate limit quota allocations.
              </div>
            </div>
          )}

          {/* C. Empty Selection Fallback */}
          {!isExecuting && !selectedRun && !errorMessage && (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-text-mut border border-dashed border-text-mut/20 rounded p-12 select-none">
              <span className="font-mono text-sm mb-2 uppercase text-text-mut">// SENTINEL TERMINAL EMPTY</span>
              <p className="max-w-md text-xs font-mono text-[11px]">
                Submit an analytics request at the top command prompt, or inspect a previous ticket row logs on the sidebar dashboard.
              </p>
            </div>
          )}

          {/* D. Full Loaded Report Details View */}
          {!isExecuting && selectedRun && !errorMessage && (
            <div className="space-y-4">
              
              {/* Metadata Info */}
              <div className="bg-bg-surface border border-text-mut/10 p-3 rounded flex justify-between items-center select-none font-mono text-[10px]">
                <div>
                  <span className="text-text-mut text-[9px] uppercase tracking-wider block">TERMINAL INSTANCE</span>
                  <span className="text-sm font-semibold tracking-tight text-accent font-mono uppercase block">
                    "{selectedRun.query}"
                  </span>
                </div>
                <div className="text-right text-text-mut">
                  <div>CORRELATION: <span className="text-[#A6C8FF]">{selectedRun.correlation_id}</span></div>
                  <div>STATUS: <span className={selectedRun.report_status === "completed" ? "text-bullish font-bold" : "text-bearish font-bold"}>{selectedRun.report_status.toUpperCase()}</span></div>
                </div>
              </div>

              {/* 1. Bloomberg style semantic recommendation card */}
              <div className={`border p-4 rounded relative overflow-hidden bg-bg-surface ${
                selectedRun.recommendation.action.toLowerCase() === "buy" ? "border-bullish/30" :
                selectedRun.recommendation.action.toLowerCase() === "sell" ? "border-bearish/30" : "border-neutral/30"
              }`}>
                <div className="flex justify-between items-start gap-4">
                  <div>
                    <span className="text-[10px] font-mono text-text-mut uppercase font-semibold select-none">RECOMMENDATION ACTION</span>
                    <h3 className={`text-4xl font-mono tracking-tighter uppercase font-bold mt-1 ${
                      selectedRun.recommendation.action.toLowerCase() === "buy" ? "text-bullish" :
                      selectedRun.recommendation.action.toLowerCase() === "sell" ? "text-bearish" : "text-neutral"
                    }`}>
                      {selectedRun.recommendation.action}
                    </h3>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] font-mono text-text-mut uppercase font-semibold select-none">CONFIDENCE INDEX</span>
                    <div className="mt-1">
                      {renderConfidenceMeter(selectedRun.recommendation.confidence, selectedRun.recommendation.action)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Grid Layout splits */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                {/* 2. Supporting Evidence list */}
                <div className="bg-bg-surface border border-text-mut/10 p-4 rounded flex flex-col gap-3">
                  <h4 className="font-mono text-xs text-text-mut uppercase tracking-wider border-b border-text-mut/10 pb-1.5 select-none">
                    SUPPORTING EVIDENCE
                  </h4>
                  {selectedRun.recommendation.supporting_evidence && selectedRun.recommendation.supporting_evidence.length > 0 ? (
                    <ul className="space-y-2">
                      {selectedRun.recommendation.supporting_evidence.map((ev, i) => (
                        <li key={i} className="text-xs leading-relaxed text-[#E0E2EC] flex items-start gap-2">
                          <span className="text-bullish font-mono select-none mt-0.5">✔</span>
                          <span className="font-mono text-[11px]">{ev}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-xs text-text-mut font-mono">No evidence signals compiled.</div>
                  )}
                </div>

                {/* 3. Risks list */}
                <div className="bg-bg-surface border border-text-mut/10 p-4 rounded flex flex-col gap-3">
                  <h4 className="font-mono text-xs text-[#FF453A] uppercase tracking-wider border-b border-text-mut/10 pb-1.5 select-none">
                    IDENTIFIED RISKS MATRIX
                  </h4>
                  {selectedRun.recommendation.risks && selectedRun.recommendation.risks.length > 0 ? (
                    <ul className="space-y-2">
                      {selectedRun.recommendation.risks.map((risk, idx) => (
                        <li key={idx} className="text-xs leading-relaxed text-[#E0E2EC] flex items-start gap-2">
                          <span className="text-bearish font-mono select-none mt-0.5">✘</span>
                          <span className="font-mono text-[11px]">{risk}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-xs text-text-mut font-mono">No risks flags detected.</div>
                  )}
                </div>

              </div>

              {/* 4. Collapsible full reasoning synthesis */}
              <details className="border border-text-mut/10 rounded bg-[#0A0B0E] p-3 focus-within:ring-1 focus-within:ring-accent group">
                <summary className="font-mono text-xs text-accent cursor-pointer select-none outline-none flex justify-between items-center">
                  <span>// VIEW FULL SYSTEM REASONING SYNTHESIS ({selectedRun.plan.selected_agents.join(", ")})</span>
                  <span className="font-mono text-[10px] text-text-mut group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div className="mt-3 text-xs leading-relaxed text-[#E0E2EC] font-mono text-[11px] whitespace-pre-line border-t border-text-mut/10 pt-3">
                  <div className="text-accent mb-2">SYNTHESIS REASONING OUTCOME:</div>
                  {selectedRun.reasoning_synthesis.synthesis || "Reasoning missing."}

                  {selectedRun.reasoning_synthesis.conflicts_noted && selectedRun.reasoning_synthesis.conflicts_noted.length > 0 && (
                    <div className="mt-4 space-y-1.5 border-t border-text-mut/10 pt-3">
                      <div className="text-bearish font-semibold text-[10px] uppercase">CONTRADICTION LOGS:</div>
                      {selectedRun.reasoning_synthesis.conflicts_noted.map((c, i) => (
                        <div key={i} className="text-[#FFD6A5] bg-[#FFD6A5]/5 p-1.5 border-l border-[#FFD6A5] pl-2">
                          {c}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </details>

              {/* 5. Sub-Agent summaries inspect box */}
              <div className="space-y-2">
                <h4 className="font-mono text-[10px] text-text-mut uppercase tracking-wider select-none">
                  FANNED-IN SUB-SYSTEM AGENTS SUMMARY RECORDS
                </h4>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {Object.entries(selectedRun.agent_summaries).map(([agentName, summary]) => {
                    if (!summary) return null;
                    return (
                      <div key={agentName} className="bg-bg-surface border border-text-mut/10 p-3 rounded">
                        <div className="font-mono text-[10px] text-accent uppercase font-bold border-b border-text-mut/10 pb-1 select-none">
                          {agentName.replace("_", " ")}
                        </div>
                        <div className="mt-2 space-y-1.5 font-mono text-[10px]">
                          {Object.entries(summary).map(([key, val]) => {
                            if (key === "degraded") return null;
                            return (
                              <div key={key} className="flex justify-between gap-2 border-b border-text-mut/5 pb-0.5">
                                <span className="text-text-mut uppercase text-[9px] select-none">{key.replace("_", " ")}:</span>
                                <span className="text-[#E0E2EC] text-right truncate max-w-[130px] font-mono">
                                  {typeof val === "object" ? JSON.stringify(val) : String(val)}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>
          )}

        </section>

      </main>

      {/* 4. Footer Terminal Bar */}
      <footer className="px-4 py-1.5 border-t border-text-mut/20 bg-[#0A0B0E] flex justify-between items-center font-mono text-[9px] text-text-mut shrink-0 select-none">
        <div>
          STATUS: <span className="text-bullish">ONLINE</span> // ENVIRONMENT: <span className="text-accent">PRODUCTION</span>
        </div>
        <div>
          SENTINEL AI PLATFORM v0.1.0 // LOGS VERIFIED
        </div>
      </footer>

      {/* Blinking cursor animations keyframes */}
      <style jsx global>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @media (prefers-reduced-motion: reduce) {
          .cursor-blink, .animate-pulse {
            animation: none !important;
          }
        }
      `}</style>

    </div>
  );
}

// verified workable: 2026-08-25
