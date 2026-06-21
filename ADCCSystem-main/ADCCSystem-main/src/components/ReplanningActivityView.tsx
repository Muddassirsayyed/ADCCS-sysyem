import React from 'react';
import { RefreshCw, Play } from 'lucide-react';

interface ReplanningAction {
  type?: string;
  trigger: string;
  action: string;
  reason: string;
  timestamp?: string;
}

interface ReplanningActivityViewProps {
  actions?: ReplanningAction[];
  timestamp?: string;
}

export const ReplanningActivityView: React.FC<ReplanningActivityViewProps> = ({
  actions = [],
  timestamp = 'Just now'
}) => {
  if (actions.length === 0) {
    return (
      <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col items-center justify-center h-48 text-xs font-mono text-adcc-textMuted border-dashed">
        NO REPLANNING EVENTS LOGGED (ENVIRONMENT STABLE)
      </div>
    );
  }

  const getTriggerColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'rainfall_increase':
        return 'text-[#38BDF8] border-[#38BDF8]/20 bg-[#38BDF8]/5';
      case 'shelter_full':
        return 'text-adcc-danger border-adcc-danger/20 bg-adcc-danger/5';
      case 'resource_deficit':
        return 'text-adcc-warning border-adcc-warning/20 bg-adcc-warning/5';
      case 'earthquake_aftershock':
        return 'text-purple-400 border-purple-400/20 bg-purple-400/5';
      default:
        return 'text-adcc-accent border-adcc-accent/20 bg-adcc-accent/5';
    }
  };

  return (
    <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-gray-850 pb-3">
        <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
          <RefreshCw size={14} className="text-adcc-accent animate-spin" />
          Dynamic Replanning Activity Log
        </h3>
        <span className="text-[9px] font-mono text-adcc-textMuted uppercase">{timestamp}</span>
      </div>

      <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
        {actions.map((act, idx) => {
          const type = act.type || 'generic';
          return (
            <div 
              key={idx}
              className="flex flex-col gap-2 bg-adcc-secondary/25 border border-gray-850 p-3.5 rounded-lg font-mono text-xs leading-relaxed"
            >
              {/* Trigger Name / Badge */}
              <div className="flex justify-between items-center border-b border-gray-900 pb-2">
                <span className={`px-2 py-0.5 rounded border text-[9px] font-bold uppercase tracking-wider ${getTriggerColor(type)}`}>
                  Trigger: {act.trigger}
                </span>
                <span className="text-[9px] text-adcc-textMuted flex items-center gap-1">
                  <Play size={8} className="text-adcc-accent" /> Active Log
                </span>
              </div>

              {/* Action Taken */}
              <div className="flex flex-col gap-0.5 mt-1">
                <span className="text-adcc-textMuted text-[10px] uppercase font-semibold">ACTION EXECUTED:</span>
                <span className="text-adcc-accent font-bold text-[12px]">{act.action}</span>
              </div>

              {/* Justification / Reason */}
              <div className="flex flex-col gap-0.5 mt-1">
                <span className="text-adcc-textMuted text-[10px] uppercase font-semibold">JUSTIFICATION:</span>
                <span className="text-adcc-textPrimary text-[11px] leading-relaxed font-sans">{act.reason}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
export default ReplanningActivityView;
