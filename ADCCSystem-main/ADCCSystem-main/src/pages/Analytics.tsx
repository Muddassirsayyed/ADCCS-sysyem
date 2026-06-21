import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import SectionHeader from '../components/SectionHeader';
import { 
  BarChart, 
  Bar, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { 
  FileSpreadsheet, 
  Calendar, 
  TrendingUp, 
  Clock, 
  Users,
  Compass
} from 'lucide-react';

export const Analytics: React.FC = () => {
  const [timeRange, setTimeRange] = useState<string>('30d');

  // Mock Analytics Data
  const resolutionSpeedData = [
    { month: 'Jan', Cyclones: 45, Wildfires: 30, Floods: 24 },
    { month: 'Feb', Cyclones: 40, Wildfires: 28, Floods: 20 },
    { month: 'Mar', Cyclones: 38, Wildfires: 25, Floods: 18 },
    { month: 'Apr', Cyclones: 32, Wildfires: 22, Floods: 15 },
    { month: 'May', Cyclones: 28, Wildfires: 18, Floods: 12 },
    { month: 'Jun', Cyclones: 24, Wildfires: 15, Floods: 10 }
  ];

  const shelterData = [
    { name: 'Shelter Alpha (West)', Occupancy: 82, Capacity: 100 },
    { name: 'Shelter Beta (Coast)', Occupancy: 95, Capacity: 100 },
    { name: 'Shelter Gamma (Metro)', Occupancy: 45, Capacity: 100 },
    { name: 'Shelter Delta (North)', Occupancy: 62, Capacity: 100 },
    { name: 'Shelter Epsilon (South)', Occupancy: 28, Capacity: 100 }
  ];

  const pieData = [
    { name: 'Contained Incidents', value: 42, color: '#00E5FF' },
    { name: 'Active Incidents', value: 12, color: '#EF4444' },
    { name: 'Resolved Incidents', value: 145, color: '#10B981' }
  ];

  return (
    <PageContainer>
      <SectionHeader 
        title="Historical Reports & Analytics" 
        description="Review multi-agent response latency, structural damage projections, and shelter occupancy indexes."
        actions={
          <div className="flex items-center gap-2">
            <Calendar size={14} className="text-adcc-accent" />
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="bg-adcc-bg border border-gray-800 text-adcc-textPrimary text-xs rounded-lg px-2.5 py-1.5 font-mono outline-none focus:border-adcc-accent"
            >
              <option value="7d">LAST 7 DAYS</option>
              <option value="30d">LAST 30 DAYS</option>
              <option value="6m">LAST 6 MONTHS</option>
              <option value="1y">LAST 1 YEAR</option>
            </select>
            <button 
              className="flex items-center gap-1.5 px-3 py-1.5 bg-adcc-accent/15 border border-adcc-accent/25 hover:bg-adcc-accent hover:text-adcc-bg text-xs font-mono font-bold uppercase tracking-wider rounded transition-all duration-200"
            >
              <FileSpreadsheet size={13} /> Export XLS
            </button>
          </div>
        }
      />

      {/* Aggregate metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        <div className="glass-panel border border-gray-800 rounded-xl p-4 flex items-center gap-4">
          <div className="p-3 bg-adcc-success/10 border border-adcc-success/20 rounded-lg text-adcc-success">
            <TrendingUp size={24} />
          </div>
          <div className="flex flex-col font-mono">
            <span className="text-[10px] text-adcc-textMuted uppercase">Mean Response Time (MRT)</span>
            <span className="text-2xl font-bold text-adcc-textPrimary mt-1">16.3 mins</span>
            <span className="text-[9px] text-adcc-success mt-0.5">-4.2% FROM PREV PERIOD</span>
          </div>
        </div>

        <div className="glass-panel border border-gray-800 rounded-xl p-4 flex items-center gap-4">
          <div className="p-3 bg-adcc-accent/10 border border-adcc-accent/20 rounded-lg text-adcc-accent">
            <Clock size={24} />
          </div>
          <div className="flex flex-col font-mono">
            <span className="text-[10px] text-adcc-textMuted uppercase">Evacuation Dispatch Latency</span>
            <span className="text-2xl font-bold text-adcc-textPrimary mt-1">3.4 mins</span>
            <span className="text-[9px] text-adcc-success mt-0.5">NOMINAL RESPONSE INDEX</span>
          </div>
        </div>

        <div className="glass-panel border border-gray-800 rounded-xl p-4 flex items-center gap-4">
          <div className="p-3 bg-adcc-warning/10 border border-adcc-warning/20 rounded-lg text-adcc-warning">
            <Users size={24} />
          </div>
          <div className="flex flex-col font-mono">
            <span className="text-[10px] text-adcc-textMuted uppercase">Shelter Buffer Capacity</span>
            <span className="text-2xl font-bold text-adcc-textPrimary mt-1">42.8%</span>
            <span className="text-[9px] text-adcc-warning mt-0.5">HIGH DENSITY TRIGGER STAGE 1</span>
          </div>
        </div>

      </div>

      {/* Main charts grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Latency curve chart */}
        <div className="xl:col-span-2 glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <h3 className="font-bold text-sm tracking-wider font-mono uppercase text-adcc-textPrimary">
              Average Resolution Speed (Minutes per incident)
            </h3>
            <span className="text-[10px] font-mono text-adcc-accent uppercase font-bold">Optimization Curve</span>
          </div>
          
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={resolutionSpeedData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="month" stroke="#9CA3AF" fontSize={11} tickLine={false} />
                <YAxis stroke="#9CA3AF" fontSize={11} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111827', border: '1px solid rgba(0, 229, 255, 0.2)', borderRadius: '8px', color: '#F9FAFB', fontFamily: 'monospace' }}
                  itemStyle={{ fontSize: '11px' }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace', paddingTop: '10px' }} />
                <Line type="monotone" dataKey="Cyclones" stroke="#EF4444" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="Wildfires" stroke="#F59E0B" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="Floods" stroke="#00E5FF" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Incident status breakdown pie */}
        <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <h3 className="font-bold text-sm tracking-wider font-mono uppercase text-adcc-textPrimary">
              Crisis Resolution Ratio
            </h3>
          </div>
          
          <div className="h-56 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111827', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', color: '#F9FAFB', fontFamily: 'monospace' }}
                  itemStyle={{ fontSize: '11px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-3 gap-1 text-[10px] font-mono text-center">
            {pieData.map((d, idx) => (
              <div key={idx} className="flex flex-col gap-1 items-center">
                <span className="w-3 h-1.5 rounded-full inline-block" style={{ backgroundColor: d.color }} />
                <span className="text-adcc-textMuted uppercase truncate max-w-[80px]">{d.name.split(' ')[0]}</span>
                <span className="text-adcc-textPrimary font-bold">{d.value}</span>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Shelter capacity bar chart */}
      <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <h3 className="font-bold text-sm tracking-wider font-mono uppercase text-adcc-textPrimary flex items-center gap-2">
            <Compass size={16} className="text-adcc-accent animate-pulse" />
            Evacuation Camps Occupancy Status
          </h3>
          <span className="text-[10px] font-mono text-adcc-accent uppercase">Live GIS telemetry feeds</span>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={shelterData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
              <XAxis dataKey="name" stroke="#9CA3AF" fontSize={10} tickLine={false} />
              <YAxis stroke="#9CA3AF" fontSize={11} tickLine={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#111827', border: '1px solid rgba(0, 229, 255, 0.2)', borderRadius: '8px', color: '#F9FAFB', fontFamily: 'monospace' }}
                itemStyle={{ fontSize: '11px' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace', paddingTop: '10px' }} />
              <Bar dataKey="Occupancy" fill="#F59E0B" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Capacity" fill="rgba(255, 255, 255, 0.05)" stroke="rgba(255, 255, 255, 0.1)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </PageContainer>
  );
};
export default Analytics;
