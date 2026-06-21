import { AlertCircle, AlertTriangle, Info, ShieldAlert } from 'lucide-react';

interface AlertCardProps {
  id: string;
  title: string;
  message: string;
  severity: 'critical' | 'warning' | 'info';
  timestamp: string;
  source: string;
  read?: boolean;
  onAction?: (id: string) => void;
  onDismiss?: (id: string) => void;
}

export const AlertCard: React.FC<AlertCardProps> = ({
  id,
  title,
  message,
  severity,
  timestamp,
  source,
  read = false,
  onAction,
  onDismiss
}) => {
  const getSeverityStyles = () => {
    switch (severity) {
      case 'critical':
        return {
          border: 'border-adcc-danger/30 hover:border-adcc-danger/60',
          bg: 'bg-adcc-danger/5',
          text: 'text-adcc-danger',
          icon: <AlertCircle className="text-adcc-danger shrink-0" size={18} />
        };
      case 'warning':
        return {
          border: 'border-adcc-warning/30 hover:border-adcc-warning/60',
          bg: 'bg-adcc-warning/5',
          text: 'text-adcc-warning',
          icon: <AlertTriangle className="text-adcc-warning shrink-0" size={18} />
        };
      default:
        return {
          border: 'border-adcc-accent/20 hover:border-adcc-accent/40',
          bg: 'bg-adcc-accentGlow/2',
          text: 'text-adcc-accent',
          icon: <Info className="text-adcc-accent shrink-0" size={18} />
        };
    }
  };

  const styles = getSeverityStyles();

  return (
    <div
      className={`glass-panel border rounded-lg p-4 transition-all duration-300 ${styles.border} ${styles.bg} ${
        !read ? 'relative' : ''
      }`}
    >
      {/* Unread indicator dot */}
      {!read && (
        <span className="absolute top-4 right-4 w-2 h-2 rounded-full bg-adcc-accent status-pulse-dot" />
      )}

      <div className="flex gap-3">
        {styles.icon}
        <div className="flex-1 flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-semibold text-sm text-adcc-textPrimary pr-4">{title}</h4>
            <span className="text-[10px] font-mono text-adcc-textMuted shrink-0">{timestamp}</span>
          </div>

          <p className="text-xs text-adcc-textMuted leading-relaxed font-sans">{message}</p>

          <div className="flex items-center justify-between gap-4 mt-2 pt-2 border-t border-gray-800/40">
            <span className="text-[10px] font-mono text-adcc-textMuted flex items-center gap-1 uppercase tracking-wider">
              <ShieldAlert size={12} className="text-adcc-accent" />
              Source: {source}
            </span>

            <div className="flex items-center gap-2">
              {onAction && severity === 'critical' && (
                <button
                  onClick={() => onAction(id)}
                  className="px-2 py-1 bg-adcc-accent/10 border border-adcc-accent/20 hover:bg-adcc-accent hover:text-adcc-bg text-[10px] font-mono font-bold uppercase tracking-wider rounded transition-all duration-200"
                >
                  Orchestrate Response
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={() => onDismiss(id)}
                  className="px-2 py-1 hover:bg-gray-800 text-[10px] font-mono text-adcc-textMuted hover:text-adcc-textPrimary rounded transition-colors duration-150"
                >
                  Archive
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
export default AlertCard;
