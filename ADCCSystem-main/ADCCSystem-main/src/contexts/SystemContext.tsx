import React, { createContext, useContext, useState, useEffect } from 'react';

export interface Disaster {
  id: string;
  name: string;
  type: 'earthquake' | 'wildfire' | 'flood' | 'cyclone';
  severity: 'critical' | 'major' | 'minor';
  location: string;
  lat: number;
  lng: number;
  affectedPopulation: number;
  status: 'active' | 'contained' | 'resolved';
  timestamp: string;
  description: string;
}

export interface ResourceItem {
  name: string;
  total: number;
  available: number;
  unit: string;
}

export interface ResourceStatus {
  personnel: ResourceItem;
  medicalDrones: ResourceItem;
  shelters: ResourceItem;
  vehicles: ResourceItem;
  rations: ResourceItem;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  status: 'idle' | 'processing' | 'success' | 'alert';
  currentTask: string;
  lastActive: string;
  logs: string[];
}

export interface AlertNotification {
  id: string;
  title: string;
  message: string;
  severity: 'critical' | 'warning' | 'info';
  timestamp: string;
  source: string;
  read: boolean;
}

interface SystemContextType {
  disasters: Disaster[];
  resources: ResourceStatus;
  agents: Agent[];
  notifications: AlertNotification[];
  systemStatus: 'nominal' | 'alert' | 'simulation';
  setSystemStatus: (status: 'nominal' | 'alert' | 'simulation') => void;
  addDisaster: (disaster: Disaster) => void;
  resolveDisaster: (id: string) => void;
  dispatchResources: (resourceName: keyof ResourceStatus, count: number) => boolean;
  replenishResources: (resourceName: keyof ResourceStatus, count: number) => void;
  triggerNotification: (title: string, message: string, severity: 'critical' | 'warning' | 'info', source: string) => void;
  markAllNotificationsRead: () => void;
  runSimulation: (type: 'earthquake' | 'wildfire' | 'flood' | 'cyclone', intensity: number, radiusKm: number, locationName: string) => void;
  sendAgentCommand: (agentId: string, cmd: string) => void;
}

const SystemContext = createContext<SystemContextType | undefined>(undefined);

