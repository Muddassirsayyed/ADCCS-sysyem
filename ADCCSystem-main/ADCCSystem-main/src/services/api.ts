import axios from 'axios';

// Backend URL configuration
const BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interfaces matching Backend Pydantic Schemas
export interface BackendDisaster {
  id: string;
  title: string;
  disaster_type: 'Flood' | 'Cyclone' | 'Earthquake' | 'Wildfire' | 'Heatwave' | 'Landslide';
  severity: 'Low' | 'Medium' | 'High' | 'Critical';
  status: 'Active' | 'Monitoring' | 'Resolved' | 'Archived';
  latitude: number;
  longitude: number;
  affected_population?: number;
  confidence_score?: number;
  source?: string;
  source_type?: string;
  source_url?: string;
  verification_status: 'Unverified' | 'Pending' | 'Verified' | 'Rejected';
  last_verified_at?: string;
  created_at: string;
  updated_at: string;
}

export interface BackendResource {
  id: string;
  resource_name: string;
  resource_type: 'Boat' | 'Ambulance' | 'Medical_Team' | 'Rescue_Team' | 'Helicopter' | 'Food_Truck' | 'NDRF_Unit';
  status: 'Available' | 'Busy' | 'Maintenance';
  quantity: number;
  latitude?: number;
  longitude?: number;
  last_updated: string;
}

export interface BackendHospital {
  id: string;
  name: string;
  city: string;
  total_beds: number;
  available_beds: number;
  latitude: number;
  longitude: number;
}

export interface BackendShelter {
  id: string;
  name: string;
  city: string;
  capacity: number;
  occupied: number;
  latitude: number;
  longitude: number;
}

export interface BackendAlert {
  id: string;
  title: string;
  severity: 'Low' | 'Medium' | 'High' | 'Critical';
  message: string;
  source?: string;
  source_type?: string;
  source_url?: string;
  confidence_score?: number;
  created_at: string;
}

export interface BackendSyncLog {
  id: string;
  source_name: string;
  sync_status: 'Success' | 'Failed' | 'Partial' | 'Running';
  records_fetched?: number;
  error_message?: string;
  started_at: string;
  completed_at?: string;
}

export interface BackendVerificationLog {
  id: string;
  disaster_id: string;
  source_checked: string;
  result: string;
  confidence: number;
  notes?: string;
  created_at: string;
}

export interface BackendAllocation {
  id: string;
  disaster_id: string;
  resource_id: string;
  quantity: number;
  allocation_reason?: string;
  status: 'Active' | 'Completed' | 'Cancelled';
  allocated_at: string;
  completed_at?: string;
}

export interface BackendSimulation {
  id: string;
  scenario_name: string;
  rainfall_change?: number;
  wind_speed_change?: number;
  population_change?: number;
  result_summary?: string;
  predicted_severity?: string;
  created_at: string;
}

export interface SystemHealthResponse {
  status: string;
  database: string;
  stats: {
    disasters: number;
    resources: number;
  };
}

export interface OrchestrationResult {
  status: 'success' | 'error';
  severity: 'Low' | 'Medium' | 'High' | 'Critical';
  confidence: number;
  resources_allocated: boolean;
  shelters_assigned: boolean;
  session_id: string;
  disasters_created: string[];
  replanning_actions: Array<{
    type: string;
    trigger: string;
    action: string;
    reason: string;
  }>;
  recommendations: string[];
  node_trace: string[];
  state: any;
}

export interface DemoRunResult {
  verified_reports: any[];
  severity_score: number;
  allocation_plan: any;
  shelter_plan: any;
  replanning_actions: any[];
  node_trace: string[];
  disasters_created: string[];
}

