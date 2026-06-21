import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation } from '@tanstack/react-query';
import apiService, { 
  SimulationRunRequest, 
  SimulationRunResult, 
  BackendDisaster 
} from '../services/api';
import PageContainer from '../components/PageContainer';
import SectionHeader from '../components/SectionHeader';
import { 
  Play, 
  Settings, 
  ShieldAlert, 
  Activity, 
  Compass, 
  RefreshCw, 
  AlertTriangle, 
  HeartPulse, 
  Boxes, 
  Warehouse, 
  Terminal, 
  ArrowRight 
} from 'lucide-react';

export const Simulation: React.FC = () => {
  // 1. Fetch live active disasters to choose as baseline context
  const { data: disasters = [], isLoading: disastersLoading } = useQuery<BackendDisaster[]>({
    queryKey: ['disasters'],
    queryFn: apiService.getDisasters
  });

  // 2. States for inputs
  const [simulationType, setSimulationType] = useState<'Flood' | 'Cyclone' | 'Earthquake'>('Flood');
  const [selectedDisasterId, setSelectedDisasterId] = useState<string>('');
  
  // Percentages sliders state
  const [rainfallChangePct, setRainfallChangePct] = useState<number>(30);
  const [windSpeedChangePct, setWindSpeedChangePct] = useState<number>(15);
  const [populationChangePct, setPopulationChangePct] = useState<number>(20);
  const [shelterCapacityChangePct, setShelterCapacityChangePct] = useState<number>(-10);
  const [resourceAvailabilityChangePct, setResourceAvailabilityChangePct] = useState<number>(-20);

  // Outcome log and results state
  const [outcomeReport, setOutcomeReport] = useState<SimulationRunResult | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [stepIndex, setStepIndex] = useState<number>(-1);

  const steps = [
    { title: 'Ingesting Spatial Layer', detail: 'Fetching terrain heights and routing networks...' },
    { title: 'Tuning Meteorology', detail: 'Adjusting atmospheric wind grids and storm surge projections...' },
    { title: 'Simulating Logistics Stress', detail: 'Applying capacity multiplier constraints to shelter networks...' },
    { title: 'Compiling Digital Twin State', detail: 'Finalizing agent heuristic matrices and risk curves...' }
  ];

  // 3. Mutation to execute simulation
  const simulateMutation = useMutation({
    mutationFn: (payload: SimulationRunRequest) => apiService.runSimulation(payload),
    onSuccess: (data) => {
      setOutcomeReport(data);
      setLogs(prev => [
        `[SUCCESS] Digital Twin calculation completed successfully.`,
        `[LOGS] Registered Scenario Run: "${data.scenario_name}"`,
        ...prev
      ]);
      setStepIndex(steps.length);
    },
    onError: (err: any) => {
      setLogs(prev => [
        `[CRITICAL ERROR] Digital Twin model crashed: ${err.message}`,
        ...prev
      ]);
      setStepIndex(-1);
    }
  });

  const handleStartSimulation = (e: React.FormEvent) => {
    e.preventDefault();
    setOutcomeReport(null);
    setStepIndex(0);
    setLogs(['[SYSTEM] Initializing Digital Twin simulation kernel...']);

    // Step-by-step progress logging simulation
    let currentStep = 0;
    const interval = setInterval(() => {
      currentStep++;
      if (currentStep < steps.length) {
        setStepIndex(currentStep);
        setLogs(prev => [
          `[OK] ${steps[currentStep - 1].title} completed.`,
          `[RUNNING] ${steps[currentStep].title}... ${steps[currentStep].detail}`,
          ...prev
        ]);
      } else {
        clearInterval(interval);
        
        // Trigger actual backend simulation
        const payload: SimulationRunRequest = {
          simulation_type: simulationType,
          rainfall_change_pct: rainfallChangePct,
          wind_speed_change_pct: windSpeedChangePct,
          population_change_pct: populationChangePct,
          shelter_capacity_change_pct: shelterCapacityChangePct,
          resource_availability_change_pct: resourceAvailabilityChangePct,
          disaster_id: selectedDisasterId || undefined
        };

        simulateMutation.mutate(payload);
      }
    }, 1000);
  };

  const getSliderLabel = (val: number) => {
    if (val > 0) return `+${val}%`;
    return `${val}%`;
  };

  const getSeverityBadgeColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'bg-adcc-danger text-white border-adcc-danger/30';
      case 'high': return 'bg-[#F97316] text-white border-[#F97316]/30';
      case 'medium': return 'bg-adcc-warning text-adcc-bg border-adcc-warning/30';
      default: return 'bg-adcc-success text-white border-adcc-success/30';
    }
  };

  const activeDisasters = disasters.filter(d => d.status === 'Active');

  return (
    <PageContainer>
      <SectionHeader 
        title="Digital Twin Simulation Console" 
        description="Trigger predictive natural hazard scenarios, adjust environmental variables, and analyze resource stress indicators."
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Left Column: Settings Configurator (1 Col) */}
        <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4 bg-adcc-secondary/20 h-fit">
          <div className="border-b border-gray-850 pb-3">
            <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
              <Settings size={14} className="text-adcc-accent" />
              What-If Configurator
            </h3>
          </div>

          <form onSubmit={handleStartSimulation} className="space-y-4 font-mono text-[11px] text-adcc-textMuted">
            {/* Simulated Disaster Type */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-adcc-textMuted uppercase font-semibold">Simulated Disaster Type</label>
              <select
                value={simulationType}
                onChange={(e) => setSimulationType(e.target.value as any)}
                disabled={simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
                className="w-full bg-adcc-bg border border-gray-855 text-adcc-textPrimary text-xs rounded-lg p-2.5 outline-none focus:border-adcc-accent"
              >
                <option value="Flood">FLOOD INCIDENT</option>
                <option value="Cyclone">CYCLONE / HURRICANE SURGE</option>
                <option value="Earthquake">EARTHQUAKE FAULT SHIFT</option>
              </select>
            </div>

            {/* Baseline Context Disaster */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-adcc-textMuted uppercase font-semibold">Baseline Disaster Target</label>
              <select
                value={selectedDisasterId}
                onChange={(e) => setSelectedDisasterId(e.target.value)}
                disabled={disastersLoading || simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
                className="w-full bg-adcc-bg border border-gray-855 text-adcc-textPrimary text-xs rounded-lg p-2.5 outline-none focus:border-adcc-accent"
              >
                <option value="">-- DEFAULT PRESETS (CITY GRID) --</option>
                {activeDisasters.filter(d => d.disaster_type === simulationType).map(d => (
                  <option key={d.id} value={d.id}>{d.title.toUpperCase()} ({d.severity})</option>
                ))}
              </select>
            </div>

            {/* Rainfall Slider (only relevant for Flood/Cyclone) */}
            {simulationType !== 'Earthquake' && (
              <div className="flex flex-col gap-1.5 border-t border-gray-900 pt-3">
                <div className="flex justify-between font-bold">
                  <span className="uppercase">RAINFALL DELTA</span>
                  <span className="text-adcc-accent">{getSliderLabel(rainfallChangePct)}</span>
                </div>
                <input
                  type="range"
                  min="-100"
                  max="100"
                  step="5"
                  value={rainfallChangePct}
                  onChange={(e) => setRainfallChangePct(parseInt(e.target.value))}
                  disabled={simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
                  className="w-full accent-adcc-accent cursor-pointer bg-gray-850 h-1 rounded appearance-none"
                />
              </div>
            )}

            {/* Wind Speed Slider (Relevant for Cyclone/Earthquake as seismic proxy) */}
            <div className="flex flex-col gap-1.5 border-t border-gray-900 pt-3">
              <div className="flex justify-between font-bold">
                <span className="uppercase">
                  {simulationType === 'Earthquake' ? 'SEISMIC ENERGY INTENSITY' : 'WIND SPEED DELTA'}
                </span>
                <span className="text-adcc-accent">{getSliderLabel(windSpeedChangePct)}</span>
              </div>
              <input
                type="range"
                min="-100"
                max="100"
                step="5"
                value={windSpeedChangePct}
                onChange={(e) => setWindSpeedChangePct(parseInt(e.target.value))}
                disabled={simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
                className="w-full accent-adcc-accent cursor-pointer bg-gray-850 h-1 rounded appearance-none"
              />
            </div>

            {/* Population Slider */}
            <div className="flex flex-col gap-1.5 border-t border-gray-900 pt-3">
              <div className="flex justify-between font-bold">
                <span className="uppercase">POPULATION DENSITY DELTA</span>
                <span className="text-adcc-accent">{getSliderLabel(populationChangePct)}</span>
              </div>
              <input
                type="range"
                min="-100"
                max="100"
                step="5"
                value={populationChangePct}
                onChange={(e) => setPopulationChangePct(parseInt(e.target.value))}
                disabled={simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
                className="w-full accent-adcc-accent cursor-pointer bg-gray-850 h-1 rounded appearance-none"
              />
            </div>

            {/* Resource Availability Slider */}
            <div className="flex flex-col gap-1.5 border-t border-gray-900 pt-3">
              <div className="flex justify-between font-bold">
                <span className="uppercase">DEPOT RESOURCES AVAILABLE</span>
                <span className="text-adcc-accent">{getSliderLabel(resourceAvailabilityChangePct)}</span>
              </div>
              <input
                type="range"
                min="-100"
                max="100"
                step="5"
                value={resourceAvailabilityChangePct}
                onChange={(e) => setResourceAvailabilityChangePct(parseInt(e.target.value))}
                disabled={simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
                className="w-full accent-adcc-accent cursor-pointer bg-gray-850 h-1 rounded appearance-none"
              />
            </div>

            {/* Shelter Capacity Slider */}
            <div className="flex flex-col gap-1.5 border-t border-gray-900 pt-3">
              <div className="flex justify-between font-bold">
                <span className="uppercase">SHELTER CAPACITY COEFFICIENT</span>
                <span className="text-adcc-accent">{getSliderLabel(shelterCapacityChangePct)}</span>
              </div>
              <input
                type="range"
                min="-100"
                max="100"
                step="5"
                value={shelterCapacityChangePct}
                onChange={(e) => setShelterCapacityChangePct(parseInt(e.target.value))}
                disabled={simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
                className="w-full accent-adcc-accent cursor-pointer bg-gray-850 h-1 rounded appearance-none"
              />
            </div>

            <button
              type="submit"
              disabled={simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length}
              className="w-full flex items-center justify-center gap-1.5 py-3 mt-4 bg-adcc-warning/10 border border-adcc-warning/25 hover:bg-adcc-warning hover:text-adcc-bg text-xs font-mono font-bold uppercase rounded-lg transition-all duration-200 disabled:opacity-40"
            >
              {simulateMutation.isPending || stepIndex >= 0 && stepIndex < steps.length ? (
                <RefreshCw size={13} className="animate-spin text-adcc-warning" />
              ) : (
                <Play size={13} fill="currentColor" />
              )}
              Initialize Digital Twin Model
            </button>
          </form>
        </div>

        {/* Right Columns: Output Diagnostic & Comparative Assessment (2 Cols) */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          
          {/* Simulation Progress Terminal */}
          <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4 bg-[#090E1A]/80">
            <div className="flex items-center justify-between border-b border-gray-850 pb-3">
              <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
                <Terminal size={14} className="text-adcc-warning animate-pulse" />
                Scenario Analytics Pipeline Logs
              </h3>
              {stepIndex >= 0 && stepIndex < steps.length && (
                <span className="text-[10px] font-mono text-adcc-warning animate-pulse">SOLVING EQUATIONS...</span>
              )}
            </div>

            {/* Visual Step Nodes */}
            {stepIndex >= 0 && stepIndex < steps.length && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-1 p-2 bg-adcc-secondary/25 border border-gray-850 rounded-lg">
                {steps.map((s, idx) => (
                  <div 
                    key={idx} 
                    className={`flex flex-col gap-1 p-2.5 border rounded font-mono text-[9px] transition-all duration-300 ${
                      stepIndex >= idx ? 'bg-adcc-accentGlow/5 border-adcc-accent/30 text-adcc-accent' : 'bg-transparent border-transparent text-gray-700'
                    }`}
                  >
                    <span className="font-bold">STAGE 0{idx + 1}</span>
                    <span className="truncate">{s.title}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Terminal logs window */}
            <div className="h-32 bg-[#050811] border border-gray-855 rounded-lg p-3 font-mono text-[10.5px] leading-relaxed text-adcc-warning overflow-y-auto flex flex-col-reverse gap-1.5 select-text">
              {logs.length === 0 ? (
                <div className="flex items-center justify-center h-full text-xs text-adcc-textMuted uppercase tracking-wider">
                  Twin Simulator Offline. Load configuration parameters to boot.
                </div>
              ) : (
                logs.map((l, index) => (
                  <div key={index} className="border-b border-gray-900/40 pb-1">{l}</div>
                ))
              )}
            </div>
          </div>

          {/* Simulation Output comparisons */}
          <AnimatePresence mode="wait">
            {outcomeReport && (
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                className="flex flex-col gap-6"
              >
                {/* 1. COMPARISON CARDS - Before vs After */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
                  {/* Severity Card */}
                  <div className="glass-panel border border-gray-800 p-4 rounded-xl flex flex-col justify-between bg-adcc-secondary/10">
                    <span className="text-adcc-textMuted uppercase text-[9px] mb-2 block font-bold">Severity Level Comparison</span>
                    <div className="flex items-center justify-between mt-1">
                      <div className="flex flex-col">
                        <span className="text-[9px] text-gray-505 uppercase">Baseline</span>
                        <span className="text-xs text-adcc-textPrimary font-bold">{outcomeReport.summary.baseline.severity}</span>
                      </div>
                      <ArrowRight size={14} className="text-adcc-accent" />
                      <div className="flex flex-col items-end">
                        <span className="text-[9px] text-gray-550 uppercase">Simulated</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${getSeverityBadgeColor(outcomeReport.summary.predicted.severity_level)}`}>
                          {outcomeReport.summary.predicted.severity_level}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Risk Score Card */}
                  <div className="glass-panel border border-gray-800 p-4 rounded-xl flex flex-col justify-between bg-adcc-secondary/10">
                    <span className="text-adcc-textMuted uppercase text-[9px] mb-2 block font-bold">Total Risk Score</span>
                    <div className="flex items-center justify-between mt-1">
                      <div className="flex flex-col">
                        <span className="text-[9px] text-gray-505 uppercase">Baseline</span>
                        <span className="text-sm text-adcc-textPrimary font-bold">
                          {outcomeReport.summary.baseline.severity === 'Critical' ? '82.5%' : 
                           outcomeReport.summary.baseline.severity === 'High' ? '64.0%' : 
                           outcomeReport.summary.baseline.severity === 'Medium' ? '38.0%' : '14.5%'}
                        </span>
                      </div>
                      <ArrowRight size={14} className="text-adcc-accent" />
                      <div className="flex flex-col items-end">
                        <span className="text-[9px] text-gray-550 uppercase">Simulated</span>
                        <span className="text-sm text-adcc-accent font-bold">
                          {outcomeReport.summary.predicted.severity_score}%
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Population Affected Card */}
                  <div className="glass-panel border border-gray-800 p-4 rounded-xl flex flex-col justify-between bg-adcc-secondary/10">
                    <span className="text-adcc-textMuted uppercase text-[9px] mb-2 block font-bold">Evacuees / Population Impact</span>
                    <div className="flex items-center justify-between mt-1">
                      <div className="flex flex-col">
                        <span className="text-[9px] text-gray-505 uppercase">Baseline</span>
                        <span className="text-xs text-adcc-textPrimary font-bold">{outcomeReport.summary.baseline.affected_population.toLocaleString()}</span>
                      </div>
                      <ArrowRight size={14} className="text-adcc-accent" />
                      <div className="flex flex-col items-end">
                        <span className="text-xs text-adcc-warning font-bold">
                          {outcomeReport.summary.predicted.affected_population.toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 2. RESOURCE DEFICITS & COGNITIVE PLANS */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  
                  {/* Resource Deficits List */}
                  <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/40 flex flex-col gap-4">
                    <div className="border-b border-gray-850 pb-3 font-mono">
                      <h3 className="font-bold text-xs uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
                        <Boxes size={14} className="text-adcc-accent" />
                        Simulated Logistics Outbreak Gaps
                      </h3>
                    </div>

                    <div className="space-y-2.5 font-mono text-[10.5px]">
                      {Object.keys(outcomeReport.summary.resource_metrics.required).length === 0 ? (
                        <div className="p-3 border border-dashed border-gray-800 text-center text-adcc-textMuted rounded-lg">
                          NO RESOURCE DEFICITS IDENTIFIED
                        </div>
                      ) : (
                        Object.keys(outcomeReport.summary.resource_metrics.required).map((resName) => {
                          const req = outcomeReport.summary.resource_metrics.required[resName];
                          const avail = outcomeReport.summary.resource_metrics.simulated_available[resName];
                          const gap = outcomeReport.summary.resource_metrics.gap[resName];
                          const coverage = req > 0 ? Math.round((Math.max(0, req - gap) / req) * 100) : 100;
                          
                          return (
                            <div key={resName} className="p-2.5 border border-gray-850/65 rounded-lg bg-adcc-secondary/25 flex flex-col gap-2">
                              <div className="flex justify-between items-center text-adcc-textPrimary font-bold">
                                <span className="flex items-center gap-1.5 uppercase">
                                  {resName === 'Boat' ? <Compass size={11} className="text-[#38BDF8]" /> : 
                                   resName === 'Ambulance' ? <HeartPulse size={11} className="text-adcc-warning" /> : <Boxes size={11} className="text-adcc-success" />}
                                  {resName}
                                </span>
                                {gap > 0 ? (
                                  <span className="text-adcc-danger animate-pulse text-[9.5px] font-bold border border-adcc-danger/25 bg-adcc-danger/5 px-1.5 py-0.5 rounded">DEFICIT: {gap} UNITS</span>
                                ) : (
                                  <span className="text-adcc-success text-[9.5px] font-bold border border-adcc-success/25 bg-adcc-success/5 px-1.5 py-0.5 rounded">ADEQUATE</span>
                                )}
                              </div>
                              <div className="flex justify-between items-center text-[9px] text-adcc-textMuted">
                                <span>Simulated Required: {req} units</span>
                                <span>Simulated Available: {avail} units</span>
                              </div>
                              {/* Animated Progress Bar for Coverage */}
                              <div className="h-1.5 w-full bg-gray-900 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full transition-all duration-505 ${
                                    coverage >= 80 ? 'bg-adcc-success' : coverage >= 50 ? 'bg-adcc-warning' : 'bg-adcc-danger'
                                  }`}
                                  style={{ width: `${coverage}%` }}
                                />
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>

                  {/* Shelter Evacuee Overflows */}
                  <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/40 flex flex-col gap-4">
                    <div className="border-b border-gray-850 pb-3 font-mono">
                      <h3 className="font-bold text-xs uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
                        <Warehouse size={14} className="text-purple-400" />
                        Evacuation Capacity & Overflow
                      </h3>
                    </div>

                    <div className="flex flex-col gap-4 font-mono text-[11px]">
                      {/* Overall Progress Gauge details */}
                      <div className="grid grid-cols-2 gap-3 bg-adcc-secondary/20 border border-gray-850/80 p-3 rounded-lg text-xs">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[9px] text-adcc-textMuted uppercase font-bold">Assigned Citizens</span>
                          <span className="text-sm font-extrabold text-adcc-success">
                            {outcomeReport.summary.shelter_metrics.assigned_population.toLocaleString()}
                          </span>
                        </div>
                        <div className="flex flex-col gap-0.5 items-end">
                          <span className="text-[9px] text-adcc-textMuted uppercase font-bold">Unassigned Overflow</span>
                          <span className={`text-sm font-extrabold ${outcomeReport.summary.shelter_metrics.unassigned_population > 0 ? 'text-adcc-danger animate-pulse' : 'text-adcc-success'}`}>
                            {outcomeReport.summary.shelter_metrics.unassigned_population.toLocaleString()}
                          </span>
                        </div>
                      </div>

                      {/* Warnings and specific allocations */}
                      <div className="space-y-2.5 max-h-[170px] overflow-y-auto pr-1">
                        {outcomeReport.summary.shelter_metrics.unassigned_population > 0 && (
                          <div className="p-3 border border-adcc-danger/30 bg-adcc-danger/5 text-adcc-danger rounded-lg flex items-start gap-2 text-[10px] leading-relaxed">
                            <AlertTriangle size={15} className="shrink-0 animate-bounce" />
                            <span>
                              WARNING: LOGISTICS OVERFLOW DETECTED. Shelter infrastructure is overloaded. Setup temporary transit camps or adjust route grids.
                            </span>
                          </div>
                        )}

                        {outcomeReport.summary.shelter_metrics.shelter_assignments.map((sh, idx) => (
                          <div key={idx} className="flex justify-between items-center border-b border-gray-900 pb-1.5 text-[10.5px]">
                            <div className="flex flex-col gap-0.5">
                              <span className="text-adcc-textPrimary font-semibold">{sh.shelter_name}</span>
                              <span className="text-[9px] text-adcc-textMuted">Distance: {sh.distance_km} km</span>
                            </div>
                            <div className="flex flex-col items-end">
                              <span className="text-adcc-accent font-bold">+{sh.assigned_people.toLocaleString()} slots</span>
                              <span className={`text-[8.5px] font-bold ${sh.new_occupancy_pct >= 90 ? 'text-adcc-danger' : 'text-adcc-textMuted'}`}>
                                Occupancy: {sh.new_occupancy_pct}%
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                </div>

                {/* 3. SIMULATED FACTOR BREAKDOWN */}
                <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/40 flex flex-col gap-4 font-mono">
                  <div className="border-b border-gray-850 pb-2">
                    <h3 className="font-bold text-xs uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
                      <Activity size={14} className="text-adcc-accent" />
                      What-If Severity Stress Factors Breakdown
                    </h3>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                    <div className="p-3 bg-adcc-secondary/20 border border-gray-850 rounded-lg flex flex-col">
                      <span className="text-[9px] text-gray-500 uppercase">Population Risk (40%)</span>
                      <span className="text-sm font-extrabold text-adcc-textPrimary mt-1">
                        {outcomeReport.summary.predicted.breakdown.population_impact_score}/100
                      </span>
                    </div>

                    <div className="p-3 bg-adcc-secondary/20 border border-gray-850 rounded-lg flex flex-col">
                      <span className="text-[9px] text-gray-500 uppercase">Weather Risk (25%)</span>
                      <span className="text-sm font-extrabold text-adcc-textPrimary mt-1">
                        {outcomeReport.summary.predicted.breakdown.weather_risk_score}/100
                      </span>
                    </div>

                    <div className="p-3 bg-adcc-secondary/20 border border-gray-850 rounded-lg flex flex-col">
                      <span className="text-[9px] text-gray-500 uppercase">Magnitude Risk (20%)</span>
                      <span className="text-sm font-extrabold text-adcc-textPrimary mt-1">
                        {outcomeReport.summary.predicted.breakdown.disaster_magnitude_score}/100
                      </span>
                    </div>

                    <div className="p-3 bg-adcc-secondary/20 border border-gray-850 rounded-lg flex flex-col">
                      <span className="text-[9px] text-gray-500 uppercase">Resource Strain (15%)</span>
                      <span className="text-sm font-extrabold text-adcc-textPrimary mt-1">
                        {outcomeReport.summary.predicted.breakdown.resource_stress_score}/100
                      </span>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {!outcomeReport && stepIndex < 0 && (
            /* Standby view */
            <div className="glass-panel border border-gray-800 rounded-xl p-8 bg-[#090E1A]/40 flex flex-col items-center justify-center gap-3 text-center min-h-[350px]">
              <div className="p-3 bg-adcc-warning/10 border border-adcc-warning/20 rounded-full text-adcc-warning animate-pulse">
                <ShieldAlert size={28} />
              </div>
              <div className="font-mono text-xs text-adcc-textPrimary uppercase tracking-wider font-bold">DIGITAL TWIN STANDBY</div>
              <p className="text-[11px] text-adcc-textMuted leading-relaxed max-w-sm font-sans">
                Adjust delta percentages for rainfall, wind speed, populations, resources, and capacities. Press "Initialize Digital Twin Model" to run comparative what-if forecasts.
              </p>
            </div>
          )}

        </div>

      </div>
    </PageContainer>
  );
};
export default Simulation;
