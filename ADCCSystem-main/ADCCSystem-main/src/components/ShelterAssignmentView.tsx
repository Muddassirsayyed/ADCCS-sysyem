import React from 'react';
import { Home, Users, AlertOctagon, CheckCircle2, ShieldAlert } from 'lucide-react';

interface ShelterAssignmentViewProps {
  shelterPlan?: {
    assigned_shelters?: Array<{
      shelter_id?: string;
      name?: string;
      city?: string;
      capacity: number;
      assigned_people: number;
      distance_km?: number;
    }>;
    total_shelter_capacity?: number;
    total_people_assigned?: number;
    overflow_risk?: boolean;
    unassigned_population?: number;
    assigned_population?: number;
    affected_population?: number;
    recommended_additional_shelters?: string[];
  } | null;
}

export const ShelterAssignmentView: React.FC<ShelterAssignmentViewProps> = ({
  shelterPlan
}) => {
  if (!shelterPlan) {
    return (
      <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col items-center justify-center h-48 text-xs font-mono text-adcc-textMuted border-dashed">
        NO SHELTER ASSIGNMENT DATA IN QUEUE
      </div>
    );
  }

  // Get data points with safe fallbacks
  const affected = shelterPlan.affected_population ?? shelterPlan.total_people_assigned ?? 0;
  const assigned = shelterPlan.assigned_population ?? shelterPlan.total_people_assigned ?? 0;
  const unassigned = shelterPlan.unassigned_population ?? (affected - assigned) ?? 0;
  const overflowRisk = shelterPlan.overflow_risk ?? unassigned > 0;
  const shelters = shelterPlan.assigned_shelters || [];

  const totalCapacity = shelterPlan.total_shelter_capacity ?? 
    shelters.reduce((acc, curr) => acc + curr.capacity, 0);
  
  const totalOccupied = shelters.reduce((acc, curr) => acc + curr.assigned_people, 0);
  const capacityPercent = totalCapacity > 0 ? Math.round((totalOccupied / totalCapacity) * 100) : 0;

  return (
    <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-gray-850 pb-3">
        <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
          <Home size={14} className="text-adcc-accent" />
          Evacuation Shelter Assignment Plan
        </h3>
        <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider border ${
          overflowRisk ? 'text-adcc-danger border-adcc-danger/30 bg-adcc-danger/5 animate-pulse' : 'text-adcc-success border-adcc-success/30 bg-adcc-success/5'
        }`}>
          {overflowRisk ? 'OVERFLOW RISK' : 'SECURE'}
        </span>
      </div>

      {/* Numerical Stats */}
      <div className="grid grid-cols-3 gap-2.5 font-mono text-center">
        <div className="bg-adcc-secondary/20 border border-gray-850 p-3 rounded-lg flex flex-col gap-0.5">
          <span className="text-[9px] text-adcc-textMuted uppercase flex items-center justify-center gap-1">
            <Users size={10} /> Affected
          </span>
          <span className="text-md font-bold text-adcc-textPrimary">{affected.toLocaleString()}</span>
        </div>
        <div className="bg-adcc-secondary/20 border border-gray-850 p-3 rounded-lg flex flex-col gap-0.5">
          <span className="text-[9px] text-adcc-textMuted uppercase flex items-center justify-center gap-1">
            <CheckCircle2 size={10} className="text-adcc-success" /> Assigned
          </span>
          <span className="text-md font-bold text-adcc-success">{assigned.toLocaleString()}</span>
        </div>
        <div className="bg-adcc-secondary/20 border border-gray-850 p-3 rounded-lg flex flex-col gap-0.5">
          <span className="text-[9px] text-adcc-textMuted uppercase flex items-center justify-center gap-1">
            <AlertOctagon size={10} className={unassigned > 0 ? 'text-adcc-danger' : 'text-adcc-textMuted'} /> Overflow
          </span>
          <span className={`text-md font-bold ${unassigned > 0 ? 'text-adcc-danger' : 'text-adcc-textMuted'}`}>
            {unassigned.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Capacity Progress Bar */}
      <div className="flex flex-col gap-2 font-mono text-[10px]">
        <div className="flex justify-between items-center text-[10px] text-adcc-textMuted">
          <span>SHELTER VOLUME CAPACITY UTILIZATION:</span>
          <span className="text-adcc-textPrimary font-semibold">{capacityPercent}% ({totalOccupied} / {totalCapacity} slots)</span>
        </div>
        <div className="w-full bg-gray-900 rounded-full h-1.5 overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              capacityPercent >= 90 ? 'bg-adcc-danger shadow-[0_0_8px_rgba(239,68,68,0.4)]' :
              capacityPercent >= 75 ? 'bg-adcc-warning' : 'bg-adcc-accent'
            }`} 
            style={{ width: `${Math.min(100, capacityPercent)}%` }}
          />
        </div>
      </div>

      {/* Shelter Allocations List */}
      {shelters.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-gray-850/60 pt-3">
          <span className="text-[9px] font-mono text-adcc-textMuted uppercase">Active Assignments:</span>
          <div className="space-y-2 max-h-[120px] overflow-y-auto pr-1">
            {shelters.map((shelter, i) => {
              const util = shelter.capacity > 0 ? Math.round((shelter.assigned_people / shelter.capacity) * 100) : 0;
              return (
                <div key={i} className="flex justify-between items-center text-xs font-mono bg-adcc-secondary/15 border border-gray-900 p-2 rounded">
                  <div className="flex flex-col">
                    <span className="text-adcc-textPrimary text-[11px] font-semibold">{shelter.name}</span>
                    <span className="text-[9px] text-adcc-textMuted">City: {shelter.city || 'Disaster Zone'} | Dist: {shelter.distance_km ? `${shelter.distance_km.toFixed(1)}km` : 'Local'}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-adcc-accent font-bold">{shelter.assigned_people}</span>
                    <span className="text-adcc-textMuted text-[9px]"> / {shelter.capacity} ({util}%)</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Advisory Warnings */}
      {overflowRisk && (
        <div className="flex flex-col gap-1.5 bg-adcc-danger/5 border border-adcc-danger/25 p-3 rounded-lg font-mono text-[10px]">
          <span className="text-adcc-danger font-bold uppercase tracking-wider flex items-center gap-1">
            <ShieldAlert size={12} /> ACTIONABLE SHELTER MITIGATIONS
          </span>
          <ul className="list-disc pl-4 space-y-1 text-adcc-textMuted">
            {shelterPlan.recommended_additional_shelters?.map((rec, i) => (
              <li key={i}>{rec}</li>
            )) || (
              <>
                <li>Deploy temporary emergency camps (e.g. Relief Camp Delta).</li>
                <li>Request district-level resources for emergency tents.</li>
              </>
            )}
          </ul>
        </div>
      )}
    </div>
  );
};
export default ShelterAssignmentView;
