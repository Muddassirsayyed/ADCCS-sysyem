import React from 'react';
import { Boxes, Ship, Ambulance, Users, ShieldAlert, Award } from 'lucide-react';

interface ResourceAllocationViewProps {
  allocationPlan?: {
    disaster_title?: string;
    allocations?: Array<{
      resource_id?: string;
      resource_name?: string;
      quantity: number;
      reason?: string;
    }>;
    total_resources_deployed?: number;
    estimated_coverage_pct?: number;
    gaps?: string[];
  } | null;
}

export const ResourceAllocationView: React.FC<ResourceAllocationViewProps> = ({
  allocationPlan
}) => {
  if (!allocationPlan) {
    return (
      <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col items-center justify-center h-48 text-xs font-mono text-adcc-textMuted border-dashed">
        NO RESOURCE ALLOCATION DATA IN QUEUE
      </div>
    );
  }

  const allocations = allocationPlan.allocations || [];
  const coverage = allocationPlan.estimated_coverage_pct ?? 100;
  const gaps = allocationPlan.gaps || [];

  // Count allocations by resource keywords
  const countAllocated = (keywords: string[]) => {
    return allocations
      .filter(a => {
        const name = (a.resource_name || '').toLowerCase();
        return keywords.some(k => name.includes(k));
      })
      .reduce((sum, a) => sum + a.quantity, 0);
  };

  const boatsCount = countAllocated(['boat', 'vessel']);
  const ambulancesCount = countAllocated(['ambulance', 'paramedic']);
  const medicalCount = countAllocated(['medical', 'doctor', 'clinic']);
  const ndrfCount = countAllocated(['ndrf', 'rescue team', 'specialist']);

  // Get status color based on coverage
  const getCoverageColor = (cov: number) => {
    if (cov >= 90) return 'text-adcc-success border-adcc-success/35 bg-adcc-success/5';
    if (cov >= 75) return 'text-adcc-warning border-adcc-warning/30 bg-adcc-warning/5';
    return 'text-adcc-danger border-adcc-danger/30 bg-adcc-danger/5';
  };

  return (
    <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-gray-850 pb-3">
        <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
          <Boxes size={14} className="text-adcc-accent" />
          Tactical Resource Allocation Plan
        </h3>
        <span className="text-[9px] font-mono text-adcc-accent uppercase font-semibold">
          {allocationPlan.disaster_title || 'Active Plan'}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono">
        {/* Boats */}
        <div className="bg-adcc-secondary/30 border border-gray-850 p-3 rounded-lg flex flex-col gap-1">
          <span className="text-[10px] text-adcc-textMuted flex items-center gap-1">
            <Ship size={12} className="text-[#38BDF8]" /> BOATS ALLOCATED
          </span>
          <span className="text-lg font-bold text-adcc-textPrimary">{boatsCount} <span className="text-xs font-normal text-adcc-textMuted">Units</span></span>
        </div>

        {/* Ambulances */}
        <div className="bg-adcc-secondary/30 border border-gray-850 p-3 rounded-lg flex flex-col gap-1">
          <span className="text-[10px] text-adcc-textMuted flex items-center gap-1">
            <Ambulance size={12} className="text-adcc-warning" /> AMBULANCES
          </span>
          <span className="text-lg font-bold text-adcc-textPrimary">{ambulancesCount} <span className="text-xs font-normal text-adcc-textMuted">Units</span></span>
        </div>

        {/* Medical Teams */}
        <div className="bg-adcc-secondary/30 border border-gray-850 p-3 rounded-lg flex flex-col gap-1">
          <span className="text-[10px] text-adcc-textMuted flex items-center gap-1">
            <Users size={12} className="text-adcc-accent" /> MED TEAMS
          </span>
          <span className="text-lg font-bold text-adcc-textPrimary">{medicalCount} <span className="text-xs font-normal text-adcc-textMuted">Teams</span></span>
        </div>

        {/* NDRF Units */}
        <div className="bg-adcc-secondary/30 border border-gray-850 p-3 rounded-lg flex flex-col gap-1">
          <span className="text-[10px] text-adcc-textMuted flex items-center gap-1">
            <Award size={12} className="text-adcc-success" /> NDRF UNITS
          </span>
          <span className="text-lg font-bold text-adcc-textPrimary">{ndrfCount} <span className="text-xs font-normal text-adcc-textMuted">Units</span></span>
        </div>
      </div>

      {/* Coverage Meter */}
      <div className="flex flex-col gap-2 border-t border-gray-850/60 pt-3 font-mono">
        <div className="flex justify-between items-center text-xs">
          <span className="text-adcc-textMuted uppercase">Safety Coverage Level:</span>
          <span className={`px-2 py-0.5 rounded border text-[11px] font-bold ${getCoverageColor(coverage)}`}>
            {coverage}% COVERAGE
          </span>
        </div>
        <div className="w-full bg-gray-900 rounded-full h-1.5 overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              coverage >= 90 ? 'bg-adcc-success shadow-[0_0_8px_rgba(16,185,129,0.4)]' :
              coverage >= 75 ? 'bg-adcc-warning' : 'bg-adcc-danger'
            }`} 
            style={{ width: `${coverage}%` }}
          />
        </div>
      </div>

      {/* Deficits Panel */}
      {gaps.length > 0 && (
        <div className="flex flex-col gap-2 bg-adcc-danger/5 border border-adcc-danger/25 p-3 rounded-lg font-mono text-[10px]">
          <span className="text-adcc-danger font-bold uppercase tracking-wider flex items-center gap-1">
            <ShieldAlert size={12} /> SUPPLY DEFICITS IDENTIFIED
          </span>
          <ul className="list-disc pl-4 space-y-1 text-adcc-textMuted">
            {gaps.map((gap, i) => (
              <li key={i}>{gap}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
export default ResourceAllocationView;
