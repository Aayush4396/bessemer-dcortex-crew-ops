import React from 'react';
import { Plane, ShieldCheck, Activity, Cpu, Clock } from 'lucide-react';

export default function Navbar({ stats, backendStatus }) {
  return (
    <header className="h-16 bg-slate-900/90 border-b border-slate-800 px-6 flex items-center justify-between backdrop-blur-md sticky top-0 z-30">
      {/* Brand & Logo */}
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Plane className="w-6 h-6 text-white transform -rotate-45" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-bold text-lg tracking-tight text-white font-mono">dCortex</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 border border-blue-500/40 text-blue-400 font-medium">
              Crew Ops Advisor
            </span>
          </div>
          <p className="text-[11px] text-slate-400">Network Operations Control (NOC) Desk</p>
        </div>
      </div>

      {/* Real-time Status Badges */}
      <div className="flex items-center space-x-4">
        {/* Regulatory Badge */}
        <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>DGCA CAR Sec 7 Ser J</span>
        </div>

        {/* Snapshot Date Badge */}
        <div className="hidden sm:flex items-center space-x-2 px-3 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>Snapshot: <strong className="text-white font-mono">{stats?.snapshot_date || '2026-09-14'}</strong></span>
        </div>

        {/* LLM Engine Badge */}
        <div className="flex items-center space-x-2 px-3 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300">
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
          <span>Model: <strong className="text-white">Sarvam-105B</strong></span>
        </div>

        {/* Live Backend Connection Indicator */}
        <div className="flex items-center space-x-2 px-3 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${backendStatus ? 'bg-emerald-400' : 'bg-rose-400'} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${backendStatus ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
          </span>
          <span className={backendStatus ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'}>
            {backendStatus ? 'Backend Live' : 'Connecting...'}
          </span>
        </div>
      </div>
    </header>
  );
}
