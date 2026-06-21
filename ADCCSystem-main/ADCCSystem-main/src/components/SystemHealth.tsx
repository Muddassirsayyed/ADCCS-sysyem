import React from 'react';
import { Activity, RefreshCw } from 'lucide-react';

export interface HealthStatus {
  service: string;
  status: 'online' | 'offline' | 'warning';
  latency?: string;
  details?: string;
}

interface SystemHealthProps {
  dbConnected?: boolean;
  apiConnected?: boolean;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const SystemHealth: React.FC<SystemHealthProps> = ({
  dbConnected = true,
  apiConnected = true,
  onRefresh,
  isLoading = false
}) => {
  const items: HealthStatus[] = [
    {
      service: 'PostgreSQL Database',
      status: dbConnected ? 'online' : 'offline',
      latency: dbConnected ? '4ms' : '--',
      details: dbConnected ? 'Connected (adcc_db)' : 'Auth Failure / Offline'
    },
    {
      service: 'FastAPI Backend Gateway',
      status: apiConnected ? 'online' : 'offline',
      latency: apiConnected ? '12ms' : '--',
      details: apiConnected ? 'Running on http://localhost:8000' : 'Connection Timeout'
    },
    {
      service: 'Open-Meteo Weather Tool',
      status: apiConnected ? 'online' : 'offline',
      latency: apiConnected ? '140ms' : '--',
      details: 'Active current + forecast models'
    },
    {
      service: 'GDACS Live Disasters Feed',
      status: apiConnected ? 'online' : 'offline',
      latency: apiConnected ? '280ms' : '--',
      details: 'Listening on RSS XML stream'
    },
    {
      service: 'USGS Earthquake API',
      status: apiConnected ? 'online' : 'offline',
      latency: apiConnected ? '190ms' : '--',
      details: 'Subscribed to earthquake events feed'
    },
    {
      service: 'LangGraph Core Engine',
      status: apiConnected ? 'online' : 'offline',
      latency: '15ms',
      details: 'StateGraph workflow compiled'
    }
  ];

  return (
    <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-gray-850 pb-3">
        <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
          <Activity size={14} className="text-adcc-accent" />
          System Diagnostics & Health
        </h3>
        {onRefresh && (
          <button 
            disabled={isLoading}
            onClick={onRefresh}
            className="p-1 hover:bg-gray-800/80 rounded transition-all duration-150 text-adcc-textMuted hover:text-adcc-accent disabled:opacity-50"
          >
            <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((item, idx) => {
          const isOnline = item.status === 'online';
          const isOffline = item.status === 'offline';
          
          return (
            <div 
              key={idx}
              className="flex justify-between items-center bg-adcc-secondary/40 border border-gray-850/80 p-3 rounded-lg font-mono text-xs"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-adcc-textPrimary font-semibold text-[11px]">{item.service}</span>
                <span className="text-[10px] text-adcc-textMuted">{item.details}</span>
              </div>
              <div className="flex items-center gap-2">
                {item.latency && (
                  <span className="text-[9px] text-adcc-textMuted">{item.latency}</span>
                )}
                <span className={`h-2.5 w-2.5 rounded-full border transition-all duration-300 ${
                  isOnline ? 'bg-adcc-success border-adcc-success/35 shadow-[0_0_8px_rgba(16,185,129,0.4)]' :
                  isOffline ? 'bg-adcc-danger border-adcc-danger/35 shadow-[0_0_8px_rgba(239,68,68,0.4)] animate-pulse' :
                  'bg-adcc-warning border-adcc-warning/35'
                }`} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
export default SystemHealth;
