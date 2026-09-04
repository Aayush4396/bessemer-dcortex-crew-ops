import React from 'react';
import { 
  Compass, 
  AlertTriangle, 
  Zap, 
  Users, 
  Plane, 
  ShieldAlert, 
  Layers, 
  Database,
  Building2
} from 'lucide-react';

export default function Sidebar({ activeTier, setActiveTier, stats }) {
  const tiers = [
    {
      id: 1,
      title: 'Tier 1: Operations Advisory',
      desc: 'Fact retrieval & roster lookups',
      icon: Compass,
      status: 'active',
      badge: 'Active Live',
      badgeColor: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    },
    {
      id: 2,
      title: 'Tier 2: Disruption Simulator',
      desc: 'Consequence analysis & ripple cascade',
      icon: AlertTriangle,
      status: 'placeholder',
      badge: 'Step 5',
      badgeColor: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    },
    {
      id: 3,
      title: 'Tier 3: Recovery Optimizer',
      desc: 'CAR legality ranking & INR costs',
      icon: Zap,
      status: 'placeholder',
      badge: 'Step 6',
      badgeColor: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    },
  ];

  return (
    <aside className="w-72 bg-slate-900/60 border-r border-slate-800 flex flex-col justify-between p-4 backdrop-blur-sm">
      {/* Tier Switcher Navigation */}
      <div className="space-y-6">
        <div>
          <h2 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-3 px-2">
            Operations Workflows
          </h2>
          <nav className="space-y-2">
            {tiers.map((t) => {
              const Icon = t.icon;
              const isActive = activeTier === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTier(t.id)}
                  className={`w-full text-left p-3 rounded-xl border transition-all duration-200 flex flex-col space-y-1.5 ${
                    isActive
                      ? 'bg-blue-600/15 border-blue-500/50 shadow-md shadow-blue-500/5'
                      : 'bg-slate-800/30 border-slate-800/60 hover:bg-slate-800/60 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2.5">
                      <Icon className={`w-4 h-4 ${isActive ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span className={`text-sm font-semibold ${isActive ? 'text-white' : 'text-slate-200'}`}>
                        Tier {t.id}
                      </span>
                    </div>
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${t.badgeColor}`}>
                      {t.badge}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 font-medium pl-6">{t.title.split(':')[1]}</p>
                  <p className="text-[11px] text-slate-500 pl-6 leading-tight">{t.desc}</p>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Database & Fleet Status Card */}
        <div className="bg-slate-800/40 rounded-xl p-3.5 border border-slate-700/50 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-300">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span>Operational Datasets (SQLite)</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div className="flex items-center space-x-1.5 text-slate-400 mb-0.5">
                <Plane className="w-3 h-3" />
                <span className="text-[11px]">Flights</span>
              </div>
              <span className="text-base font-bold text-white font-mono">{stats?.flights || 147}</span>
            </div>

            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div className="flex items-center space-x-1.5 text-slate-400 mb-0.5">
                <Users className="w-3 h-3" />
                <span className="text-[11px]">Crew</span>
              </div>
              <span className="text-base font-bold text-white font-mono">{stats?.crew || 150}</span>
            </div>

            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div className="flex items-center space-x-1.5 text-slate-400 mb-0.5">
                <ShieldAlert className="w-3 h-3" />
                <span className="text-[11px]">Reserves</span>
              </div>
              <span className="text-base font-bold text-white font-mono">{stats?.reserves || 112}</span>
            </div>

            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div className="flex items-center space-x-1.5 text-slate-400 mb-0.5">
                <Layers className="w-3 h-3" />
                <span className="text-[11px]">Pairings</span>
              </div>
              <span className="text-base font-bold text-white font-mono">{stats?.pairings || 42}</span>
            </div>
          </div>

          <div className="pt-1 border-t border-slate-700/40 flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center space-x-1">
              <Building2 className="w-3 h-3 text-slate-500" />
              <span>Hubs:</span>
            </span>
            <span className="font-mono text-slate-300">BLR | BOM | DEL</span>
          </div>
        </div>
      </div>

      {/* Controller Desk Footer */}
      <div className="text-[11px] text-slate-500 border-t border-slate-800 pt-3 flex items-center justify-between">
        <span>Airline OCC Desk v1.0</span>
        <span className="text-blue-400 font-mono">Bessemer dCortex</span>
      </div>
    </aside>
  );
}
