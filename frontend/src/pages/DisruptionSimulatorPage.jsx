import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  Flame,
  Layers,
  Plane,
  Play,
  RotateCcw,
  ShieldAlert,
  Users,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { simulateDisruption } from '@/lib/api'

const BENCHMARK_PRESETS = [
  {
    id: 'S1',
    name: 'S1: ATR Captain Sick Call',
    desc: 'ATR Captain C-3231 sick for 1-day pairing P-2224 at 01:30Z',
    payload: {
      type: 'SICK_CREW',
      crew_id: 'C-3231',
      pairing_id: 'P-2224',
      reported_utc: '2026-09-16T01:30:00Z',
    },
  },
  {
    id: 'S2',
    name: 'S2: Flagship 2-Day Sick Call',
    desc: 'Captain C-1042 sick for multi-day pairing P-2291 with overnight stay',
    payload: {
      type: 'SICK_CREW',
      crew_id: 'C-1042',
      pairing_id: 'P-2291',
      reported_utc: '2026-09-15T05:00:00Z',
    },
  },
  {
    id: 'S3',
    name: 'S3: BLR Station Closure',
    desc: 'Runway maintenance closes BLR 08:00-14:00Z on 17 Sep (13 flights)',
    payload: {
      type: 'STATION_CLOSURE',
      station: 'BLR',
      date: '2026-09-17',
      window_utc: { start: '2026-09-17T08:00:00Z', end: '2026-09-17T14:00:00Z' },
    },
  },
  {
    id: 'S4',
    name: 'S4: VT-DXA 90m Delay & FDP Breach',
    desc: 'Technical delay of 1.5h cascades into crew FDP breach on sector 4',
    payload: {
      type: 'DELAY',
      aircraft: 'VT-DXA',
      date: '2026-09-16',
      delay_hours: 1.5,
    },
  },
  {
    id: 'S5',
    name: 'S5: Preflight Cert Expiry',
    desc: 'C-5417 recurrent training expired on 17 Sep before 19 Sep rostered duty',
    payload: {
      type: 'CERT_EXPIRY',
      crew_id: 'C-5417',
      pairing_id: 'P-2213',
      date: '2026-09-19',
    },
  },
  {
    id: 'S6',
    name: 'S6: Joint Multi-Sick Outbreak',
    desc: 'Captains for VT-DXA (P-2205) and VT-DXB (P-2212) call sick simultaneously',
    payload: {
      type: 'MULTI_SICK',
      events: [
        { crew_id: 'C-3940', pairing_id: 'P-2205', reported_utc: '2026-09-18T00:30:00Z' },
        { crew_id: 'C-1938', pairing_id: 'P-2212', reported_utc: '2026-09-18T00:30:00Z' },
      ],
    },
  },
]

