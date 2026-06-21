import React from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  ShieldAlert, 
  MapPin, 
  Activity, 
  Boxes, 
  BellRing,
  FileDown,
  ShieldCheck,
  RefreshCw
} from 'lucide-react';
import apiService from '../services/api';
import PageContainer from '../components/PageContainer';
import SectionHeader from '../components/SectionHeader';
import StatCard from '../components/StatCard';
import SystemHealth from '../components/SystemHealth';
import LiveAlertsPanel from '../components/LiveAlertsPanel';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  BarChart, 
  Bar, 
  Legend 
} from 'recharts';

export const Dashboard: React.FC = () => {
  // 1. Fetch live data from FastAPI backend using React Query
  const { data: disasters = [], isLoading: disastersLoading, refetch: refetchDisasters } = useQuery({
    queryKey: ['disasters'],
    queryFn: apiService.getDisasters
  });

  const { data: resources = [], isLoading: resourcesLoading, refetch: refetchResources } = useQuery({
    queryKey: ['resources'],
    queryFn: apiService.getResources
  });

  const { data: alerts = [], isLoading: alertsLoading, refetch: refetchAlerts } = useQuery({
    queryKey: ['alerts'],
    queryFn: apiService.getAlerts
  });

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ['health'],
    queryFn: apiService.getHealth
  });

  // Sync Mutation to query GDACS & USGS on the backend
  const syncMutation = useMutation({
    mutationFn: apiService.syncDisasters,
    onSuccess: () => {
      refetchDisasters();
      refetchResources();
      refetchAlerts();
      refetchHealth();
    }
  });

  const handleRefreshAll = () => {
    syncMutation.mutate();
  };

  const isRefreshLoading = disastersLoading || resourcesLoading || alertsLoading || healthLoading || syncMutation.isPending;

  // 2. Compute dynamic stats
  const activeDisasters = disasters.filter(d => d.status === 'Active');
  const criticalDisasters = activeDisasters.filter(d => d.severity === 'Critical' || d.severity === 'High');
  const verifiedReports = disasters.filter(d => d.verification_status === 'Verified');
  
  // Affected Population
  const totalAffectedPop = activeDisasters.reduce((acc, curr) => acc + (curr.affected_population || 0), 0);
  
  // Resource Available
  const totalQty = resources.reduce((acc, curr) => acc + curr.quantity, 0);
  const availableQty = resources.filter(r => r.status === 'Available').reduce((acc, curr) => acc + curr.quantity, 0);
  const resourcePercent = totalQty > 0 ? Math.round((availableQty / totalQty) * 100) : 0;

  // Highest severity level in play
  const getHighestSeverity = () => {
    if (activeDisasters.some(d => d.severity === 'Critical')) return 'Critical';
    if (activeDisasters.some(d => d.severity === 'High' || d.severity === 'Medium')) return 'High';
    return 'Low';
  };
  const currentSeverityLevel = getHighestSeverity();

  // Average confidence score across verified events
  const getAverageConfidence = () => {
    const verifiedWithConf = verifiedReports.filter(d => d.confidence_score !== undefined);
    if (verifiedWithConf.length === 0) return 0;
    const totalConf = verifiedWithConf.reduce((sum, d) => sum + (d.confidence_score || 0), 0);
    return Math.round((totalConf / verifiedWithConf.length) * 100);
  };
  const avgConfidence = getAverageConfidence();

  // 3. Map charts data from DB fields
  const resourceChartData = ['Boat', 'Ambulance', 'Medical_Team', 'Rescue_Team', 'NDRF_Unit'].map(type => {
    const typeResources = resources.filter(r => r.resource_type === type);
    const available = typeResources.filter(r => r.status === 'Available').reduce((sum, r) => sum + r.quantity, 0);
    const busy = typeResources.filter(r => r.status === 'Busy').reduce((sum, r) => sum + r.quantity, 0);
    return {
      name: type.replace('_', ' '),
      Available: available,
      Deployed: busy
    };
  });

  const trendData = [
    { name: 'Jan', Cyclones: 1, Wildfires: 2, Floods: 2 },
    { name: 'Feb', Cyclones: 0, Wildfires: 1, Floods: 3 },
    { name: 'Mar', Cyclones: 2, Wildfires: 1, Floods: 4 },
    { name: 'Apr', Cyclones: 1, Wildfires: 2, Floods: 5 },
    { name: 'May', Cyclones: 2, Wildfires: 3, Floods: 6 },
    { name: 'Jun', 
      Cyclones: activeDisasters.filter(d=>d.disaster_type==='Cyclone').length, 
      Wildfires: activeDisasters.filter(d=>d.disaster_type==='Wildfire').length, 
      Floods: activeDisasters.filter(d=>d.disaster_type==='Flood').length 
    }
  ];

  // Export report dummy handler
  const handleExport = () => {
    const csvContent = "data:text/csv;charset=utf-8,ADCC OPERATIONAL COMMAND REPORT - " + new Date().toISOString() + "\n" +
      "Active Disasters," + activeDisasters.length + "\n" +
      "Verified Reports," + verifiedReports.length + "\n" +
      "Highest Severity Level," + currentSeverityLevel + "\n" +
      "Affected Population," + totalAffectedPop + "\n" +
      "Resource Available %," + resourcePercent + "\n";
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `adcc_live_command_report_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Layout Framer Motion animations
  const containerVariants = {
    hidden: {},
    show: {
      transition: {
        staggerChildren: 0.03
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: 'easeOut' as const } }
  };

  const isDemoActive = activeDisasters.some(d => d.source === 'DEMO');

  return (
    <PageContainer>
      {isDemoActive && (
        <div className="mb-6 flex items-center justify-between p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-500 font-mono text-xs shadow-[0_0_15px_rgba(245,158,11,0.05)]">
          <div className="flex items-center gap-2.5">
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
            </span>
            <span className="font-bold tracking-wider uppercase">DEMO MODE ACTIVE</span>
            <span className="text-gray-400 border-l border-gray-800 pl-2.5">
              This scenario is generated for testing and training.
            </span>
          </div>
        </div>
      )}
      <SectionHeader 
        title="Emergency Operations Command" 
        description="Real-time live multi-agent pipeline monitoring and dispatch synchronization."
        actions={
          <div className="flex gap-2">
            <button 
              disabled={isRefreshLoading}
              onClick={handleRefreshAll}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-adcc-accent/15 border border-adcc-accent/25 hover:bg-adcc-accent hover:text-adcc-bg text-xs font-mono font-bold uppercase tracking-wider rounded transition-all duration-200"
            >
              <RefreshCw size={12} className={isRefreshLoading ? 'animate-spin' : ''} /> Sync
            </button>
            <button 
              onClick={handleExport}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-adcc-secondary border border-gray-800 hover:border-gray-700 text-xs font-mono font-bold uppercase tracking-wider rounded transition-all duration-200"
            >
              <FileDown size={12} /> Export Report
            </button>
          </div>
        }
      />

      {/* KPI Cards Grid */}
      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4"
      >
        <motion.div variants={itemVariants}>
          <StatCard
            title="Active Disasters"
            value={activeDisasters.length}
            icon={<ShieldAlert size={20} />}
            trend={`${criticalDisasters.length} Critical`}
            trendDirection={criticalDisasters.length > 0 ? "up" : "neutral"}
            statusText={activeDisasters.length > 0 ? 'ACTIVE HAZARD' : 'NOMINAL'}
            statusType={activeDisasters.length > 0 ? 'danger' : 'success'}
            glow={activeDisasters.length > 0}
          />
        </motion.div>

        <motion.div variants={itemVariants}>
          <StatCard
            title="Verified Reports"
            value={verifiedReports.length}
            icon={<ShieldCheck size={20} className="text-adcc-success" />}
            trend={`${disasters.length - verifiedReports.length} Pending`}
            trendDirection="neutral"
            statusText="CONFIRMED EVENTS"
            statusType="success"
          />
        </motion.div>

        <motion.div variants={itemVariants}>
          <StatCard
            title="Severity Level"
            value={currentSeverityLevel}
            icon={<MapPin size={20} />}
            trend="Max Outbreak"
            trendDirection="neutral"
            statusText="RESPONSE LEVEL"
            statusType={currentSeverityLevel === 'Critical' ? 'danger' : currentSeverityLevel === 'High' ? 'warning' : 'success'}
            glow={currentSeverityLevel === 'Critical'}
          />
        </motion.div>

        <motion.div variants={itemVariants}>
          <StatCard
            title="Confidence Score"
            value={`${avgConfidence}%`}
            icon={<Activity size={20} />}
            trend="Consensus Rating"
            trendDirection="neutral"
            statusText="DATA RELIABILITY"
            statusType={avgConfidence >= 75 ? 'success' : avgConfidence >= 50 ? 'warning' : 'danger'}
          />
        </motion.div>

        <motion.div variants={itemVariants}>
          <StatCard
            title="Resource Available"
            value={`${resourcePercent}%`}
            icon={<Boxes size={20} />}
            trend={`${availableQty} Units Vacant`}
            trendDirection={resourcePercent < 50 ? "down" : "neutral"}
            statusText="LOGISTICS BUFFER"
            statusType={resourcePercent >= 80 ? 'success' : resourcePercent >= 50 ? 'warning' : 'danger'}
          />
        </motion.div>

        <motion.div variants={itemVariants}>
          <StatCard
            title="Critical Alerts"
            value={alerts.filter(a => a.severity === 'Critical').length}
            icon={<BellRing size={20} />}
            trend="Live Sensors"
            trendDirection="neutral"
            statusText="ALARM STATUS"
            statusType={alerts.some(a=>a.severity==='Critical') ? 'danger' : 'info'}
          />
        </motion.div>
      </motion.div>

      {/* Diagnostics Health Status Widget */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.3 }}
      >
        <SystemHealth 
          dbConnected={health?.database === 'connected'} 
          apiConnected={!!health}
          onRefresh={handleRefreshAll}
          isLoading={isRefreshLoading}
        />
      </motion.div>

      {/* Visual Analytics / Main Panels Section */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Disaster Inundation Trend Chart */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.35 }}
          className="xl:col-span-2 glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4"
        >
          <div className="flex items-center justify-between border-b border-gray-850 pb-3 font-mono">
            <h3 className="font-bold text-xs tracking-wider uppercase text-adcc-textPrimary">
              Incident Frequency Ingestion (Active Models)
            </h3>
            <span className="text-[9px] text-adcc-accent uppercase">Live GIS Ingestion</span>
          </div>
          
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorCyclones" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#EF4444" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#EF4444" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorWildfires" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#F59E0B" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorFloods" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00E5FF" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#00E5FF" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" />
                <XAxis dataKey="name" stroke="#9CA3AF" fontSize={10} tickLine={false} />
                <YAxis stroke="#9CA3AF" fontSize={10} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#090E1A', border: '1px solid rgba(0, 229, 255, 0.15)', borderRadius: '8px', color: '#F9FAFB', fontFamily: 'monospace' }}
                  itemStyle={{ fontSize: '10px' }}
                />
                <Legend wrapperStyle={{ fontSize: '10px', fontFamily: 'monospace', paddingTop: '10px' }} />
                <Area type="monotone" dataKey="Cyclones" stroke="#EF4444" fillOpacity={1} fill="url(#colorCyclones)" strokeWidth={1.5} />
                <Area type="monotone" dataKey="Wildfires" stroke="#F59E0B" fillOpacity={1} fill="url(#colorWildfires)" strokeWidth={1.5} />
                <Area type="monotone" dataKey="Floods" stroke="#00E5FF" fillOpacity={1} fill="url(#colorFloods)" strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Live Alerts Panel (Auto-polling backend every 30s) */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.35 }}
          className="h-full"
        >
          <LiveAlertsPanel limit={4} />
        </motion.div>
      </div>

      {/* Second Row: Resource Utilization Chart */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Resource Allocation Chart */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.35 }}
          className="xl:col-span-2 glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4"
        >
          <div className="flex items-center justify-between border-b border-gray-850 pb-3 font-mono">
            <h3 className="font-bold text-xs tracking-wider uppercase text-adcc-textPrimary">
              Resource Distribution Telemetry (Database Sync)
            </h3>
            <span className="text-[9px] text-adcc-accent uppercase">Logistics Depot Logs</span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={resourceChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" />
                <XAxis dataKey="name" stroke="#9CA3AF" fontSize={10} tickLine={false} />
                <YAxis stroke="#9CA3AF" fontSize={10} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#090E1A', border: '1px solid rgba(0, 229, 255, 0.15)', borderRadius: '8px', color: '#F9FAFB', fontFamily: 'monospace' }}
                  itemStyle={{ fontSize: '10px' }}
                />
                <Legend wrapperStyle={{ fontSize: '10px', fontFamily: 'monospace', paddingTop: '10px' }} />
                <Bar dataKey="Available" fill="#00E5FF" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Deployed" fill="#F59E0B" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Tactical Status Metrics */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.35 }}
          className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4"
        >
          <div className="flex items-center justify-between border-b border-gray-850 pb-3 font-mono">
            <h3 className="font-bold text-xs tracking-wider uppercase text-adcc-textPrimary">
              Logistics Registry Summary
            </h3>
            <span className="text-[9px] text-adcc-success uppercase">Active Sync</span>
          </div>

          <div className="flex-1 flex flex-col justify-center space-y-3 font-mono text-[11px]">
            <div className="flex justify-between items-center bg-adcc-secondary/40 border border-gray-850 p-2.5 rounded-lg">
              <span className="text-adcc-textMuted uppercase">GIS Ingestion Server</span>
              <span className="font-bold text-adcc-success">99.98% UPTIME</span>
            </div>

            <div className="flex justify-between items-center bg-adcc-secondary/40 border border-gray-850 p-2.5 rounded-lg">
              <span className="text-adcc-textMuted uppercase">Heartbeat Frequency</span>
              <span className="font-bold text-adcc-accent">1.0s (POLLING)</span>
            </div>

            <div className="flex justify-between items-center bg-adcc-secondary/40 border border-gray-850 p-2.5 rounded-lg">
              <span className="text-adcc-textMuted uppercase">Satellite Latency</span>
              <span className="font-bold text-adcc-warning">480ms (SAT-NET)</span>
            </div>

            <div className="flex justify-between items-center bg-adcc-secondary/40 border border-gray-850 p-2.5 rounded-lg">
              <span className="text-adcc-textMuted uppercase">Primary Data Center</span>
              <span className="font-bold text-adcc-success">MUMBAI-CENTRAL</span>
            </div>
          </div>
        </motion.div>
      </div>

    </PageContainer>
  );
};
export default Dashboard;
