import React from 'react';
import { 
  AlertTriangle, 
  Zap, 
  ArrowRight, 
  Clock, 
  IndianRupee, 
  ShieldAlert, 
  MessageSquare,
  Sparkles,
  PlaneTakeoff,
  UserX
} from 'lucide-react';

export function Tier2Placeholder({ onSwitchToTier1 }) {
  const scenarios = [
    {
      id: 'S1',
      title: 'Unscheduled Sick Call (Capt C-1042 on DX412)',
      trigger: 'Reported 2h prior to report time at BLR',
      impact: 'Grounds flight DX412 and downstream pairing P-2291 unless replacement assigned.',
      severity: 'Critical',
      color: 'border-rose-500/40 bg-rose-500/5',
    },
    {
      id: 'S2',
      title: '2-Hour Technical Delay at DEL',
      trigger: 'Aircraft VT-DXA maintenance delay',
      impact: 'Cascading duty extension breaches FDP limits on flight DX402.',
      severity: 'High',
      color: 'border-amber-500/40 bg-amber-500/5',
    },
    {
      id: 'S3',
      title: 'Airport Weather Closure (BOM Dense Fog)',
      trigger: 'Zero-visibility CAT-III closure 04:00-08:00 UTC',
      impact: 'Diverts incoming flights, stranding 4 operating crews out of base.',
      severity: 'High',
      color: 'border-amber-500/40 bg-amber-500/5',
    },
    {
      id: 'S4',
      title: 'En-route Pressurization Snag Diversion',
      trigger: 'Diversion to HYD alternate station',
      impact: 'Crew exceeds max duty hours; duty clock must reset with mandatory rest.',
      severity: 'Medium',
      color: 'border-blue-500/40 bg-blue-500/5',
    },
    {
      id: 'S5',
      title: 'In-flight Medical Emergency Diversion',
      trigger: 'Passenger medical distress on DX588',
      impact: 'FDP ceiling exceeded; requires fresh replacement crew callout.',
      severity: 'High',
      color: 'border-amber-500/40 bg-amber-500/5',
    },
    {
      id: 'S6',
      title: 'Mid-Rotation Certification Expiration',
      trigger: 'FO C-2087 medical expires mid-pairing',
      impact: 'Legally grounds first officer from operating scheduled return legs.',
      severity: 'Critical',
      color: 'border-rose-500/40 bg-rose-500/5',
    },
  ];

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 animate-fadeIn">
      {/* Banner */}
      <div className="bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent p-6 rounded-2xl border border-amber-500/30 flex items-start justify-between">
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase tracking-wider">
              Step 5 Module — Preview
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Tier 2: Disruption Consequence Simulator
          </h1>
          <p className="text-sm text-slate-300 max-w-2xl">
            Simulates cascading network consequences when disruptions occur. Propagates technical delays, 
            sick calls, and airport closures across pairings and evaluates immediate CAR legality breaches.
          </p>
        </div>

        <button
          onClick={onSwitchToTier1}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center space-x-2 transition-all shadow-lg shadow-blue-500/20 shrink-0"
        >
          <span>Go to Tier 1 Chat</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Disruption Scenarios Grid */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold tracking-wider text-slate-400 uppercase flex items-center space-x-2">
          <span>Target Scenarios in Dataset (S1 – S6)</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {scenarios.map((s) => (
            <div
              key={s.id}
              className={`p-5 rounded-xl border ${s.color} space-y-3 transition-all hover:scale-[1.01]`}
            >
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-cyan-400 font-mono text-xs font-bold">
                  {s.id}
                </span>
                <span className="text-xs font-semibold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                  {s.severity}
                </span>
              </div>
              <h3 className="font-semibold text-white text-sm">{s.title}</h3>
              <div className="space-y-1 text-xs text-slate-400">
                <p><strong className="text-slate-300">Trigger:</strong> {s.trigger}</p>
                <p><strong className="text-slate-300">Ripple Impact:</strong> {s.impact}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function Tier3Placeholder({ onSwitchToTier1 }) {
  const pillars = [
    {
      title: '1. Candidate Pool Generation',
      desc: 'Discovers eligible crew across home-base standbys, active reserves, and off-duty line pilots with reachability times.',
      icon: UserX,
      color: 'text-cyan-400',
    },
    {
      title: '2. CAR Legality Pre-Filter',
      desc: 'Deterministic Python evaluation of FDP limits, rolling 7d/28d caps, minimum rest, and aircraft type ratings.',
      icon: ShieldAlert,
      color: 'text-emerald-400',
    },
    {
      title: '3. Exact INR Cost Optimization',
      desc: 'Calculates exact recovery costs combining reserve callout fees, positioning deadheads, and hotel accommodations.',
      icon: IndianRupee,
      color: 'text-amber-400',
    },
    {
      title: '4. WhatsApp & SMS Notification Drafter',
      desc: 'Pre-drafts personalized operational duty summons with reporting times, gate assignments, and acknowledgment links.',
      icon: MessageSquare,
      color: 'text-indigo-400',
    },
  ];

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 animate-fadeIn">
      {/* Banner */}
      <div className="bg-gradient-to-r from-blue-500/10 via-blue-500/5 to-transparent p-6 rounded-2xl border border-blue-500/30 flex items-start justify-between">
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <Zap className="w-5 h-5 text-blue-400" />
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 uppercase tracking-wider">
              Step 6 Module — Preview
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Tier 3: Recovery Candidate Ranker & Cost Optimizer
          </h1>
          <p className="text-sm text-slate-300 max-w-2xl">
            Solves disruptions by evaluating replacement candidates, ensuring 100% DGCA CAR compliance, 
            ranking solutions by lowest net operational cost in INR, and generating automated notification drafts.
          </p>
        </div>

        <button
          onClick={onSwitchToTier1}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center space-x-2 transition-all shadow-lg shadow-blue-500/20 shrink-0"
        >
          <span>Go to Tier 1 Chat</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {pillars.map((p, idx) => {
          const Icon = p.icon;
          return (
            <div key={idx} className="bg-slate-900/60 p-6 rounded-xl border border-slate-800 space-y-3">
              <div className="flex items-center space-x-3">
                <div className="p-2.5 rounded-lg bg-slate-800 border border-slate-700/60">
                  <Icon className={`w-5 h-5 ${p.color}`} />
                </div>
                <h3 className="font-semibold text-white text-sm">{p.title}</h3>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed pl-12">{p.desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
