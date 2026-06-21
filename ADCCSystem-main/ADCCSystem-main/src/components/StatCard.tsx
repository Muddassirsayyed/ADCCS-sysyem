import React from 'react';
import { motion } from 'framer-motion';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'neutral';
  statusText?: string;
  statusType?: 'danger' | 'warning' | 'success' | 'info' | 'neutral';
  glow?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  trend,
  trendDirection = 'neutral',
  statusText,
  statusType = 'neutral',
  glow = false
}) => {
  const getStatusColor = () => {
    switch (statusType) {
      case 'danger': return 'text-adcc-danger border-adcc-danger/30 bg-adcc-danger/10';
      case 'warning': return 'text-adcc-warning border-adcc-warning/30 bg-adcc-warning/10';
      case 'success': return 'text-adcc-success border-adcc-success/30 bg-adcc-success/10';
      case 'info': return 'text-adcc-accent border-adcc-accent/30 bg-adcc-accent/10';
      default: return 'text-adcc-textMuted border-gray-700 bg-gray-800/40';
    }
  };

  return (
    <motion.div
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className={`glass-panel rounded-xl p-5 relative overflow-hidden transition-all duration-300 ${
        glow ? 'border-adcc-accent/30 shadow-glow' : 'border-gray-800'
      }`}
    >
      {/* Background radial highlight */}
      <div className="absolute -right-8 -top-8 w-24 h-24 bg-adcc-accent/5 rounded-full blur-xl pointer-events-none" />

      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-adcc-textMuted font-mono">
            {title}
          </span>
          <span className="text-3xl font-bold tracking-tight text-adcc-textPrimary mt-1 font-mono">
            {value}
          </span>
        </div>
        <div className={`p-2.5 rounded-lg border border-gray-800 bg-adcc-secondary/80 text-adcc-accent`}>
          {icon}
        </div>
      </div>

      <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-800/60 text-xs">
        <div className="flex items-center gap-1">
          {trend && (
            <span className={`flex items-center font-mono font-medium ${
              trendDirection === 'up' ? 'text-adcc-success' : trendDirection === 'down' ? 'text-adcc-danger' : 'text-adcc-textMuted'
            }`}>
              {trendDirection === 'up' && <ArrowUpRight size={14} />}
              {trendDirection === 'down' && <ArrowDownRight size={14} />}
              {trend}
            </span>
          )}
        </div>

        {statusText && (
          <span className={`px-2 py-0.5 rounded border text-[10px] uppercase font-mono font-semibold tracking-wider ${getStatusColor()}`}>
            {statusText}
          </span>
        )}
      </div>
    </motion.div>
  );
};
export default StatCard;
