import React from 'react';
import { useQuery } from '@tanstack/react-query';
import apiService, { BackendAlert } from '../services/api';
import { ShieldAlert, AlertTriangle, Info, Bell, RefreshCw } from 'lucide-react';

interface LiveAlertsPanelProps {
  limit?: number;
}

export const LiveAlertsPanel: React.FC<LiveAlertsPanelProps> = ({ limit = 8 }) => {
  // Use React Query with 30-second refetch interval
  const { data: alerts = [], isFetching, error } = useQuery<BackendAlert[]>({
    queryKey: ['liveAlerts'],
    queryFn: apiService.getAlerts,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const getAlertIcon = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return <ShieldAlert size={14} className="text-adcc-danger animate-pulse" />;
      case 'warning':
      case 'medium':
        return <AlertTriangle size={14} className="text-adcc-warning" />;
      default:
        return <Info size={14} className="text-adcc-accent" />;
    }
  };

  const getAlertBorder = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'border-adcc-danger/30 hover:border-adcc-danger/50 bg-adcc-danger/5';
      case 'warning':
      case 'medium':
        return 'border-adcc-warning/20 hover:border-adcc-warning/40 bg-adcc-warning/5';
      default:
        return 'border-gray-800/80 hover:border-adcc-accent/20 bg-adcc-secondary/20';
    }
  };

  return (
    <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between border-b border-gray-850 pb-3">
        <div className="flex items-center gap-1.5">
          <Bell size={14} className="text-adcc-accent animate-pulse" />
          <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary">
            Tactical Warnings & Alerts
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {isFetching && (
            <RefreshCw size={10} className="animate-spin text-adcc-accent" />
          )}
          <span className="text-[9px] font-mono text-adcc-textMuted uppercase">
            Auto-Sync (30s)
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1 max-h-[350px]">
        {error ? (
          <div className="flex items-center justify-center h-full text-xs font-mono text-adcc-danger">
            TELEMETRY LINK DOWN (API ERROR)
          </div>
        ) : alerts.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-xs font-mono text-adcc-textMuted border border-dashed border-gray-800/60 rounded-lg">
            NO ANOMALOUS SIGNALS DETECTED
          </div>
        ) : (
          alerts.slice(0, limit).map((alert) => (
            <div
              key={alert.id}
              className={`p-3 rounded-lg border flex flex-col gap-1.5 transition-all duration-200 ${getAlertBorder(alert.severity)}`}
            >
              <div className="flex justify-between items-center font-mono">
                <span className="font-bold text-[11px] text-adcc-textPrimary flex items-center gap-1.5">
                  {getAlertIcon(alert.severity)}
                  {alert.title}
                </span>
                <span className="text-[9px] text-adcc-textMuted">
                  {new Date(alert.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
              <p className="text-[10.5px] leading-relaxed text-adcc-textMuted font-sans">
                {alert.message}
              </p>
              <div className="flex items-center justify-between font-mono text-[9px] border-t border-gray-900/30 pt-1.5">
                <span className="text-adcc-textMuted uppercase">Source: {alert.source || 'N/A'}</span>
                {alert.confidence_score !== undefined && (
                  <span className="text-adcc-accent uppercase font-semibold">Confidence: {Math.round(alert.confidence_score * 100)}%</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
export default LiveAlertsPanel;
