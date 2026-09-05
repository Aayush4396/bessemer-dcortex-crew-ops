import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  Award,
  CheckCircle2,
  Clock,
  Copy,
  DollarSign,
  FileText,
  Layers,
  Play,
  Shield,
  ShieldAlert,
  Sparkles,
  Users,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { optimizeRecovery } from '@/lib/api'

const RECOVERY_PRESETS = [
  {
    id: 'S1',
    name: 'S1: ATR Captain Sick (P-2224)',
    desc: 'C-3231 sick call at 01:30Z; evaluate reserves, day-offs, and cancellation',
    event: {
      type: 'SICK_CREW',
      crew_id: 'C-3231',
      pairing_id: 'P-2224',
      reported_utc: '2026-09-16T01:30:00Z',
    },
  },
  {
    id: 'S2',
    name: 'S2: Flagship Captain Sick (P-2291)',
    desc: 'C-1042 out for 2-day rotation; reserve C-3310 vs DEL deadhead C-2210',
    event: {
      type: 'SICK_CREW',
      crew_id: 'C-1042',
      pairing_id: 'P-2291',
      reported_utc: '2026-09-15T05:00:00Z',
    },
  },
  {
    id: 'S4',
    name: 'S4: VT-DXA FDP Breach (DX404)',
    desc: '1.5h delay causes sector 4 breach; tail leg reserve set @ ₹75k vs cancel @ ₹250k',
    event: {
      type: 'DELAY',
      aircraft: 'VT-DXA',
      date: '2026-09-16',
      delay_hours: 1.5,
    },
  },
  {
    id: 'S5',
    name: 'S5: Preflight Cert Expiry (C-5417)',
    desc: 'Lapsed recurrent training on 17 Sep; replace with cabin reserve C-4809 @ ₹9,500',
    event: {
      type: 'CERT_EXPIRY',
      crew_id: 'C-5417',
      pairing_id: 'P-2213',
      date: '2026-09-19',
    },
  },
  {
    id: 'S6',
    name: 'S6: Multi-Sick Joint Optimization',
    desc: 'Joint combinatorial optimization for DXA + DXB minimizing total cost @ ₹42,500',
    event: {
      type: 'MULTI_SICK',
      events: [
        { crew_id: 'C-3940', pairing_id: 'P-2205', reported_utc: '2026-09-18T00:30:00Z' },
        { crew_id: 'C-1938', pairing_id: 'P-2212', reported_utc: '2026-09-18T00:30:00Z' },
      ],
    },
  },
]

