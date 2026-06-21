import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Map, 
  Package, 
  Cpu, 
  Play, 
  Terminal, 
  BarChart3, 
  Settings as SettingsIcon,
  Shield,
  Activity,
  X
} from 'lucide-react';
import { useSystem } from '../contexts/SystemContext';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, setIsOpen }) => {
  const { systemStatus, disasters } = useSystem();
  
  const activeDisastersCount = disasters.filter(d => d.status === 'active').length;

  const menuItems = [
    { name: 'Dashboard', path: '/', icon: <LayoutDashboard size={20} /> },
    { name: 'Disaster Map', path: '/map', icon: <Map size={20} /> },
    { name: 'Resources', path: '/resources', icon: <Package size={20} /> },
    { name: 'Agents', path: '/agents', icon: <Cpu size={20} /> },
    { name: 'Simulation', path: '/simulation', icon: <Play size={20} /> },
    { name: 'AI Command Center', path: '/ai-command', icon: <Terminal size={20} /> },
    { name: 'Analytics', path: '/analytics', icon: <BarChart3 size={20} /> },
    { name: 'Settings', path: '/settings', icon: <SettingsIcon size={20} /> },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-adcc-bg/80 backdrop-blur-sm lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col w-64 bg-adcc-secondary border-r border-gray-800 transition-transform duration-300 lg:translate-x-0 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        {/* Branding header */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-800 bg-adcc-bg/40">
          <div className="flex items-center gap-2">
            <div className="relative">
              <Shield className="text-adcc-accent fill-adcc-accent/15" size={24} />
              <span className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full status-pulse-dot ${
                systemStatus === 'alert' ? 'bg-adcc-danger' : systemStatus === 'simulation' ? 'bg-adcc-warning' : 'bg-adcc-success'
              }`} />
            </div>
            <div className="flex flex-col">
              <span className="font-extrabold text-sm tracking-widest text-adcc-textPrimary font-mono leading-none">
                ADCC
              </span>
              <span className="text-[9px] uppercase tracking-wider text-adcc-accent font-bold mt-1">
                Command Center
              </span>
            </div>
          </div>
          <button 
            onClick={() => setIsOpen(false)}
            className="p-1 hover:bg-gray-800 text-adcc-textMuted hover:text-adcc-textPrimary lg:hidden rounded"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 px-4 py-6 overflow-y-auto space-y-1">
          {menuItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setIsOpen(false)}
              className={({ isActive }) =>
                `flex items-center justify-between px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 group ${
                  isActive
                    ? 'bg-adcc-accent/10 border-l-2 border-adcc-accent text-adcc-accent font-semibold shadow-glow'
                    : 'text-adcc-textMuted hover:bg-gray-800/50 hover:text-adcc-textPrimary border-l-2 border-transparent'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <span className="group-hover:text-adcc-accent transition-colors duration-200">
                  {item.icon}
                </span>
                <span>{item.name}</span>
              </div>
              {item.name === 'Disaster Map' && activeDisastersCount > 0 && (
                <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-adcc-danger/20 text-adcc-danger border border-adcc-danger/30 rounded-full">
                  {activeDisastersCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Bottom system telemetry logs */}
        <div className="p-4 border-t border-gray-800 bg-adcc-bg/30">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-adcc-secondary/60 border border-gray-800/80">
            <Activity className="text-adcc-accent animate-pulse" size={16} />
            <div className="flex flex-col min-w-0">
              <span className="text-[10px] font-mono uppercase tracking-wider text-adcc-textMuted">
                Network Stream
              </span>
              <span className="text-xs font-mono font-bold text-adcc-success truncate">
                CONNECTED // 240.8G
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
export default Sidebar;
