import React from 'react';
import { motion } from 'framer-motion';
import { Clock, CheckCircle2, ShieldAlert } from 'lucide-react';

export interface TimelineItem {
  time: string;
  title: string;
  description: string;
  status: 'completed' | 'active' | 'pending' | 'warning';
  nodeName: string;
}

interface AgentTimelineProps {
  trace?: string[];
  severityLevel?: string;
  replanningActions?: any[];
}

export const AgentTimeline: React.FC<AgentTimelineProps> = ({
  trace = [],
  severityLevel = 'Low',
  replanningActions = []
}) => {
  // Determine standard timestamps based on node execution trace
  const hasNode = (node: string) => trace.includes(node) || trace.some(t => t.includes(node));
  const isLast = (node: string) => trace.length > 0 && trace[trace.length - 1].includes(node);

  const getStatus = (node: string): 'completed' | 'active' | 'pending' => {
    if (isLast(node)) return 'active';
    if (hasNode(node)) return 'completed';
    return 'pending';
  };

  const steps: TimelineItem[] = [
    {
      time: hasNode('data_collection_agent') ? '09:30 IST' : '--:--',
      title: 'Data Collection Ingestion',
      description: 'Open-Meteo, GDACS, USGS, and DB Resource registry sync complete.',
      status: getStatus('data_collection_agent'),
      nodeName: 'data_collection_agent'
    },
    {
      time: hasNode('verification_agent') ? '09:31 IST' : '--:--',
      title: 'Disaster Verification',
      description: 'Cross-analyzing NewsAPI reports and met sensors. Consensus achieved.',
      status: getStatus('verification_agent'),
      nodeName: 'verification_agent'
    },
    {
      time: hasNode('severity_agent') ? '09:32 IST' : '--:--',
      title: `Severity Score Assessment`,
      description: hasNode('severity_agent') 
        ? `Disaster severity evaluated as ${severityLevel.toUpperCase()}.`
        : 'Calculating population exposure and resource stress matrix.',
      status: getStatus('severity_agent'),
      nodeName: 'severity_agent'
    },
    {
      time: hasNode('allocation_agent') ? '09:33 IST' : '--:--',
      title: 'Logistics & Resource Allocation',
      description: 'Calculated optimal equipment dispatch routes. Warehouse lock confirmed.',
      status: getStatus('allocation_agent'),
      nodeName: 'allocation_agent'
    },
    {
      time: hasNode('shelter_agent') ? '09:34 IST' : '--:--',
      title: 'Shelter Routing Assignment',
      description: 'Assigning affected population to closest shelters sequentially.',
      status: getStatus('shelter_agent'),
      nodeName: 'shelter_agent'
    },
    {
      time: hasNode('route_planning_agent') ? '09:35 IST' : '--:--',
      title: 'Evacuation Route Planning',
      description: 'Calculated primary and alternative evacuation routes to shelters.',
      status: getStatus('route_planning_agent'),
      nodeName: 'route_planning_agent'
    },
    {
      time: hasNode('notification_agent') ? '09:36 IST' : '--:--',
      title: 'Emergency Notification Dispatch',
      description: 'Dispatched Twilio SMS and WhatsApp alerts to emergency contacts.',
      status: getStatus('notification_agent'),
      nodeName: 'notification_agent'
    },
    {
      time: hasNode('replanning_agent') ? '09:37 IST' : '--:--',
      title: 'Dynamic Replanning Monitor',
      description: replanningActions.length > 0 
        ? `${replanningActions.length} replanning triggers active. Updated plans pushed.`
        : 'Monitoring incoming rainfall anomalies, capacity bottlenecks, and aftershocks.',
      status: replanningActions.length > 0 ? 'warning' : getStatus('replanning_agent') as any,
      nodeName: 'replanning_agent'
    }
  ];

  const containerVariants = {
    hidden: {},
    show: {
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, x: -10 },
    show: { opacity: 1, x: 0, transition: { duration: 0.3 } }
  };

  return (
    <div className="glass-panel border border-gray-800 rounded-xl p-5 bg-[#090E1A]/60 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-gray-850 pb-3">
        <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
          <Clock size={14} className="text-adcc-accent" />
          LangGraph Agent Execution Timeline
        </h3>
        <span className="text-[9px] font-mono text-adcc-textMuted uppercase">Telemetry Streams</span>
      </div>

      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-col relative pl-6 border-l border-gray-800 space-y-5 py-2"
      >
        {steps.map((step, idx) => {
          const isCompleted = step.status === 'completed';
          const isActive = step.status === 'active';
          const isWarning = step.status === 'warning';
          
          return (
            <motion.div 
              key={idx} 
              variants={itemVariants}
              className="relative flex flex-col gap-1 text-xs"
            >
              {/* Timeline Indicator Dot */}
              <span className={`absolute -left-[31px] top-0.5 flex items-center justify-center rounded-full border shadow-sm transition-all duration-300 ${
                isCompleted ? 'bg-[#10B981]/10 border-[#10B981]/40 text-[#10B981] p-0.5' :
                isWarning ? 'bg-adcc-warning/15 border-adcc-warning/40 text-adcc-warning p-0.5 animate-pulse' :
                isActive ? 'bg-adcc-accent/20 border-adcc-accent text-adcc-accent p-0.5 shadow-glow animate-pulse' :
                'bg-gray-900 border-gray-800 text-gray-600 p-0.5'
              }`}>
                {isCompleted ? <CheckCircle2 size={10} /> : 
                 isWarning ? <ShieldAlert size={10} /> :
                 isActive ? <span className="h-1.5 w-1.5 bg-adcc-accent rounded-full" /> : 
                 <span className="h-1.5 w-1.5 bg-gray-700 rounded-full" />}
              </span>

              {/* Header */}
              <div className="flex justify-between items-center font-mono">
                <span className={`font-bold tracking-wider ${
                  isCompleted ? 'text-adcc-textPrimary' :
                  isWarning ? 'text-adcc-warning font-bold' :
                  isActive ? 'text-adcc-accent font-bold' :
                  'text-adcc-textMuted'
                }`}>
                  {step.title}
                </span>
                <span className="text-[10px] text-adcc-textMuted">{step.time}</span>
              </div>

              {/* Description */}
              <p className="text-[11px] leading-relaxed text-adcc-textMuted font-sans">
                {step.description}
              </p>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
};
export default AgentTimeline;