export function RecoveryOptimizerPage() {
  const location = useLocation()
  const [selectedPreset, setSelectedPreset] = useState(RECOVERY_PRESETS[0].id)
  const [currentEvent, setCurrentEvent] = useState(
    location.state?.initialEvent || RECOVERY_PRESETS[0].event,
  )
  const [plan, setPlan] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [copiedNotification, setCopiedNotification] = useState(false)

  // Auto-run if passed from Disruption Simulator
  useEffect(() => {
    if (location.state?.initialEvent) {
      setCurrentEvent(location.state.initialEvent)
      runOptimization(location.state.initialEvent)
    }
  }, [location.state])

  const runOptimization = async (evtToRun) => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await optimizeRecovery(evtToRun || currentEvent)
      setPlan(data)
    } catch (err) {
      setError(err.message || 'Optimization failed')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectPreset = (preset) => {
    setSelectedPreset(preset.id)
    setCurrentEvent(preset.event)
    setPlan(null)
    setError(null)
  }

  const handleCopyNotification = (text) => {
    navigator.clipboard.writeText(text)
    setCopiedNotification(true)
    setTimeout(() => setCopiedNotification(false), 2000)
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-y-auto bg-[#eef1f5] p-6">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Recovery Optimizer</h1>
            <Badge variant="outline" className="border-indigo-200 bg-indigo-50 text-indigo-700">
              Tier 3 Multi-Objective Solver
            </Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Automated crew re-assignment, DGCA CAR rule validation, candidate ranking, financial costing, and dispatch callouts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={() => runOptimization(currentEvent)}
            disabled={isLoading}
            className="gap-2 bg-slate-900 text-white hover:bg-slate-800"
          >
            <Play className="h-4 w-4" />
            {isLoading ? 'Solving...' : 'Optimize Recovery'}
          </Button>
        </div>
      </div>

      {/* Preset Selector */}
      <div className="mb-6">
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          Operational Recovery Benchmarks
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {RECOVERY_PRESETS.map((preset) => {
            const isSelected = selectedPreset === preset.id
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => handleSelectPreset(preset)}
                className={`flex flex-col items-start rounded-xl border p-3.5 text-left transition-all ${
                  isSelected
                    ? 'border-indigo-500 bg-white shadow-md ring-2 ring-indigo-500/20'
                    : 'border-slate-200 bg-white/70 hover:border-slate-300 hover:bg-white'
                }`}
              >
                <div className="flex w-full items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">{preset.id}</span>
                  <Badge variant="secondary" className="text-[10px]">
                    {preset.event.type}
                  </Badge>
                </div>
                <p className="mt-1 text-xs font-semibold text-slate-800 line-clamp-1">{preset.name.split(': ')[1]}</p>
                <p className="mt-1 text-[11px] text-slate-500 line-clamp-2">{preset.desc}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Error Card */}
      {error && (
        <Card className="mb-6 border-rose-200 bg-rose-50 p-4 text-rose-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0" />
            <p className="text-sm font-medium">{error}</p>
          </div>
        </Card>
      )}

      {/* Optimized Recovery Plan Output */}
      {plan ? (
        <div className="space-y-6">
          {/* Top Recommendation Banner */}
          {plan.expected_choice && (
            <div className="rounded-xl border border-emerald-300 bg-gradient-to-r from-emerald-50 to-teal-50/50 p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm">
                    <Award className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-800">
                        Top Ranked Recovery Recommendation
                      </span>
                      <Badge className="bg-emerald-600 text-white">Rank 1</Badge>
                    </div>
                    <p className="text-base font-bold text-slate-900 mt-0.5">
                      {plan.expected_choice.action}
                    </p>
                    <p className="text-xs text-slate-600 mt-1">
                      {plan.expected_choice.reasoning || 'Evaluated across all 7 DGCA CAR rules and found completely legal.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase">Incremental Cost</span>
                    <p className="text-lg font-bold text-slate-900">
                      ₹{plan.expected_choice.cost_inr?.toLocaleString() ?? 0}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase">Departure Delay</span>
                    <p className="text-lg font-bold text-slate-900">
                      +{plan.expected_choice.delay_hours ?? 0}h
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Joint Combinatorial Plan (S6) */}
          {plan.optimal_joint_plan && (
            <Card className="p-5 bg-white border-indigo-200 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Layers className="h-5 w-5 text-indigo-600" />
                  <h3 className="text-sm font-bold text-slate-900">
                    S6 Optimal Joint Assignment (Global Minimum)
                  </h3>
                </div>
                <Badge className="bg-indigo-600 text-white text-xs">
                  Total: ₹{plan.optimal_joint_plan.total_cost_inr?.toLocaleString()}
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3.5 text-xs">
                  <span className="font-bold text-slate-500 uppercase text-[10px]">Rotation 1: VT-DXA</span>
                  <p className="font-bold text-slate-900 text-sm mt-1">
                    {plan.optimal_joint_plan.assign_dxa.action}
                  </p>
                  <div className="mt-2 flex justify-between text-slate-600">
                    <span>Cost: ₹{plan.optimal_joint_plan.assign_dxa.cost_inr?.toLocaleString()}</span>
                    <span>Delay: +{plan.optimal_joint_plan.assign_dxa.delay_hours}h</span>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3.5 text-xs">
                  <span className="font-bold text-slate-500 uppercase text-[10px]">Rotation 2: VT-DXB</span>
                  <p className="font-bold text-slate-900 text-sm mt-1">
                    {plan.optimal_joint_plan.assign_dxb.action}
                  </p>
                  <div className="mt-2 flex justify-between text-slate-600">
                    <span>Cost: ₹{plan.optimal_joint_plan.assign_dxb.cost_inr?.toLocaleString()}</span>
                    <span>Delay: +{plan.optimal_joint_plan.assign_dxb.delay_hours}h</span>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Ranked Candidates Table */}
          <Card className="p-5 bg-white shadow-sm border-slate-200">
            <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <Users className="h-4 w-4 text-slate-500" />
              Ranked Feasible Recovery Options
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase text-[10px]">
                    <th className="pb-2.5">Rank</th>
                    <th className="pb-2.5">Action & Candidate</th>
                    <th className="pb-2.5">CAR Legality</th>
                    <th className="pb-2.5 text-right">Cost (INR)</th>
                    <th className="pb-2.5 text-right">Delay (Hours)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {plan.options && plan.options.length > 0 ? (
                    plan.options.map((opt) => (
                      <tr key={opt.rank} className="hover:bg-slate-50/70">
                        <td className="py-3 font-bold text-slate-900">#{opt.rank}</td>
                        <td className="py-3 font-medium text-slate-800">
                          {opt.action}
                          {opt.crew_id && (
                            <span className="ml-2 font-mono text-[11px] text-slate-500">
                              ({opt.crew_id})
                            </span>
                          )}
                        </td>
                        <td className="py-3">
                          {opt.legal ? (
                            <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-700 gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Legal
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="border-rose-300 bg-rose-50 text-rose-700 gap-1">
                              <XCircle className="h-3 w-3" />
                              Illegal
                            </Badge>
                          )}
                        </td>
                        <td className="py-3 text-right font-bold text-slate-900">
                          ₹{opt.cost_inr?.toLocaleString()}
                        </td>
                        <td className="py-3 text-right text-slate-600">
                          +{opt.delay_hours}h
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="5" className="py-4 text-center text-slate-500">
                        No viable recovery options available.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Excluded Candidates & Reasons */}
          {plan.excluded_candidates && plan.excluded_candidates.length > 0 && (
            <Card className="p-5 bg-white shadow-sm border-slate-200">
              <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-rose-500" />
                Excluded Candidates & Specific Violation Audit ({plan.excluded_candidates.length})
              </h3>
              <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                {plan.excluded_candidates.map((cand, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/70 p-2.5 text-xs"
                  >
                    <span className="font-mono font-bold text-slate-800">{cand.crew_id}</span>
                    <span className="text-rose-700 font-medium">{cand.reason}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Callout Notification Draft (Q36) */}
          {plan.notification_draft && (
            <Card className="p-5 bg-slate-900 text-white shadow-md border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-white">
                    Official Dispatch Callout Notification Draft (Q36)
                  </h3>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopyNotification(plan.notification_draft.message_text)}
                  className="gap-1.5 border-slate-700 bg-slate-800 text-xs text-slate-200 hover:bg-slate-700"
                >
                  <Copy className="h-3.5 w-3.5" />
                  {copiedNotification ? 'Copied!' : 'Copy Notification'}
                </Button>
              </div>

              <pre className="overflow-x-auto rounded-lg bg-black/40 p-4 font-mono text-xs leading-relaxed text-slate-300">
                {plan.notification_draft.message_text}
              </pre>
            </Card>
          )}
        </div>
      ) : (
        <Card className="flex flex-col items-center justify-center p-12 text-center bg-white border-dashed border-slate-300">
          <Sparkles className="h-10 w-10 text-slate-400 mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No Recovery Plan Generated</h3>
          <p className="mt-1 text-sm text-slate-500 max-w-md">
            Select an operational benchmark above and click <strong>Optimize Recovery</strong> to evaluate candidates against all 7 DGCA CAR rules and find the cost-optimal legal resolution.
          </p>
        </Card>
      )}
    </div>
  )
}
