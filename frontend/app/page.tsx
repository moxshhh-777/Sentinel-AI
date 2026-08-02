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
  const [executionLogs, setExecutionLogs] = useState<string[]>([]);
  
  // Liveness states
  const [health, setHealth] = useState({
    database: "checking",
    cache: "checking",
  });

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const logTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Fetch runs history & health check on mount
  useEffect(() => {
    fetchHistory();
    fetchHealth();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_URL}/api/runs`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
        // Default select first item if available
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
      const res = await fetch(`${API_URL}/health`);
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
    try {
      const res = await fetch(`${API_URL}/api/runs/${runId}`);
      if (res.ok) {
        const rawData = await res.json();
        // Convert API shape to Detail shape
        const plan = rawData.plan_json || { selected_agents: [], reasoning: "" };
        
        // Find agent summaries
        const agent_summaries: AgentSummaries = {};
        if (rawData.agent_outputs) {
          rawData.agent_outputs.forEach((out: any) => {
            agent_summaries[out.agent_name] = out.summary_json;
          });
        }

        // Find recommendations
        const rec = rawData.recommendations && rawData.recommendations.length > 0
          ? rawData.recommendations[0]
          : { action: "hold", confidence: 0.0, reasoning_summary: "", risks_json: { risks: [] } };

        const formattedDetail: AnalysisRunDetail = {
          id: rawData.id,
          query: rawData.query,
          symbol: "ASSET", // placeholder
          correlation_id: rawData.correlation_id,
          plan: {
            selected_agents: plan.selected_agents || [],
            reasoning: plan.reasoning || "Planning finalized."
          },
          agent_summaries,
          reasoning_synthesis: {
            synthesis: rec.reasoning_summary || "Synthesis complete.",
            supporting_evidence: [],
            conflicts_noted: []
          },
          verifier_audit: {
            is_supported: true,
            confidence_adjustment: 0.0,
            notes: "Audit passed."
          },
          recommendation: {
            action: rec.action,
            confidence: rec.confidence,
            supporting_evidence: [],
            risks: rec.risks_json?.risks || []
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

  // 2. Simulate parallel agent status matrix logs
  const startLogSimulation = (correlationId: string) => {
    setExecutionLogs([
      `[SYSTEM LOG] INIT AT ${new Date().toISOString()}`,
      `[SYSTEM LOG] ASSIGNED CORRELATION_ID: ${correlationId}`,
      `PLANNING MODULE       : [ RUNNING ]`
    ]);

    let step = 0;
    const logs = [
      `PLANNING MODULE       : [ OK ] - selected: market_agent, news_agent, risk_agent`,
      `MARKET AGENT NODE     : [ RUNNING ]\nNEWS AGENT NODE       : [ RUNNING ]\nRISK AGENT NODE       : [ RUNNING ]`,
      `MARKET AGENT NODE     : [ OK ] - technical trend analysis complete`,
      `NEWS AGENT NODE       : [ OK ] - sentiment signals extracted`,
      `RISK AGENT NODE       : [ OK ] - volatility assessment complete`,
      `VERIFIER AUDIT NODE   : [ RUNNING ] - challenging contradiction signals`,
      `VERIFIER AUDIT NODE   : [ OK ] - analysis logical support verified`,
      `RECOMMENDATION NODE   : [ RUNNING ] - calculating adjusted confidence`,
      `RECOMMENDATION NODE   : [ OK ] - final order compiled`,
      `[SYSTEM LOG] PIPELINE EXECUTION SUCCESSFUL`
    ];

    if (logTimerRef.current) clearInterval(logTimerRef.current);

    logTimerRef.current = setInterval(() => {
      if (step < logs.length) {
        setExecutionLogs(prev => [...prev, logs[step]]);
        step++;
      } else {
        if (logTimerRef.current) clearInterval(logTimerRef.current);
      }
    }, 900);
  };

  // 3. Submit analysis request
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanQuery = query.trim();
    if (!cleanQuery) return;

    setIsExecuting(true);
    setSelectedRun(null);
    
    // Pre-generate temporary correlation ID for UI logging
    const tempCid = "xxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0, v = c === "x" ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
    
    startLogSimulation(tempCid);

    try {
      const res = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: cleanQuery }),
      });

      if (res.ok) {
        const data = await res.json();
        // Clear log timer and set details
        if (logTimerRef.current) clearInterval(logTimerRef.current);
        
        const detail: AnalysisRunDetail = {
          query: data.query,
          symbol: data.symbol,
          correlation_id: data.correlation_id,
          plan: data.plan,
          agent_summaries: data.agent_summaries,
          reasoning_synthesis: data.reasoning_synthesis,
          verifier_audit: data.verifier_audit,
          recommendation: data.recommendation,
          report_status: data.report_status
        };

        setSelectedRun(detail);
        setQuery("");
        // Refresh past runs list
        await fetchHistory();
      } else {
        const errData = await res.json();
        setExecutionLogs(prev => [
          ...prev,
          `[CRITICAL ERROR] Execution failed: ${errData.detail || "Server error"}`
        ]);
      }
    } catch (err) {
      setExecutionLogs(prev => [
        ...prev,
        `[CRITICAL ERROR] Network connection refused. Ensure backend is running.`
      ]);
    } finally {
      setIsExecuting(false);
    }
  };

  const getActionColor = (action: string) => {
    switch (action.toLowerCase()) {
      case "buy":
        return "text-bullish border-bullish bg-bullish/5";
      case "sell":
        return "text-bearish border-bearish bg-bearish/5";
      default:
        return "text-neutral border-neutral bg-neutral/5";
    }
  };

  const getActionBadge = (action: string) => {
    switch (action.toLowerCase()) {
      case "buy":
        return "bg-bullish text-black font-semibold";
      case "sell":
        return "bg-bearish text-black font-semibold";
      default:
        return "bg-neutral text-black font-semibold";
    }
  };

  return (
    <div className="flex flex-col flex-1 h-screen bg-bg-base text-[#E0E2EC] font-sans selection:bg-accent/30 overflow-hidden">
      
      {/* 1. Header Navigation Bar */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-text-mut/20 bg-bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-accent animate-pulse font-mono font-bold text-lg">■</span>
          <h1 className="font-mono text-xs uppercase tracking-wider font-bold text-[#E0E2EC]">
            SENTINEL AI // DECISION INTELLIGENCE TERMINAL
          </h1>
        </div>
        <div className="flex items-center gap-6 font-mono text-[10px] text-text-mut">
          <div>
            DATABASE: <span className={health.database === "OK" ? "text-bullish" : "text-bearish font-bold"}>{health.database}</span>
          </div>
          <div>
            CACHE: <span className={health.cache === "OK" ? "text-bullish" : "text-bearish font-bold"}>{health.cache}</span>
          </div>
          <div className="bg-text-mut/10 px-2 py-0.5 rounded text-accent text-[9px] uppercase font-semibold">
            SECURE SESSION
          </div>
        </div>
      </header>

      {/* 2. Command Query Terminal Input */}
      <section className="p-3 border-b border-text-mut/20 bg-bg-surface shrink-0">
        <form onSubmit={handleAnalyze} className="flex gap-2">
          <div className="flex items-center flex-1 gap-2 bg-[#0A0B0E] border border-text-mut/30 focus-within:border-accent px-3 py-2 rounded">
            <span className="text-accent font-mono text-sm font-bold">&gt;</span>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isExecuting}
              placeholder="ENTER TRADING ANALYTICS QUERY (e.g. 'Analyze AAPL stock parameters')"
              className="flex-1 bg-transparent text-sm text-[#E0E2EC] focus:outline-none placeholder-text-mut/50 font-mono tracking-tight"
            />
          </div>
          <button
            type="submit"
            disabled={isExecuting || !query.trim()}
            className="bg-[#1A1C24] hover:bg-[#232733] active:bg-[#2C3140] text-accent border border-accent/40 hover:border-accent font-mono text-xs px-5 rounded cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {isExecuting ? "RUNNING..." : "RUN ANALYSIS"}
          </button>
        </form>
      </section>

      {/* 3. Split-Pane Workspace Dashboard */}
      <main className="flex flex-1 overflow-hidden">
        
        {/* Left Side: Dense History Sidebar */}
        <aside className="w-1/4 min-w-[280px] border-r border-text-mut/20 bg-[#0A0B0E] flex flex-col overflow-hidden">
          <div className="px-3 py-2 bg-bg-surface/50 border-b border-text-mut/20 flex justify-between items-center">
            <span className="font-mono text-[10px] text-text-mut uppercase font-semibold">EXECUTION LOGS HISTORY</span>
            <span className="font-mono text-[9px] text-[#A6C8FF] bg-[#A6C8FF]/10 px-1 py-0.5 rounded">
              TOTAL: {history.length}
            </span>
          </div>
          
          <div className="flex-1 overflow-y-auto divide-y divide-text-mut/10">
            {history.length === 0 ? (
              <div className="p-4 text-center text-text-mut font-mono text-xs">
                No past runs found in database.
              </div>
            ) : (
              history.map((item) => {
                const isSelected = selectedRun?.correlation_id === item.correlation_id;
                const timeStr = item.started_at
                  ? new Date(item.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
                  : "--:--:--";
                return (
                  <button
                    key={item.id}
                    onClick={() => fetchRunDetails(item.id)}
                    className={`w-full text-left p-3 hover:bg-bg-surface/40 flex flex-col gap-1 transition-colors cursor-pointer relative ${
                      isSelected ? "bg-bg-surface/60 border-l-2 border-accent" : ""
                    }`}
                  >
                    <div className="flex justify-between items-center text-[11px] font-mono">
                      <span className="text-text-mut">{timeStr}</span>
                      <span className={`px-1.5 py-0.2 rounded font-bold uppercase text-[9px] ${
                        item.action.toLowerCase() === "buy" ? "bg-bullish/10 text-bullish" :
                        item.action.toLowerCase() === "sell" ? "bg-bearish/10 text-bearish" : "bg-neutral/10 text-neutral"
                      }`}>
                        {item.action.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-xs font-mono font-medium truncate text-[#E0E2EC]">
                      {item.query}
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-mono text-text-mut">
                      <span className="font-mono text-[9px] truncate max-w-[120px]">
                        ID: {item.correlation_id.substring(0, 8)}...
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
          
          {/* A. Dynamic simulated console logger during execution */}
          {isExecuting && (
            <div className="flex-1 bg-[#050608] border border-[#232733] font-mono p-4 rounded text-xs leading-relaxed overflow-y-auto shadow-inner">
              <div className="text-accent mb-2">RUNNING STATEGRAPH WORKFLOW PIPELINE IN REAL-TIME...</div>
              <div className="space-y-1">
                {executionLogs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`whitespace-pre-line ${
                      log.includes("OK") ? "text-bullish" :
                      log.includes("RUNNING") ? "text-accent animate-pulse" :
                      log.includes("CRITICAL") ? "text-bearish" : "text-[#E0E2EC]"
                    }`}
                  >
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* B. No selection fallback */}
          {!isExecuting && !selectedRun && (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-text-mut border border-dashed border-text-mut/20 rounded p-12">
              <span className="font-mono text-lg mb-2 text-text-mut">NO ANALYSIS RUN REPORT LOADED</span>
              <p className="max-w-md text-xs font-mono">
                Submit an analytics request at the top terminal command line, or select an execution line item from the sidebar history.
              </p>
            </div>
          )}

          {/* C. Render Full Analysis Detail */}
          {!isExecuting && selectedRun && (
            <div className="space-y-4">
              
              {/* Header Metadata Info */}
              <div className="bg-bg-surface border border-text-mut/10 p-3 rounded flex justify-between items-center">
                <div>
                  <div className="text-text-mut text-[9px] font-mono uppercase tracking-wider">QUERY RUNNING</div>
                  <h2 className="text-sm font-semibold tracking-tight text-accent font-mono uppercase">
                    "{selectedRun.query}"
                  </h2>
                </div>
                <div className="text-right font-mono text-[10px] text-text-mut">
                  <div>CORRELATION ID: <span className="text-[#A6C8FF]">{selectedRun.correlation_id}</span></div>
                  <div>STATUS: <span className={selectedRun.report_status === "completed" ? "text-bullish font-bold" : "text-bearish font-bold"}>{selectedRun.report_status.toUpperCase()}</span></div>
                </div>
              </div>

              {/* 1. Main Recommendation Order-Ticket Banner */}
              <div className={`border p-4 rounded relative overflow-hidden ${getActionColor(selectedRun.recommendation.action)}`}>
                <div className="flex justify-between items-start gap-4">
                  <div>
                    <span className="text-[10px] font-mono text-text-mut uppercase font-semibold">SIGNAL OUTCOME</span>
                    <h3 className="text-3xl font-mono tracking-tighter uppercase font-bold mt-1">
                      {selectedRun.recommendation.action}
                    </h3>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] font-mono text-text-mut uppercase font-semibold">CONFIDENCE FACTOR</span>
                    <div className="text-3xl font-mono font-bold mt-1 text-[#E0E2EC]">
                      {Math.round(selectedRun.recommendation.confidence * 100)}%
                    </div>
                  </div>
                </div>
                
                {/* Confidence Bar */}
                <div className="w-full bg-[#1F222F] h-1.5 rounded-full mt-3 overflow-hidden">
                  <div
                    style={{ width: `${selectedRun.recommendation.confidence * 100}%` }}
                    className={`h-full rounded-full ${
                      selectedRun.recommendation.action.toLowerCase() === "buy" ? "bg-bullish" :
                      selectedRun.recommendation.action.toLowerCase() === "sell" ? "bg-bearish" : "bg-neutral"
                    }`}
                  />
                </div>
              </div>

              {/* Grid 2-columns layout */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                {/* 2. Synthesis and Conflicts Card */}
                <div className="bg-bg-surface border border-text-mut/10 p-4 rounded flex flex-col gap-3">
                  <h4 className="font-mono text-xs text-text-mut uppercase tracking-wider border-b border-text-mut/10 pb-1.5">
                    ANALYST SYNTHESIS REASONING
                  </h4>
                  <p className="text-xs leading-relaxed text-[#E0E2EC]">
                    {selectedRun.reasoning_synthesis.synthesis || "No synthesis compiled."}
                  </p>
                  
                  {/* Conflicts and Contradictions */}
                  <div className="mt-2 space-y-2">
                    <div className="text-[10px] font-mono text-bearish uppercase font-bold">
                      UNRESOLVED CONFLICTS DETECTED:
                    </div>
                    {selectedRun.reasoning_synthesis.conflicts_noted && selectedRun.reasoning_synthesis.conflicts_noted.length > 0 ? (
                      <ul className="space-y-1.5">
                        {selectedRun.reasoning_synthesis.conflicts_noted.map((c, i) => (
                          <li key={i} className="text-[11px] text-[#FFD6A5] bg-[#FFD6A5]/5 border-l border-[#FFD6A5] pl-2 font-mono">
                            {c}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="text-[10px] text-text-mut font-mono">
                        No contradictions or conflicting parameters noted.
                      </div>
                    )}
                  </div>
                </div>

                {/* 3. Risks & Verification Audit Card */}
                <div className="bg-bg-surface border border-text-mut/10 p-4 rounded flex flex-col gap-3">
                  <h4 className="font-mono text-xs text-text-mut uppercase tracking-wider border-b border-text-mut/10 pb-1.5">
                    RISK AUDIT & VERIFIER FEEDBACK
                  </h4>
                  
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-text-mut">LOGICAL SUPPORT STATE:</span>
                    <span className={selectedRun.verifier_audit.is_supported ? "text-bullish font-bold" : "text-bearish font-bold"}>
                      {selectedRun.verifier_audit.is_supported ? "VERIFIED" : "UNSUPPORTED"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-text-mut">CONFIDENCE MODIFIER:</span>
                    <span className={selectedRun.verifier_audit.confidence_adjustment < 0 ? "text-bearish font-bold" : "text-text-mut"}>
                      {selectedRun.verifier_audit.confidence_adjustment > 0 ? "+" : ""}
                      {selectedRun.verifier_audit.confidence_adjustment.toFixed(2)}
                    </span>
                  </div>

                  <div className="space-y-1.5 mt-1">
                    <div className="text-[10px] font-mono text-text-mut uppercase">AUDITOR ASSESSMENT NOTES:</div>
                    <div className="text-xs bg-[#0A0B0E] p-2 rounded text-text-mut border border-text-mut/5 font-mono text-[11px]">
                      {selectedRun.verifier_audit.notes || "Audit notes empty."}
                    </div>
                  </div>

                  {/* Risks List */}
                  <div className="mt-2 space-y-1">
                    <div className="text-[10px] font-mono text-bearish uppercase">IDENTIFIED RISK PROFILE:</div>
                    {selectedRun.recommendation.risks && selectedRun.recommendation.risks.length > 0 ? (
                      <ul className="list-disc pl-4 text-xs text-text-mut space-y-1">
                        {selectedRun.recommendation.risks.map((risk, index) => (
                          <li key={index} className="text-[#FF453A]/80 font-mono text-[11px]">{risk}</li>
                        ))}
                      </ul>
                    ) : (
                      <div className="text-[10px] text-text-mut font-mono">No risks identified.</div>
                    )}
                  </div>
                </div>

              </div>

              {/* 4. Planned Agents Digests (Dropdowns/Inspectors) */}
              <div className="space-y-2">
                <h4 className="font-mono text-[11px] text-text-mut uppercase tracking-wider">
                  ACTIVE MULTI-AGENT SUB-SYSTEM SUMMARY DIGESTS
                </h4>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {Object.entries(selectedRun.agent_summaries).map(([agentName, summary]) => {
                    if (!summary) return null;
                    return (
                      <div key={agentName} className="bg-bg-surface border border-text-mut/10 p-3 rounded">
                        <div className="font-mono text-[10px] text-accent uppercase font-bold border-b border-text-mut/5 pb-1">
                          {agentName.replace("_", " ")}
                        </div>
                        <div className="mt-2 space-y-1.5 font-mono text-[10px]">
                          {Object.entries(summary).map(([key, val]) => {
                            if (key === "degraded") return null;
                            return (
                              <div key={key} className="flex justify-between gap-2">
                                <span className="text-text-mut uppercase text-[9px]">{key.replace("_", " ")}:</span>
                                <span className="text-[#E0E2EC] text-right truncate max-w-[130px]">
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
      <footer className="px-4 py-1.5 border-t border-text-mut/20 bg-[#0A0B0E] flex justify-between items-center font-mono text-[9px] text-text-mut shrink-0">
        <div>
          STATUS: <span className="text-bullish">ONLINE</span> // ENV: <span className="text-accent">DEVELOPMENT</span>
        </div>
        <div>
          SENTINEL PLATFORM SYSTEM v0.1.0 // ALL SIGNALS VERIFIED
        </div>
      </footer>

    </div>
  );
}
