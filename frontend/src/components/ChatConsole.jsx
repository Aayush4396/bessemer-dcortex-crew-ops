import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Bot, 
  User, 
  Sparkles, 
  Loader2, 
  Plane, 
  Clock, 
  ShieldAlert, 
  RotateCcw,
  Search
} from 'lucide-react';
import AuditDrawer from './AuditDrawer';

export default function ChatConsole() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: `👋 **Welcome to the dCortex Crew Operations Control Desk.**\n\nI am your AI Operations Advisor powered by **LangGraph** and **Sarvam-105B**, operating over live flight schedules, crew rosters, and DGCA CAR Section 7 regulations.\n\nAsk me any operational lookup question or click one of the quick inquiry chips below.`,
      toolCalls: [],
      toolResults: [],
      reasoningTrace: [
        'Initialized dCortex Crew Operations Control Desk',
        'Ready for controller queries across 147 flights, 150 crew, and 112 reserves'
      ],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const quickPrompts = [
    { label: '✈️ DX412 Aircraft & Seats', query: 'Which aircraft operates flight DX412 on 2026-09-15 and how many seats does it have?' },
    { label: '👨‍✈️ BLR Reserves (Sep 15)', query: 'Who is on reserve at BLR on 2026-09-15, and what are their on-call windows?' },
    { label: '⏱️ C-1042 7d Duty & Headroom', query: 'How many duty hours has C-1042 accrued in the 7 days ending 2026-09-14, and what is the remaining headroom?' },
    { label: '⚠️ C-1042 Risk Score & Drivers', query: 'What is the disruption risk score for C-1042 and what operational factors drive it?' },
    { label: '📋 Expiring Certifications (30d)', query: 'List all crew certifications expiring within 30 days of 2026-09-15.' },
    { label: '🛫 DEL Departures (Sep 15)', query: 'Which flights depart DEL on 2026-09-15?' },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (queryText) => {
    const textToSend = queryText || inputQuery;
    if (!textToSend.trim() || isLoading) return;

    const userMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuery('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: textToSend, tier: 1 }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: data.response,
        toolCalls: data.tool_calls || [],
        toolResults: data.tool_results || [],
        reasoningTrace: data.reasoning_trace || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `⚠️ **Operational Connection Error:** Unable to reach backend agent: ${err.message}`,
        toolCalls: [],
        toolResults: [],
        reasoningTrace: ['Failed to reach FastAPI backend on http://127.0.0.1:8000'],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Helper to format tables and markdown lines
  const formatText = (text) => {
    const lines = text.split('\n');
    let inTable = false;
    let tableRows = [];
    const elements = [];

    lines.forEach((line, index) => {
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        // Table line
        if (!inTable) inTable = true;
        tableRows.push(line.trim());
      } else {
        if (inTable) {
          // Render accumulated table
          elements.push(renderTable(tableRows, `table-${index}`));
          tableRows = [];
          inTable = false;
        }

        if (line.trim().startsWith('###')) {
          elements.push(<h3 key={index} className="text-sm font-bold text-white mt-3 mb-1">{line.replace('###', '').trim()}</h3>);
        } else if (line.trim().startsWith('##')) {
          elements.push(<h2 key={index} className="text-base font-bold text-white mt-4 mb-1">{line.replace('##', '').trim()}</h2>);
        } else if (line.trim().startsWith('-') || line.trim().startsWith('*')) {
          elements.push(
            <li key={index} className="text-slate-300 ml-4 list-disc text-xs leading-relaxed">
              {renderFormattedInline(line.substring(1).trim())}
            </li>
          );
        } else if (line.trim() === '') {
          elements.push(<div key={index} className="h-1.5" />);
        } else {
          elements.push(
            <p key={index} className="text-slate-200 text-xs leading-relaxed">
              {renderFormattedInline(line)}
            </p>
          );
        }
      }
    });

    if (inTable && tableRows.length > 0) {
      elements.push(renderTable(tableRows, 'table-end'));
    }

    return elements;
  };

  const renderTable = (rows, key) => {
    if (rows.length < 2) return null;
    const headerRow = rows[0].split('|').filter(c => c.trim() !== '').map(c => c.trim());
    // row 1 is divider (|---|---|)
    const bodyRows = rows.slice(2).map(r => r.split('|').filter(c => c.trim() !== '').map(c => c.trim()));

    return (
      <div key={key} className="my-3 overflow-x-auto rounded-lg border border-slate-700/80 bg-slate-950/70">
        <table className="w-full text-left text-xs border-collapse font-sans">
          <thead>
            <tr className="bg-slate-800/80 text-slate-300 border-b border-slate-700">
              {headerRow.map((h, i) => (
                <th key={i} className="py-2 px-3 font-semibold text-[11px] uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-slate-200">
            {bodyRows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-slate-800/40 transition-colors">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="py-2 px-3 text-[11px] font-mono">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderFormattedInline = (text) => {
    // Basic bold **text** parsing
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={idx} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-4rem)] bg-slate-950/40">
      {/* Quick Action Chips */}
      <div className="px-6 py-3 border-b border-slate-800/60 bg-slate-900/30 overflow-x-auto flex items-center space-x-2 shrink-0">
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider shrink-0 mr-2 flex items-center space-x-1">
          <Sparkles className="w-3.5 h-3.5 text-blue-400" />
          <span>Quick Inquiries:</span>
        </span>
        {quickPrompts.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(p.query)}
            disabled={isLoading}
            className="px-3 py-1 rounded-full bg-slate-800/70 hover:bg-blue-600/20 hover:border-blue-500/50 border border-slate-700/60 text-slate-300 text-xs whitespace-nowrap transition-all duration-150 disabled:opacity-50"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Message Feed */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex items-start space-x-3.5 ${m.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-md ${
                m.sender === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 border border-slate-700 text-cyan-400'
              }`}
            >
              {m.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Bubble */}
            <div className={`max-w-3xl space-y-1 ${m.sender === 'user' ? 'text-right' : ''}`}>
              <div className="flex items-center space-x-2 text-[11px] text-slate-400">
                <span className="font-semibold text-slate-300">
                  {m.sender === 'user' ? 'Crew Controller' : 'dCortex AI Advisor'}
                </span>
                <span>•</span>
                <span>{m.timestamp}</span>
              </div>

              <div
                className={`p-4 rounded-2xl border text-xs shadow-md ${
                  m.sender === 'user'
                    ? 'bg-blue-600 text-white border-blue-500 rounded-tr-none'
                    : 'bg-slate-900/90 text-slate-200 border-slate-800 rounded-tl-none space-y-2'
                }`}
              >
                {m.sender === 'user' ? (
                  <p className="text-sm font-medium">{m.text}</p>
                ) : (
                  <div>{formatText(m.text)}</div>
                )}

                {/* Explainability / Tool Audit Drawer */}
                {m.sender === 'assistant' && (m.toolCalls?.length > 0 || m.reasoningTrace?.length > 0) && (
                  <AuditDrawer
                    toolCalls={m.toolCalls}
                    toolResults={m.toolResults}
                    reasoningTrace={m.reasoningTrace}
                  />
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Loading Bubble */}
        {isLoading && (
          <div className="flex items-start space-x-3.5 animate-pulse">
            <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 text-cyan-400 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 text-slate-400 text-xs rounded-tl-none flex items-center space-x-3">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              <span>Analyzing controller query & evaluating CAR regulations via LangGraph...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="p-4 bg-slate-900/80 border-t border-slate-800 backdrop-blur-md">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-3 max-w-5xl mx-auto"
        >
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-4 top-1/2 transform -translate-y-1/2" />
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask an operational lookup (e.g. 'Who is on reserve at BLR on Sep 15?' or 'DX412 aircraft details')..."
              disabled={isLoading}
              className="w-full bg-slate-950 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-white rounded-xl pl-11 pr-4 py-3 text-xs placeholder:text-slate-500 transition-all outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!inputQuery.trim() || isLoading}
            className="px-5 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-semibold rounded-xl flex items-center space-x-2 transition-all shadow-lg shadow-blue-500/20 shrink-0"
          >
            <span>Send Query</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