// API Service Methods
export const apiService = {
  // Health
  getHealth: async (): Promise<SystemHealthResponse> => {
    const { data } = await api.get<SystemHealthResponse>('/health');
    return data;
  },

  // Disasters
  getDisasters: async (): Promise<BackendDisaster[]> => {
    const { data } = await api.get<BackendDisaster[]>('/api/disasters');
    return data;
  },
  
  createDisaster: async (disaster: Omit<BackendDisaster, 'id' | 'created_at' | 'updated_at'>): Promise<BackendDisaster> => {
    const { data } = await api.post<BackendDisaster>('/api/disasters', disaster);
    return data;
  },

  syncDisasters: async (): Promise<{ status: string; synced_count: number }> => {
    const { data } = await api.post<{ status: string; synced_count: number }>('/api/disasters/sync');
    return data;
  },

  // Resources
  getResources: async (): Promise<BackendResource[]> => {
    const { data } = await api.get<BackendResource[]>('/api/resources');
    return data;
  },

  // Hospitals & Shelters
  getHospitals: async (): Promise<BackendHospital[]> => {
    const { data } = await api.get<BackendHospital[]>('/api/hospitals');
    return data;
  },

  getShelters: async (): Promise<BackendShelter[]> => {
    const { data } = await api.get<BackendShelter[]>('/api/shelters');
    return data;
  },

  // Alerts
  getAlerts: async (): Promise<BackendAlert[]> => {
    const { data } = await api.get<BackendAlert[]>('/api/alerts');
    return data;
  },
  
  createAlert: async (alert: Omit<BackendAlert, 'id' | 'created_at'>): Promise<BackendAlert> => {
    const { data } = await api.post<BackendAlert>('/api/alerts', alert);
    return data;
  },

  // Logs
  getSyncLogs: async (): Promise<BackendSyncLog[]> => {
    const { data } = await api.get<BackendSyncLog[]>('/api/sync-logs');
    return data;
  },

  getVerificationLogs: async (): Promise<BackendVerificationLog[]> => {
    const { data } = await api.get<BackendVerificationLog[]>('/api/verification-logs');
    return data;
  },

  // Allocations
  getAllocations: async (): Promise<BackendAllocation[]> => {
    const { data } = await api.get<BackendAllocation[]>('/api/allocations');
    return data;
  },
  
  createAllocation: async (allocation: Omit<BackendAllocation, 'id' | 'allocated_at'>): Promise<BackendAllocation> => {
    const { data } = await api.post<BackendAllocation>('/api/allocations', allocation);
    return data;
  },

  recommendAllocation: async (disasterId: string): Promise<{
    resource_id: string;
    resource_name: string;
    quantity: number;
    distance_km: number;
    route_name: string;
    recommendation_reason: string;
  }> => {
    const { data } = await api.get(`/api/allocations/recommend?disaster_id=${disasterId}`);
    return data;
  },

  // Simulations
  getSimulations: async (): Promise<BackendSimulation[]> => {
    const { data } = await api.get<BackendSimulation[]>('/api/simulations');
    return data;
  },

  runSimulation: async (payload: SimulationRunRequest): Promise<SimulationRunResult> => {
    const { data } = await api.post<SimulationRunResult>('/api/simulations/run', payload);
    return data;
  },

  // LangGraph Orchestration Pipeline
  runOrchestration: async (payload: {
    latitude: number;
    longitude: number;
    location_label: string;
    country: string;
    disaster_title?: string;
    disaster_type?: string;
  }): Promise<OrchestrationResult> => {
    const { data } = await api.post<OrchestrationResult>('/api/orchestration/run', payload);
    return data;
  },

  // Demo Mode Pipeline
  runDemoScenario: async (payload: {
    scenario: 'Mumbai Flood' | 'Gujarat Cyclone' | 'Kashmir Earthquake';
    severity?: string;
  }): Promise<DemoRunResult> => {
    const { data } = await api.post<DemoRunResult>('/api/demo/run', payload);
    return data;
  },

  // AI Command Center Chatbot & Explainers
  sendChatMessage: async (message: string, history: ChatMessage[]): Promise<string> => {
    const { data } = await api.post<{ answer: string }>('/api/command-center/chat', {
      message,
      conversation_history: history,
    });
    return data.answer;
  },

  getCognitiveSummary: async (): Promise<string> => {
    const { data } = await api.get<{ summary: string }>('/api/command-center/summary');
    return data.summary;
  },

  getSeverityExplanation: async (): Promise<string> => {
    const { data } = await api.get<{ explanation: string }>('/api/command-center/explain-severity');
    return data.explanation;
  },

  getAllocationExplanation: async (): Promise<string> => {
    const { data } = await api.get<{ explanation: string }>('/api/command-center/explain-allocation');
    return data.explanation;
  },

  getShelterExplanation: async (): Promise<string> => {
    const { data } = await api.get<{ explanation: string }>('/api/command-center/explain-shelters');
    return data.explanation;
  },

  getActionRecommendations: async (): Promise<string> => {
    const { data } = await api.get<{ recommendations: string }>('/api/command-center/recommendations');
    return data.recommendations;
  },
};

export interface ChatMessage {
  role: 'user' | 'model';
  content: string;
}

export interface SimulationRunRequest {
  simulation_type: 'Flood' | 'Cyclone' | 'Earthquake';
  rainfall_change_pct: number;
  wind_speed_change_pct: number;
  population_change_pct: number;
  shelter_capacity_change_pct: number;
  resource_availability_change_pct: number;
  disaster_id?: string;
}

export interface SimulationRunResult {
  id: string;
  scenario_name: string;
  created_at: string;
  summary: {
    simulation_type: string;
    location: string;
    coordinates: { latitude: number; longitude: number };
    inputs: {
      rainfall_change_pct: number;
      wind_speed_change_pct: number;
      population_change_pct: number;
      shelter_capacity_change_pct: number;
      resource_availability_change_pct: number;
    };
    baseline: {
      affected_population: number;
      severity: string;
    };
    predicted: {
      affected_population: number;
      severity_level: 'Low' | 'Medium' | 'High' | 'Critical';
      severity_score: number;
      breakdown: {
        population_impact_score: number;
        weather_risk_score: number;
        disaster_magnitude_score: number;
        resource_stress_score: number;
      };
    };
    resource_metrics: {
      required: Record<string, number>;
      simulated_available: Record<string, number>;
      gap: Record<string, number>;
      total_gap_units: number;
    };
    shelter_metrics: {
      affected_population: number;
      assigned_population: number;
      unassigned_population: number;
      total_simulated_capacity: number;
      total_occupied_slots: number;
      shelter_assignments: Array<{
        shelter_name: string;
        distance_km: number;
        assigned_people: number;
        simulated_capacity: number;
        new_occupancy_pct: number;
      }>;
    };
  };
}

export default apiService;
