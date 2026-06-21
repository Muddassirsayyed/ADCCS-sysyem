import React, { useState, useEffect, useRef } from 'react';
import { Bell, Menu, ShieldCheck, ShieldAlert, Zap, Clock, Check } from 'lucide-react';
import { useSystem } from '../contexts/SystemContext';
import { useLocation } from 'react-router-dom';

interface NavbarProps {
  setSidebarOpen: (open: boolean) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ setSidebarOpen }) => {
  const { notifications, systemStatus, markAllNotificationsRead } = useSystem();
  const [showNotifications, setShowNotifications] = useState(false);
  const [time, setTime] = useState(new Date());
  const dropdownRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  // Get human readable title based on path
  const getPageTitle = () => {
    switch (location.pathname) {
      case '/': return 'Dashboard Overview';
      case '/map': return 'Tactical Disaster Map';
      case '/resources': return 'Resource Allocation & Inventory';
      case '/agents': return 'Multi-Agent Operations';
      case '/simulation': return 'Crisis Simulation Engine';
      case '/ai-command': return 'AI command Center Console';
      case '/analytics': return 'Historical Reports & Analytics';
      case '/settings': return 'System Settings';
      default: return 'Autonomous Disaster Command Center';
    }
  };

  // Clock Update
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Close notifications dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const unreadNotifications = notifications.filter(n => !n.read);
  const unreadCount = unreadNotifications.length;

  const getSystemStatusDetails = () => {
    switch (systemStatus) {
      case 'alert':
        return {
          text: 'ALERT ACTIVE',
          color: 'text-adcc-danger bg-adcc-danger/10 border-adcc-danger/35',
          icon: <ShieldAlert className="text-adcc-danger" size={14} />
        };
      case 'simulation':
        return {
          text: 'SIMULATION ACTIVE',
          color: 'text-adcc-warning bg-adcc-warning/10 border-adcc-warning/35',
          icon: <Zap className="text-adcc-warning" size={14} />
        };
      default:
        return {
          text: 'SYSTEM NOMINAL',
          color: 'text-adcc-success bg-adcc-success/10 border-adcc-success/35',
          icon: <ShieldCheck className="text-adcc-success" size={14} />
        };
    }
  };

  const status = getSystemStatusDetails();

  return (
    <header className="h-16 border-b border-gray-800 bg-adcc-secondary px-4 lg:px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Title / Hamburger */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-1.5 hover:bg-gray-800 text-adcc-textMuted hover:text-adcc-textPrimary lg:hidden rounded transition-colors"
        >
          <Menu size={20} />
        </button>
        <div className="flex flex-col">
          <h2 className="text-sm lg:text-base font-bold text-adcc-textPrimary tracking-wide font-mono">
            {getPageTitle()}
          </h2>
          <span className="text-[10px] text-adcc-textMuted lg:hidden">ADCC Operational Panel</span>
        </div>
      </div>

      {/* Control Actions / Clock / Notifications */}
      <div className="flex items-center gap-4">
        {/* System status indicator */}
        <div className={`hidden md:flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-extrabold tracking-wider border rounded-full ${status.color}`}>
          {status.icon}
          <span>{status.text}</span>
        </div>

        {/* Tactical Clock */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-adcc-bg border border-gray-800 rounded-lg text-xs font-mono font-medium text-adcc-textMuted">
          <Clock size={13} className="text-adcc-accent" />
          <span>
            {time.toLocaleDateString(undefined, { day: '2-digit', month: 'short' })}
          </span>
          <span className="text-gray-700">|</span>
          <span className="text-adcc-textPrimary font-bold">
            {time.toLocaleTimeString(undefined, { hour12: false })}
          </span>
        </div>

        {/* Notifications Tray */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 text-adcc-textMuted hover:text-adcc-textPrimary hover:bg-gray-800/80 rounded-lg relative transition-colors"
          >
            <Bell size={20} className={unreadCount > 0 ? 'animate-bounce' : ''} />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-adcc-danger text-[9px] font-mono font-bold text-white flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 lg:w-96 glass-panel-heavy rounded-xl border border-gray-800 shadow-2xl overflow-hidden z-50">
              <div className="px-4 py-3 border-b border-gray-800 bg-adcc-secondary flex items-center justify-between">
                <span className="text-xs font-bold font-mono tracking-wider uppercase text-adcc-textPrimary">
                  System Alerts ({unreadCount})
                </span>
                {unreadCount > 0 && (
                  <button
                    onClick={() => {
                      markAllNotificationsRead();
                      setShowNotifications(false);
                    }}
                    className="flex items-center gap-1 text-[10px] font-mono text-adcc-accent hover:text-adcc-textPrimary font-bold uppercase"
                  >
                    <Check size={12} /> Mark read
                  </button>
                )}
              </div>

              <div className="max-h-80 overflow-y-auto divide-y divide-gray-800/40">
                {notifications.length === 0 ? (
                  <div className="px-4 py-8 text-center text-xs text-adcc-textMuted font-mono">
                    NO ACTIVE INCIDENT TELEMETRY
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div 
                      key={n.id} 
                      className={`p-3 text-left transition-colors duration-150 hover:bg-adcc-bg/30 ${
                        !n.read ? 'bg-adcc-accentGlow/2 border-l-2 border-adcc-accent' : 'border-l-2 border-transparent'
                      }`}
                    >
                      <div className="flex justify-between items-start gap-1">
                        <span className={`text-[10px] font-mono font-bold uppercase tracking-wider ${
                          n.severity === 'critical' ? 'text-adcc-danger' : n.severity === 'warning' ? 'text-adcc-warning' : 'text-adcc-info'
                        }`}>
                          {n.title}
                        </span>
                        <span className="text-[9px] font-mono text-adcc-textMuted">{n.timestamp}</span>
                      </div>
                      <p className="text-xs text-adcc-textMuted mt-1 leading-normal font-sans">
                        {n.message}
                      </p>
                      <div className="text-[9px] font-mono text-gray-500 mt-2">
                        Source: {n.source}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User avatar and control center badge */}
        <div className="flex items-center gap-2 border-l border-gray-800 pl-4">
          <div className="relative">
            <img
              src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=256&auto=format&fit=crop"
              alt="Operator"
              className="w-8 h-8 rounded-lg object-cover border border-adcc-accent/20"
            />
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-adcc-success border-2 border-adcc-secondary" />
          </div>
          <div className="hidden xl:flex flex-col text-left">
            <span className="text-xs font-semibold text-adcc-textPrimary leading-none font-sans">
              Dr. Ashfa
            </span>
            <span className="text-[9px] font-mono text-adcc-accent uppercase font-bold mt-1">
              Duty Commander
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
export default Navbar;