export function DisruptionSimulatorPage() {
  const navigate = useNavigate()
  const [selectedPreset, setSelectedPreset] = useState(BENCHMARK_PRESETS[0].id)
  const [currentPayload, setCurrentPayload] = useState(BENCHMARK_PRESETS[0].payload)
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSelectPreset = (preset) => {
    setSelectedPreset(preset.id)
    setCurrentPayload(preset.payload)
    setResult(null)
    setError(null)
  }

  const handleRunSimulation = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await simulateDisruption(currentPayload)
      setResult(data)
    } catch (err) {
      setError(err.message || 'Simulation failed')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSendToOptimizer = () => {
    navigate('/recovery', { state: { initialEvent: currentPayload, simulationResult: result } })
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-y-auto bg-[#eef1f5] p-6">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Disruption Simulator</h1>
            <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
              Tier 2 Engine Active
            </Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Predictive cascading impact analysis, FDP breach detection, passenger exposure, and multi-day pairing breakage.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={handleRunSimulation}
            disabled={isLoading}
            className="gap-2 bg-emerald-600 text-white hover:bg-emerald-700"
          >
            <Play className="h-4 w-4" />
            {isLoading ? 'Simulating...' : 'Run Simulation'}
          </Button>
        </div>
      </div>

      {/* Preset Scenarios Grid */}
      <div className="mb-6">
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          Benchmark Disruption Scenarios (S1–S6)
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {BENCHMARK_PRESETS.map((preset) => {
            const isSelected = selectedPreset === preset.id
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => handleSelectPreset(preset)}
                className={`flex flex-col items-start rounded-xl border p-3.5 text-left transition-all ${
                  isSelected
                    ? 'border-emerald-500 bg-white shadow-md ring-2 ring-emerald-500/20'
                    : 'border-slate-200 bg-white/70 hover:border-slate-300 hover:bg-white'
                }`}
              >
                <div className="flex w-full items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">{preset.id}</span>
                  <Badge variant="secondary" className="text-[10px]">
                    {preset.payload.type}
                  </Badge>
                </div>
                <p className="mt-1 text-xs font-semibold text-slate-800 line-clamp-1">{preset.name.split(': ')[1]}</p>
                <p className="mt-1 text-[11px] text-slate-500 line-clamp-2">{preset.desc}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <Card className="mb-6 border-rose-200 bg-rose-50 p-4 text-rose-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0" />
            <p className="text-sm font-medium">{error}</p>
          </div>
        </Card>
      )}

      {/* Results View */}
      {result ? (
        <div className="space-y-6">
          {/* Action Callout Bar */}
          <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50/80 px-5 py-3.5 shadow-sm">
            <div className="flex items-center gap-3">
              <ShieldAlert className="h-5 w-5 text-amber-600" />
              <div>
                <p className="text-sm font-semibold text-amber-900">
                  Disruption Impact Assessment Completed
                </p>
                <p className="text-xs text-amber-700">
                  Cascading operational consequences identified. Click below to generate legal, cost-optimal recovery options.
                </p>
              </div>
            </div>
            <Button
              onClick={handleSendToOptimizer}
              className="gap-2 bg-slate-900 text-white hover:bg-slate-800"
              size="sm"
            >
              Optimize Recovery (Tier 3)
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>

          {/* Metric KPIs */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="p-4 bg-white shadow-sm border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>Disruption Type</span>
                <Flame className="h-4 w-4 text-orange-500" />
              </div>
              <p className="mt-2 text-xl font-bold text-slate-900">
                {result.disruption_type || result.type}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {result.is_multi_day ? 'Multi-Day Cascading Rotation' : 'Single Duty Impact'}
              </p>
            </Card>

            <Card className="p-4 bg-white shadow-sm border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>Passengers at Risk</span>
                <Users className="h-4 w-4 text-indigo-500" />
              </div>
              <p className="mt-2 text-xl font-bold text-slate-900">
                {result.passengers_at_risk || (result.passengers_day1 ? result.passengers_day1 : 0)}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {result.passengers_at_risk_day1 ? `Day 1: ${result.passengers_at_risk_day1} seats` : 'Total seat capacity'}
              </p>
            </Card>

            <Card className="p-4 bg-white shadow-sm border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>Uncrewed Flights</span>
                <Plane className="h-4 w-4 text-emerald-500" />
              </div>
              <p className="mt-2 text-xl font-bold text-slate-900">
                {result.uncovered_flights?.length || result.affected_flights?.length || result.affected_legs?.length || 0}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {result.pairing_id ? `Pairing: ${result.pairing_id}` : 'Direct flight sectors'}
              </p>
            </Card>

            <Card className="p-4 bg-white shadow-sm border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>CAR Legality & FDP</span>
                <Clock className="h-4 w-4 text-rose-500" />
              </div>
              <p className="mt-2 text-xl font-bold text-slate-900">
                {result.breach || result.fdp_breach || result.legal === false ? (
                  <span className="text-rose-600">Breach Detected</span>
                ) : (
                  <span className="text-emerald-600">Feasible</span>
                )}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {result.fdp_after_delay ? `${result.fdp_after_delay}h / ${result.fdp_limit}h limit` : 'DGCA CAR validation'}
              </p>
            </Card>
          </div>

          {/* Detailed Lists */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Uncovered Flights Card */}
            <Card className="p-5 bg-white shadow-sm border-slate-200">
              <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
                <Plane className="h-4 w-4 text-slate-500" />
                Impacted Flight Sectors
              </h3>
              {result.uncovered_flights && result.uncovered_flights.length > 0 ? (
                <div className="space-y-2">
                  {result.uncovered_flights_day1 && (
                    <div className="mb-3">
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Day 1 Sectors</span>
                      <div className="mt-1.5 flex flex-wrap gap-2">
                        {result.uncovered_flights_day1.map((f) => (
                          <Badge key={f} variant="outline" className="border-rose-200 bg-rose-50 text-rose-700">
                            {f}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {result.uncovered_flights_day2 && (
                    <div>
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Day 2 Sectors</span>
                      <div className="mt-1.5 flex flex-wrap gap-2">
                        {result.uncovered_flights_day2.map((f) => (
                          <Badge key={f} variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">
                            {f}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {!result.uncovered_flights_day1 && (
                    <div className="flex flex-wrap gap-2">
                      {result.uncovered_flights.map((f) => (
                        <Badge key={f} variant="outline" className="border-rose-200 bg-rose-50 text-rose-700">
                          {f}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ) : result.affected_flights && result.affected_flights.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {result.affected_flights.map((f) => (
                    <Badge key={f} variant="outline" className="border-slate-300 bg-slate-50 text-slate-700">
                      {f}
                    </Badge>
                  ))}
                </div>
              ) : result.affected_legs && result.affected_legs.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {result.affected_legs.map((f) => (
                    <Badge key={f} variant="outline" className="border-slate-300 bg-slate-50 text-slate-700">
                      {f}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">No uncrewed flight sectors found.</p>
              )}

              {result.breach_detail && (
                <div className="mt-4 rounded-lg bg-rose-50 p-3 text-xs text-rose-800 border border-rose-200">
                  <span className="font-bold">FDP Breach Assessment: </span>
                  {result.breach_detail}
                </div>
              )}
            </Card>

            {/* Assessment Details / Station Assessments */}
            <Card className="p-5 bg-white shadow-sm border-slate-200">
              <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
                <Clock className="h-4 w-4 text-slate-500" />
                Operational Assessment & Timeline
              </h3>
              {result.per_flight_assessment && result.per_flight_assessment.length > 0 ? (
                <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                  {result.per_flight_assessment.map((a) => (
                    <div
                      key={a.flight_id}
                      className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/70 p-2.5 text-xs"
                    >
                      <div>
                        <span className="font-bold text-slate-800">{a.flight_id}</span>
                        <span className="ml-2 text-slate-500">Delay: +{a.min_delay_hours}h</span>
                        {a.crew_fdp_after_delay && (
                          <span className="ml-2 text-slate-500">
                            FDP: {a.crew_fdp_after_delay}h / {a.fdp_limit}h
                          </span>
                        )}
                      </div>
                      <Badge
                        variant="outline"
                        className={
                          a.action.includes('re-crew')
                            ? 'border-rose-200 bg-rose-50 text-rose-700'
                            : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        }
                      >
                        {a.action}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-3 text-xs text-slate-600">
                  <div className="flex justify-between border-b border-slate-100 pb-2">
                    <span className="font-medium text-slate-500">Affected Crew Role</span>
                    <span className="font-semibold text-slate-800">{result.role || result.rank || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-100 pb-2">
                    <span className="font-medium text-slate-500">Reported Timestamp</span>
                    <span className="font-semibold text-slate-800">{result.reported_utc || result.date || 'N/A'}</span>
                  </div>
                  {result.lapsed_cert && (
                    <div className="flex justify-between border-b border-slate-100 pb-2">
                      <span className="font-medium text-slate-500">Lapsed Certification</span>
                      <Badge variant="outline" className="border-rose-200 bg-rose-50 text-rose-700">
                        {result.lapsed_cert}
                      </Badge>
                    </div>
                  )}
                  {result.aircraft && (
                    <div className="flex justify-between border-b border-slate-100 pb-2">
                      <span className="font-medium text-slate-500">Aircraft Tail</span>
                      <span className="font-semibold text-slate-800">{result.aircraft}</span>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        </div>
      ) : (
        <Card className="flex flex-col items-center justify-center p-12 text-center bg-white border-dashed border-slate-300">
          <Plane className="h-10 w-10 text-slate-400 mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No Simulation Executed</h3>
          <p className="mt-1 text-sm text-slate-500 max-w-md">
            Select a benchmark disruption preset above (S1–S6) and click <strong>Run Simulation</strong> to compute the cascading operational impacts under DGCA CAR regulations.
          </p>
        </Card>
      )}
    </div>
  )
}
