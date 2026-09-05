import React, { useState } from 'react';
import { 
  MessageSquare, 
  Plus, 
  Trash2, 
  Search, 
  Clock, 
  ChevronLeft, 
  ChevronRight,
  Database
} from 'lucide-react';

export default function SessionSidebar({
  sessions = [],
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isCollapsed,
  setIsCollapsed,
  isLoadingSessions = false,
}) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredSessions = sessions.filter((s) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (s.title && s.title.toLowerCase().includes(term)) ||
      (s.session_id && s.session_id.toLowerCase().includes(term))
    );
  });

  const formatTimestamp = (ts) => {
    if (!ts) return '';
    try {
      // Handles both ISO '2026-09-05 12:04:00' and standard formats
      const date = new Date(ts.replace(' ', 'T'));
      if (isNaN(date.getTime())) return ts.slice(11, 16);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return ts.slice(11, 16);
    }
  };

  if (isCollapsed) {
    return (
      <aside className="w-14 bg-[#070b16] border-r border-slate-800/80 flex flex-col items-center py-4 space-y-4 shrink-0 transition-all duration-200">
        <button
          onClick={() => setIsCollapsed(false)}
          className="p-2 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Expand Session History"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        <button
          onClick={onNewSession}
          className="p-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition-all"
          title="New Operational Inquiry"
        >
          <Plus className="w-4 h-4" />
        </button>

        <div className="w-8 h-px bg-slate-800" />

        <div className="flex-1 overflow-y-auto space-y-2 w-full px-2 flex flex-col items-center">
          {sessions.slice(0, 8).map((s) => (
            <button
              key={s.session_id}
              onClick={() => onSelectSession(s.session_id)}
              className={`w-9 h-9 rounded-lg flex items-center justify-center text-xs transition-all ${
                s.session_id === activeSessionId
                  ? 'bg-blue-600/30 border border-blue-500 text-blue-300 font-bold'
                  : 'bg-slate-900/60 hover:bg-slate-800 text-slate-400 border border-slate-800'
              }`}
              title={s.title || 'Inquiry'}
            >
              <MessageSquare className="w-3.5 h-3.5" />
            </button>
          ))}
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-72 bg-[#070b16]/95 backdrop-blur-md border-r border-slate-800/80 flex flex-col h-full shrink-0 transition-all duration-200">
      {/* Sidebar Header */}
      <div className="p-3.5 border-b border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-md bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <MessageSquare className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            Inquiry History
          </span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 border border-slate-700/60 font-mono">
            {sessions.length}
          </span>
        </div>

        <button
          onClick={() => setIsCollapsed(true)}
          className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          title="Collapse Sidebar"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* New Inquiry Action */}
      <div className="p-3 border-b border-slate-800/50">
        <button
          onClick={onNewSession}
          className="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 flex items-center justify-center space-x-2 transition-all active:scale-[0.98]"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Inquiry Session</span>
        </button>
      </div>

      {/* Filter / Search Box */}
      <div className="px-3 pt-2 pb-1">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search inquiries..."
            className="w-full bg-slate-950/70 border border-slate-800/80 focus:border-blue-500/60 rounded-lg pl-8 pr-2.5 py-1.5 text-[11px] text-slate-200 placeholder:text-slate-500 outline-none transition-all"
          />
        </div>
      </div>

      {/* Scrollable Session List */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1.5">
        {isLoadingSessions && sessions.length === 0 ? (
          <div className="p-4 text-center text-slate-500 text-xs">
            Loading sessions...
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="p-6 text-center text-slate-500 text-xs space-y-1">
            <p className="font-medium text-slate-400">No sessions found</p>
            <p className="text-[10px]">Start a new operational query to create a persistent thread.</p>
          </div>
        ) : (
          filteredSessions.map((sess) => {
            const isActive = sess.session_id === activeSessionId;
            return (
              <div
                key={sess.session_id}
                onClick={() => onSelectSession(sess.session_id)}
                className={`group relative flex flex-col p-2.5 rounded-xl text-xs transition-all cursor-pointer border ${
                  isActive
                    ? 'bg-blue-600/15 border-blue-500/40 text-white shadow-sm'
                    : 'bg-slate-900/40 hover:bg-slate-800/60 text-slate-300 border-slate-800/50 hover:border-slate-700/60'
                }`}
              >
                {/* Top Row: Title + Delete action */}
                <div className="flex items-center justify-between pr-5">
                  <span className="font-semibold text-xs truncate max-w-[170px] group-hover:text-white transition-colors">
                    {sess.title || 'Untitled Session'}
                  </span>
                </div>

                {/* Bottom Row: Timestamp + Message count badge */}
                <div className="flex items-center justify-between mt-1 text-[10px] text-slate-400">
                  <div className="flex items-center space-x-1">
                    <Clock className="w-2.5 h-2.5 text-slate-500" />
                    <span>{formatTimestamp(sess.updated_at || sess.created_at)}</span>
                  </div>

                  <span className="px-1.5 py-0.2 rounded bg-slate-800/80 border border-slate-700/50 text-[9px] font-mono text-slate-400">
                    {sess.message_count || 0} msg{(sess.message_count || 0) === 1 ? '' : 's'}
                  </span>
                </div>

                {/* Delete button on hover */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(sess.session_id, e);
                  }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity absolute right-2 top-2.5 p-1 rounded-md hover:bg-red-500/20 text-slate-400 hover:text-red-400"
                  title="Delete Session"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Storage Footer */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/40 flex items-center justify-between text-[10px] text-slate-400">
        <div className="flex items-center space-x-1.5">
          <Database className="w-3 h-3 text-cyan-400" />
          <span className="font-mono text-[10px] text-slate-400">crew_ops.db</span>
        </div>
        <div className="flex items-center space-x-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-slate-400 font-medium">Persisted</span>
        </div>
      </div>
    </aside>
  );
}
