import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
  Terminal, 
  CheckCircle2, 
  Database, 
  Cpu, 
  Code2 
} from 'lucide-react';

export default function AuditDrawer({ toolCalls = [], toolResults = [], reasoningTrace = [] }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('trace'); // 'trace' | 'tools' | 'raw'

  if ((!toolCalls || toolCalls.length === 0) && (!reasoningTrace || reasoningTrace.length === 0)) {
    return null;
  }

  return (
    <div className="mt-3 border border-slate-700/60 rounded-xl overflow-hidden bg-slate-900/60 backdrop-blur-sm text-xs">
      {/* Accordion Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 bg-slate-800/40 hover:bg-slate-800/70 transition-colors flex items-center justify-between text-slate-300 font-medium"
      >
        <div className="flex items-center space-x-2.5">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <span>Explainability & LangGraph Tool Audit</span>
          <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-[10px] text-cyan-300 font-mono">
            {toolCalls.length} tool call(s)
          </span>
          <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-[10px] text-emerald-400 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>Deterministic Math</span>
          </span>
        </div>
        <div className="flex items-center space-x-1 text-slate-400">
          <span className="text-[11px]">{isOpen ? 'Hide Audit Trail' : 'View Audit Trail'}</span>
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {/* Accordion Body */}
      {isOpen && (
        <div className="p-4 border-t border-slate-800 space-y-4">
          {/* Sub-tabs */}
          <div className="flex space-x-2 border-b border-slate-800 pb-2">
            <button
              onClick={() => setActiveTab('trace')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                activeTab === 'trace'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              Reasoning Trace ({reasoningTrace.length})
            </button>
            <button
              onClick={() => setActiveTab('tools')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                activeTab === 'tools'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              Tool Calls ({toolCalls.length})
            </button>
            <button
              onClick={() => setActiveTab('raw')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                activeTab === 'raw'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              Raw SQLite Outputs ({toolResults.length})
            </button>
          </div>

          {/* Tab 1: Reasoning Trace */}
          {activeTab === 'trace' && (
            <div className="space-y-2">
              <div className="text-[11px] text-slate-400 mb-1">
                Step-by-step operational log recorded by LangGraph state machine:
              </div>
              <ol className="space-y-1.5 pl-2">
                {reasoningTrace.map((step, idx) => (
                  <li key={idx} className="flex items-start space-x-2 text-slate-300 font-mono text-[11px]">
                    <span className="w-5 h-5 rounded-full bg-slate-800 text-cyan-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                      {idx + 1}
                    </span>
                    <span className="bg-slate-950/80 px-2.5 py-1 rounded border border-slate-800/80 w-full leading-relaxed">
                      {step}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Tab 2: Dispatched Tool Calls */}
          {activeTab === 'tools' && (
            <div className="space-y-3">
              {toolCalls.map((tc, idx) => (
                <div key={idx} className="bg-slate-950 rounded-lg p-3 border border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-cyan-400 font-semibold font-mono text-xs">{tc.name}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{tc.id}</span>
                  </div>
                  <div className="text-[11px] text-slate-400">Parameters Dispatched:</div>
                  <pre className="bg-slate-900/90 p-2 rounded border border-slate-800/80 text-[11px] font-mono text-amber-300 overflow-x-auto">
                    {JSON.stringify(tc.args, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}

          {/* Tab 3: Raw SQLite Outputs */}
          {activeTab === 'raw' && (
            <div className="space-y-3">
              {toolResults.map((tr, idx) => (
                <div key={idx} className="bg-slate-950 rounded-lg p-3 border border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-emerald-400 font-semibold font-mono text-xs">{tr.tool_name}</span>
                    <span className="text-[10px] text-slate-500">Source: SQLite DB</span>
                  </div>
                  <pre className="bg-slate-900/90 p-2 rounded border border-slate-800/80 text-[11px] font-mono text-emerald-300 max-h-60 overflow-y-auto">
                    {JSON.stringify(tr.result, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