export const SystemProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [systemStatus, setSystemStatus] = useState<'nominal' | 'alert' | 'simulation'>('alert');
  
  // Mock Active Disasters
  const [disasters, setDisasters] = useState<Disaster[]>([
    {
      id: 'd-1',
      name: 'Cyclone Tasha - Coastal Storm Surge',
      type: 'cyclone',
      severity: 'critical',
      location: 'Sector 4-B, East Bay Coastline',
      lat: 22.3482,
      lng: 88.5429,
      affectedPopulation: 145000,
      status: 'active',
      timestamp: '10 mins ago',
      description: 'Category 4 cyclonic storm landfall with wind speeds up to 180 km/h causing major storm surge and electrical grid collapse.'
    },
    {
      id: 'd-2',
      name: 'Wildfire Outbreak - Ridge Ridge Forest',
      type: 'wildfire',
      severity: 'major',
      location: 'Sector 9-A, North Valley Forest Reserve',
      lat: 23.1205,
      lng: 87.2045,
      affectedPopulation: 28000,
      status: 'active',
      timestamp: '42 mins ago',
      description: 'Rapidly spreading canopy fire fueled by high summer winds and prolonged dry conditions. Evacuations in progress for surrounding foothills.'
    },
    {
      id: 'd-3',
      name: 'Flash Flood - Urban Drainage Overflow',
      type: 'flood',
      severity: 'minor',
      location: 'Metropolitan Sector 1',
      lat: 22.5726,
      lng: 88.3639,
      affectedPopulation: 12500,
      status: 'contained',
      timestamp: '2 hours ago',
      description: 'Intense cloudburst overwhelmed municipal storm sewers. Water levels stabilized, recovery teams pumping residential basements.'
    }
  ]);

  // Mock Resources
  const [resources, setResources] = useState<ResourceStatus>({
    personnel: { name: 'Rescue Specialists (NDRF)', total: 1200, available: 450, unit: 'personnel' },
    medicalDrones: { name: 'Emergency Medical Drones', total: 80, available: 32, unit: 'units' },
    shelters: { name: 'Relief Shelters', total: 24, available: 9, unit: 'camps' },
    vehicles: { name: 'Amphibious Rescue Vehicles', total: 150, available: 68, unit: 'vehicles' },
    rations: { name: 'Food & Medical Rations', total: 50000, available: 31200, unit: 'kits' }
  });

  // Mock Agents (Multi-Agent framework logs)
  const [agents, setAgents] = useState<Agent[]>([
    {
      id: 'a-1',
      name: 'Data Collection Agent',
      role: 'Monitors news, weather, satellite, and social streams.',
      status: 'processing',
      currentTask: 'Scanning NOAA satellite data feeds & Twitter sentiment for fire perimeters.',
      lastActive: 'Just now',
      logs: [
        '[12:30:05] Initialized NOAA/GDACS listener endpoints.',
        '[12:32:15] Ingesting local news reports of smoke columns near Sector 9-A.',
        '[12:33:02] Satellite thermal infrared sensor shows hotspots at 23.1205 N, 87.2045 E.',
        '[12:34:50] Scraping geo-tagged social media data. High keyword clusters for "fire", "smoke", "evacuate".'
      ]
    },
    {
      id: 'a-2',
      name: 'Verification Agent',
      role: 'Cross-references feeds and generates confidence metrics.',
      status: 'success',
      currentTask: 'Standby. Verification confidence for Cyclone Tasha is locked at 98.4%.',
      lastActive: '2 mins ago',
      logs: [
        '[12:31:00] Analyzing Incident ID d-2 (Wildfire).',
        '[12:32:45] Cross-checking satellite thermal anomaly with local meteorological sensors.',
        '[12:33:30] Forest wind telemetry matches wildfire spread speed parameters.',
        '[12:34:10] Incident d-2 verified. Confidence rating: 92.1% (Sensor triangulation + Social corroboration).'
      ]
    },
    {
      id: 'a-3',
      name: 'Severity Agent',
      role: 'Assesses population density and infrastructure risk.',
      status: 'processing',
      currentTask: 'Evaluating critical grid impact in Sector 4-B.',
      lastActive: '1 min ago',
      logs: [
        '[12:31:20] Fetching GIS layout layers for Sector 9-A.',
        '[12:33:15] Overlaying forest boundary with residential zone metadata.',
        '[12:34:00] Estimated population exposure: 28,000 residents in direct wind vector.',
        '[12:34:45] Infrastructure warning: High-voltage substation located 2.4km from active fire front.'
      ]
    },
    {
      id: 'a-4',
      name: 'Allocation Agent',
      role: 'Calculates logistics paths and relief distributions.',
      status: 'alert',
      currentTask: 'Requesting allocation confirmation for medical drones in Sector 4-B.',
      lastActive: 'Just now',
      logs: [
        '[12:32:00] Processing supply levels for Cyclone Tasha surge victims.',
        '[12:33:40] Warehouse inventory query: Sector 4 depot rations at 12% capacity.',
        '[12:34:20] Calculated route: NDRF Base to Coastal Camp 2 is BLOCKED due to waterlogging.',
        '[12:34:55] ALERT: Resource deficit detected. Drone deployment required for medical kit drop-off.'
      ]
    },
    {
      id: 'a-5',
      name: 'Shelter Agent',
      role: 'Manages evacuee routing and camp capacities.',
      status: 'processing',
      currentTask: 'Rerouting Sector 9-A evacuees from Shelter 3 (Full) to Shelter 5.',
      lastActive: '5 mins ago',
      logs: [
        '[12:20:10] Shelter 3 capacity reached (350/350 evacuees). Locking entrance.',
        '[12:25:35] Recalculating evacuation vectors for remaining sector population.',
        '[12:30:10] Activating secondary emergency shelter (Shelter 5 - Capacity 500).',
        '[12:34:15] Sending localized navigation routes to evacuation transit dispatch.'
      ]
    },
    {
      id: 'a-6',
      name: 'Replanning Agent',
      role: 'Dynamic path optimization and rescue coordination.',
      status: 'idle',
      currentTask: 'Idling. Monitoring road block updates.',
      lastActive: '12 mins ago',
      logs: [
        '[12:05:00] Initialized street camera analysis service.',
        '[12:15:30] Rerouted NDRF Unit 3 around highway blockage (Bridge collapsed). Route optimized.',
        '[12:22:15] Monitoring status of coastal road closures.'
      ]
    }
  ]);

  // Mock Notifications
  const [notifications, setNotifications] = useState<AlertNotification[]>([
    {
      id: 'n-1',
      title: 'CRITICAL: Storm Surge Inundation',
      message: 'Coastal defenses breached in Sector 4-B. Water levels rising 1.5m per hour.',
      severity: 'critical',
      timestamp: '5 mins ago',
      source: 'GDACS Sensor Stream',
      read: false
    },
    {
      id: 'n-2',
      title: 'WARNING: Forest Fire Boundary Expansion',
      message: 'Wildfire in Sector 9-A has breached the northern containment line.',
      severity: 'warning',
      timestamp: '22 mins ago',
      source: 'Satellite Imagery Agent',
      read: false
    },
    {
      id: 'n-3',
      title: 'INFO: Drone Transit Active',
      message: 'Dispatching 12 medical drones to deliver insulin and trauma kits to Sector 4-B.',
      severity: 'info',
      timestamp: '35 mins ago',
      source: 'Allocation Agent',
      read: true
    }
  ]);

  // Handle new notifications
  const triggerNotification = (title: string, message: string, severity: 'critical' | 'warning' | 'info', source: string) => {
    const newAlert: AlertNotification = {
      id: `n-${Date.now()}`,
      title,
      message,
      severity,
      timestamp: 'Just now',
      source,
      read: false
    };
    setNotifications(prev => [newAlert, ...prev]);
    if (severity === 'critical') setSystemStatus('alert');
  };

  const markAllNotificationsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  // Add a disaster
  const addDisaster = (disaster: Disaster) => {
    setDisasters(prev => [disaster, ...prev]);
    triggerNotification(
      `NEW DISASTER DETECTED: ${disaster.name}`,
      `A new ${disaster.type} has been initialized in ${disaster.location}. Estimated exposure: ${disaster.affectedPopulation.toLocaleString()} citizens.`,
      disaster.severity === 'critical' ? 'critical' : 'warning',
      'AI Command Center'
    );
  };

  // Resolve a disaster
  const resolveDisaster = (id: string) => {
    setDisasters(prev => 
      prev.map(d => d.id === id ? { ...d, status: 'resolved' } : d)
    );
    const resolvedDisaster = disasters.find(d => d.id === id);
    if (resolvedDisaster) {
      triggerNotification(
        `RESOLVED: ${resolvedDisaster.name}`,
        `Disaster status changed to RESOLVED. Clean up and logistics recovery active.`,
        'info',
        'Command Center'
      );
    }
  };

  // Dispatch resources
  const dispatchResources = (resourceName: keyof ResourceStatus, count: number): boolean => {
    let success = false;
    setResources(prev => {
      const resource = prev[resourceName];
      if (resource.available >= count) {
        success = true;
        return {
          ...prev,
          [resourceName]: {
            ...resource,
            available: resource.available - count
          }
        };
      }
      return prev;
    });

    if (success) {
      triggerNotification(
        `RESOURCES DISPATCHED: ${count} ${resources[resourceName].unit}`,
        `Deployed ${count} ${resources[resourceName].name} successfully.`,
        'info',
        'Allocation Agent'
      );
    }
    return success;
  };

  // Replenish resources
  const replenishResources = (resourceName: keyof ResourceStatus, count: number) => {
    setResources(prev => {
      const resource = prev[resourceName];
      return {
        ...prev,
        [resourceName]: {
          ...resource,
          available: Math.min(resource.total, resource.available + count)
        }
      };
    });
    triggerNotification(
      `INVENTORY UPDATE: ${resources[resourceName].name}`,
      `Restocked inventory. ${count} units processed into command database.`,
      'info',
      'Logistics Depot'
    );
  };

  // Run a scenario simulation
  const runSimulation = (type: 'earthquake' | 'wildfire' | 'flood' | 'cyclone', intensity: number, radiusKm: number, locationName: string) => {
    setSystemStatus('simulation');
    
    // Generate simulated coordinates
    const lat = 22.5 + (Math.random() - 0.5) * 1.5;
    const lng = 88.2 + (Math.random() - 0.5) * 1.5;
    
    const popMultiplier = type === 'earthquake' ? 8500 : type === 'flood' ? 3200 : type === 'cyclone' ? 6200 : 1500;
    const affectedPop = Math.round(intensity * radiusKm * popMultiplier);
    
    const severity = intensity > 7.5 ? 'critical' : intensity > 4.5 ? 'major' : 'minor';

    const newSimulatedDisaster: Disaster = {
      id: `sim-${Date.now()}`,
      name: `SIMULATION: ${type.toUpperCase()} - ${locationName}`,
      type,
      severity,
      location: locationName,
      lat,
      lng,
      affectedPopulation: affectedPop,
      status: 'active',
      timestamp: 'Just now',
      description: `Active simulation model. Intensity: ${intensity} units. Radius: ${radiusKm}km. Simulating structural load failures, emergency shelter capacity triggers, and rescue route flooding.`
    };

    // Add simulated disaster
    setDisasters(prev => [newSimulatedDisaster, ...prev]);

    // Update agent state
    setAgents(prev => prev.map(agent => {
      if (agent.id === 'a-1') {
        return {
          ...agent,
          status: 'processing',
          currentTask: `Ingesting simulated ${type} metrics at ${locationName}.`,
          logs: [`[SIMULATION START] Simulating sensor telemetry for ${type}.`, ...agent.logs]
        };
      }
      if (agent.id === 'a-3') {
        return {
          ...agent,
          status: 'processing',
          currentTask: `Simulating damage vectors for ${affectedPop} residents.`,
          logs: [`[SIMULATION] Assessing risk curves for intensity ${intensity}.`, ...agent.logs]
        };
      }
      return agent;
    }));

    triggerNotification(
      `SIMULATION TRIGGERED`,
      `Simulated ${type} registered in environment at ${locationName}. Critical severity warnings activated.`,
      'warning',
      'Simulation Engine'
    );
  };

  // Send interactive agent commands
  const sendAgentCommand = (agentId: string, cmd: string) => {
    setAgents(prev => prev.map(agent => {
      if (agent.id === agentId) {
        return {
          ...agent,
          status: 'processing',
          currentTask: `Executing command: ${cmd}`,
          logs: [`[Command Ingested] Operator issued: "${cmd}"`, ...agent.logs]
        };
      }
      return agent;
    }));

    // Add a delayed success log
    setTimeout(() => {
      setAgents(prev => prev.map(agent => {
        if (agent.id === agentId) {
          return {
            ...agent,
            status: 'success',
            currentTask: `Completed command: ${cmd}`,
            logs: [`[Command Completed] Result: SUCCESS. Command action parsed and indexed.`, ...agent.logs]
          };
        }
        return agent;
      }));
    }, 2000);
  };

  // Periodically add minor log logs to make dashboard feel ALIVE and dynamic!
  useEffect(() => {
    const logInterval = setInterval(() => {
      const agentIdx = Math.floor(Math.random() * agents.length);
      
      const randomLogs = [
        `Ingested stream update. Connection latency: ${Math.floor(Math.random() * 80) + 20}ms.`,
        `Telemetry heartbeat checked. 0 errors.`,
        `Rerouting algorithms executed. Paths optimal.`,
        `Scanning satellite grid references.`,
        `Updating emergency logistics database entries.`
      ];

      setAgents(prev => prev.map((agent, idx) => {
        if (idx === agentIdx) {
          const timestamp = new Date().toTimeString().split(' ')[0];
          return {
            ...agent,
            lastActive: 'Just now',
            logs: [`[${timestamp}] ${randomLogs[Math.floor(Math.random() * randomLogs.length)]}`, ...agent.logs.slice(0, 19)]
          };
        }
        return agent;
      }));
    }, 12000);

    return () => clearInterval(logInterval);
  }, [agents.length]);

  return (
    <SystemContext.Provider value={{
      disasters,
      resources,
      agents,
      notifications,
      systemStatus,
      setSystemStatus,
      addDisaster,
      resolveDisaster,
      dispatchResources,
      replenishResources,
      triggerNotification,
      markAllNotificationsRead,
      runSimulation,
      sendAgentCommand
    }}>
      {children}
    </SystemContext.Provider>
  );
};

export const useSystem = () => {
  const context = useContext(SystemContext);
  if (context === undefined) {
    throw new Error('useSystem must be used within a SystemProvider');
  }
  return context;
};
