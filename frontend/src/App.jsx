import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import ChatConsole from './components/ChatConsole';
import { Tier2Placeholder, Tier3Placeholder } from './components/TierPlaceholders';

export default function App() {
  const [activeTier, setActiveTier] = useState(1);
  const [stats, setStats] = useState(null);
  const [backendStatus, setBackendStatus] = useState(false);

  useEffect(() => {
    // Fetch stats and check backend health
    const checkBackend = async () => {
      try {
        const healthRes = await fetch('/api/health');
        if (healthRes.ok) {
          setBackendStatus(true);
          const statsRes = await fetch('/api/stats');
          if (statsRes.ok) {
            const statsData = await statsRes.json();
            setStats(statsData);
          }
        } else {
          setBackendStatus(false);
        }
      } catch (err) {
        console.warn('Backend server not detected on /api/health:', err);
        setBackendStatus(false);
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-[#070a12] text-slate-100 overflow-hidden select-none">
      {/* Top Operations Header */}
      <Navbar stats={stats} backendStatus={backendStatus} />

      {/* Main Operations Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Workflow Switcher & Fleet Stats Sidebar */}
        <Sidebar 
          activeTier={activeTier} 
          setActiveTier={setActiveTier} 
          stats={stats} 
        />

        {/* Dynamic Workflow Area */}
        <main className="flex-1 flex overflow-hidden bg-slate-950/20">
          {activeTier === 1 && <ChatConsole />}
          {activeTier === 2 && <Tier2Placeholder onSwitchToTier1={() => setActiveTier(1)} />}
          {activeTier === 3 && <Tier3Placeholder onSwitchToTier1={() => setActiveTier(1)} />}
        </main>
      </div>
    </div>
  );
}
