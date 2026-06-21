import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService, { 
  BackendDisaster, 
  BackendHospital, 
  BackendShelter, 
  BackendResource 
} from '../services/api';
import PageContainer from '../components/PageContainer';
import SectionHeader from '../components/SectionHeader';
import { 
  Compass, 
  MapPin, 
  Flame, 
  Wind, 
  Droplets, 
  Activity, 
  Filter,
  HeartPulse,
  Home,
  Boxes,
  Map as MapIcon,
  RefreshCw
} from 'lucide-react';

type MapEntity = 
  | { type: 'disaster'; data: BackendDisaster }
  | { type: 'hospital'; data: BackendHospital }
  | { type: 'shelter'; data: BackendShelter }
  | { type: 'resource'; data: BackendResource }
  | { type: 'route'; data: any };

const getSimulatedRouteSteps = (res: BackendResource, dis: BackendDisaster, distKm: number) => {
  const steps: string[] = [];
  steps.push(`Depart ${res.resource_name} Depot location at (${res.latitude?.toFixed(3)}°N, ${res.longitude?.toFixed(3)}°E)`);
  
  let routeName = "National Highway Corridor";
  if (distKm < 200) {
    if (res.resource_name.includes("MH") || dis.title.toLowerCase().includes("mumbai") || dis.title.toLowerCase().includes("pune")) {
      routeName = "Mumbai-Pune Expressway / NH-48";
      steps.push("Merge onto NH-48 Expressway heading West towards Mumbai.");
      steps.push("Proceed through Lonavala toll plaza, keeping right at Expressway fork.");
      steps.push("Enter Mumbai Metropolitan Region via Vashi / Sion Corridor.");
    } else if (dis.title.toLowerCase().includes("rishikesh") || dis.title.toLowerCase().includes("delhi")) {
      routeName = "NH-334 Bypass Corridor";
      steps.push("Merge onto NH-58 / NH-334 heading North via Meerut-Haridwar Highway.");
      steps.push("Proceed along Haridwar bypass, keeping right towards Rishikesh.");
    } else {
      routeName = "State Highway Corridor";
      steps.push("Merge onto closest regional highway link heading towards incident zone.");
    }
  } else {
    if (dis.title.toLowerCase().includes("guwahati") || dis.title.toLowerCase().includes("assam") || dis.title.toLowerCase().includes("kolkata")) {
      routeName = "NH-27 East-West Highway Corridor";
      steps.push("Merge onto NH-12 heading North towards Siliguri corridor.");
      steps.push("Connect to NH-27 (East-West Highway) heading East via Bongaigaon.");
    } else {
      routeName = "National Highway Corridor (NH-27 / NH-48)";
      steps.push("Proceed along National Highway corridor towards target zone coordinates.");
    }
  }
  
  steps.push(`Arrive at ${dis.title} epicenter coordinates (${dis.latitude.toFixed(3)}°N, ${dis.longitude.toFixed(3)}°E) for emergency dispatch.`);
  return { routeName, steps };
};

const getDisasterMarkerHtml = (type: string, severity: string, status: string) => {
  let glowColor = 'rgba(16, 185, 129, 0.45)';
  let strokeColor = '#10B981';
  let innerColor = 'rgba(16, 185, 129, 0.15)';

  switch (severity.toLowerCase()) {
    case 'critical':
      glowColor = 'rgba(239, 68, 68, 0.45)';
      strokeColor = '#EF4444';
      innerColor = 'rgba(239, 68, 68, 0.15)';
      break;
    case 'high':
      glowColor = 'rgba(249, 115, 22, 0.45)';
      strokeColor = '#F97316';
      innerColor = 'rgba(249, 115, 22, 0.15)';
      break;
    case 'medium':
      glowColor = 'rgba(245, 158, 11, 0.45)';
      strokeColor = '#F59E0B';
      innerColor = 'rgba(245, 158, 11, 0.15)';
      break;
  }

  let svgPath = '';
  switch (type.toLowerCase()) {
    case 'flood':
      svgPath = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a7 7 0 0 0 7-7c0-4.3-7-11-7-11S5 10.7 5 15a7 7 0 0 0 7 7z"/></svg>`;
      break;
    case 'cyclone':
      svgPath = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12.8 3a2.4 2.4 0 0 0-2.2 3.1A2.4 2.4 0 0 0 12.8 8h6.2a2.4 2.4 0 0 0 0-4.8H12.8Z"/><path d="M8.2 11a2.4 2.4 0 0 0-2.2 3.1A2.4 2.4 0 0 0 8.2 16h8.2a2.4 2.4 0 0 0 0-4.8H8.2Z"/><path d="M5.4 7a2.4 2.4 0 0 0-2.2 3.1A2.4 2.4 0 0 0 5.4 12h11.2a2.4 2.4 0 0 0 0-4.8H5.4Z"/></svg>`;
      break;
    case 'earthquake':
      svgPath = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`;
      break;
    case 'wildfire':
      svgPath = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`;
      break;
    case 'heatwave':
      svgPath = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M6.34 17.66l-1.41 1.41"/><path d="M19.07 4.93l-1.41 1.41"/></svg>`;
      break;
    default:
      svgPath = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`;
  }

  return `
    <div class="relative flex items-center justify-center animate-fade-in" style="width: 38px; height: 38px;">
      ${status === 'Active' ? `
        <div class="absolute inset-0 rounded-full animate-ping opacity-20" style="background-color: ${glowColor}; animation-duration: 2.5s;"></div>
        <div class="absolute inset-1.5 rounded-full border border-dashed opacity-25 animate-spin" style="border-color: ${strokeColor}; animation-duration: 15s;"></div>
      ` : ''}
      <div class="absolute inset-1.5 rounded-full border-2 flex items-center justify-center shadow-lg backdrop-blur-md transition-all duration-300 hover:scale-110" 
           style="background: radial-gradient(circle, ${innerColor} 0%, rgba(11, 18, 32, 0.95) 100%); border-color: ${strokeColor}; box-shadow: 0 0 15px ${glowColor};">
        <div class="flex items-center justify-center" style="color: ${strokeColor};">
          ${svgPath}
        </div>
      </div>
    </div>
  `;
};

export const DisasterMap: React.FC = () => {
  const [selectedEntity, setSelectedEntity] = useState<MapEntity | null>(null);
  const queryClient = useQueryClient();

  const syncMutation = useMutation({
    mutationFn: apiService.syncDisasters,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['disasters'] });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    }
  });
  
  // Layer toggles
  const [showDisasters, setShowDisasters] = useState(true);
  const [showHospitals, setShowHospitals] = useState(true);
  const [showShelters, setShowShelters] = useState(true);
  const [showResources, setShowResources] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);

  // Filters
  const [filterType, setFilterType] = useState<string>('all');
  const [filterSeverity, setFilterSeverity] = useState<string>('all');

  // Map Refs
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markerLayerGroupRef = useRef<any>(null);

  // Fetch live layers
  const { data: disasters = [] } = useQuery({ queryKey: ['disasters'], queryFn: apiService.getDisasters });
  const { data: hospitals = [] } = useQuery({ queryKey: ['hospitals'], queryFn: apiService.getHospitals });
  const { data: shelters = [] } = useQuery({ queryKey: ['shelters'], queryFn: apiService.getShelters });
  const { data: resources = [] } = useQuery({ queryKey: ['resources'], queryFn: apiService.getResources });
  const { data: allocations = [] } = useQuery({ queryKey: ['allocations'], queryFn: apiService.getAllocations });

  // Filter disasters
  const filteredDisasters = disasters.filter(d => {
    const matchesType = filterType === 'all' || d.disaster_type.toLowerCase() === filterType.toLowerCase();
    const matchesSeverity = filterSeverity === 'all' || d.severity.toLowerCase() === filterSeverity.toLowerCase();
    return matchesType && matchesSeverity;
  });

  const getDisasterIcon = (type: string, size = 16) => {
    switch (type.toLowerCase()) {
      case 'wildfire': return <Flame size={size} className="text-[#F97316]" />;
      case 'cyclone': return <Wind size={size} className="text-[#EF4444]" />;
      case 'flood': return <Droplets size={size} className="text-[#00E5FF]" />;
      default: return <Activity size={size} className="text-[#A78BFA]" />;
    }
  };

  const getSeverityBorderColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'border-adcc-danger text-adcc-danger';
      case 'high': return 'border-[#F97316] text-[#F97316]';
      case 'medium': return 'border-adcc-warning text-adcc-warning';
      default: return 'border-adcc-success text-adcc-success';
    }
  };

  const getSeverityBadgeColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'bg-[#EF4444] text-white';
      case 'high': return 'bg-[#F97316] text-white';
      case 'medium': return 'bg-[#F59E0B] text-adcc-bg';
      default: return 'bg-[#10B981] text-white';
    }
  };



  // Broad fallback bounds
  const getMapBounds = () => {
    const points: Array<{ lat: number; lng: number }> = [];
    if (showDisasters) filteredDisasters.forEach(d => points.push({ lat: d.latitude, lng: d.longitude }));
    if (showHospitals) hospitals.forEach(h => points.push({ lat: h.latitude, lng: h.longitude }));
    if (showShelters) shelters.forEach(s => points.push({ lat: s.latitude, lng: s.longitude }));
    if (showResources) resources.forEach(r => { if (r.latitude && r.longitude) points.push({ lat: r.latitude, lng: r.longitude }); });

    if (points.length === 0) {
      return { minLat: 8.33, maxLat: 37.44, minLng: 65.22, maxLng: 97.68 };
    }
    const lats = points.map(p => p.lat);
    const lngs = points.map(p => p.lng);
    return {
      minLat: Math.min(...lats),
      maxLat: Math.max(...lats),
      minLng: Math.min(...lngs),
      maxLng: Math.max(...lngs)
    };
  };

  const bounds = getMapBounds();

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const L = (window as any).L;
    if (!L) {
      console.error("Leaflet library not loaded");
      return;
    }

    const map = L.map(mapContainerRef.current, {
      center: [20.5937, 78.9629], // Center of India
      zoom: 5,
      minZoom: 3,
      maxZoom: 18,
      attributionControl: false
    });

    mapInstanceRef.current = map;

    // Tile Layers
    const darkLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 20
    });

    const terrainLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 17
    });

    const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19
    });

    const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19
    });

    // Default layer
    darkLayer.addTo(map);

    const baseMaps = {
      "Dark View (ADCC Theme)": darkLayer,
      "Terrain (Elevation)": terrainLayer,
      "Satellite Imagery": satelliteLayer,
      "Street Map": streetLayer
    };

    L.control.layers(baseMaps, null, { position: 'topright' }).addTo(map);

    const markerLayerGroup = L.layerGroup().addTo(map);
    markerLayerGroupRef.current = markerLayerGroup;

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Markers when layers or filters change
  useEffect(() => {
    const L = (window as any).L;
    if (!L || !mapInstanceRef.current || !markerLayerGroupRef.current) return;

    const markerLayerGroup = markerLayerGroupRef.current;
    markerLayerGroup.clearLayers();

    // 1. Render Disasters
    if (showDisasters) {
      filteredDisasters.forEach(d => {
        const marker = L.marker([d.latitude, d.longitude], {
          icon: L.divIcon({
            className: 'custom-disaster-pin',
            html: getDisasterMarkerHtml(d.disaster_type, d.severity, d.status),
            iconSize: [38, 38],
            iconAnchor: [19, 19]
          })
        });
        marker.on('click', () => setSelectedEntity({ type: 'disaster', data: d }));
        marker.addTo(markerLayerGroup);
      });
    }

    // 2. Render Hospitals
    if (showHospitals) {
      hospitals.forEach(h => {
        const marker = L.marker([h.latitude, h.longitude], {
          icon: L.divIcon({
            className: 'custom-hospital-pin',
            html: `
              <div class="relative flex items-center justify-center animate-fade-in" style="width: 28px; height: 28px;">
                <div class="w-6 h-6 rounded-full border-2 border-white flex items-center justify-center text-white font-bold transition-all duration-200 hover:scale-115" 
                     style="background-color: #2563EB; box-shadow: 0 2px 5px rgba(0,0,0,0.65);">
                  <span class="text-[11px] font-sans font-black leading-none" style="margin-top: -0.5px;">H</span>
                </div>
              </div>
            `,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          })
        });
        marker.on('click', () => setSelectedEntity({ type: 'hospital', data: h }));
        marker.addTo(markerLayerGroup);
      });
    }

    // 3. Render Shelters
    if (showShelters) {
      shelters.forEach(s => {
        const marker = L.marker([s.latitude, s.longitude], {
          icon: L.divIcon({
            className: 'custom-shelter-pin',
            html: `
              <div class="relative flex items-center justify-center animate-fade-in" style="width: 28px; height: 28px;">
                <div class="w-6 h-6 rounded-full border-2 border-white flex items-center justify-center text-white transition-all duration-200 hover:scale-115" 
                     style="background-color: #D97706; box-shadow: 0 2px 5px rgba(0,0,0,0.65);">
                  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
                </div>
              </div>
            `,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          })
        });
        marker.on('click', () => setSelectedEntity({ type: 'shelter', data: s }));
        marker.addTo(markerLayerGroup);
      });
    }

    // 4. Render Resources
    if (showResources) {
      resources.forEach(r => {
        if (!r.latitude || !r.longitude) return;
        const marker = L.marker([r.latitude, r.longitude], {
          icon: L.divIcon({
            className: 'custom-resource-pin',
            html: `
              <div class="relative flex items-center justify-center animate-fade-in" style="width: 28px; height: 28px;">
                <div class="w-6 h-6 rounded-full border-2 border-white flex items-center justify-center text-white transition-all duration-200 hover:scale-115" 
                     style="background-color: #16A34A; box-shadow: 0 2px 5px rgba(0,0,0,0.65);">
                  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>
                </div>
              </div>
            `,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          })
        });
        marker.on('click', () => setSelectedEntity({ type: 'resource', data: r }));
        marker.addTo(markerLayerGroup);
      });
    }

    // 5. Render Routing Paths for Active Allocations
    if (showRoutes) {
      allocations.forEach(alloc => {
        if (alloc.status !== 'Active') return;
        
        const resource = resources.find(r => r.id === alloc.resource_id);
        const disaster = disasters.find(d => d.id === alloc.disaster_id);
        
        if (resource && disaster && resource.latitude && resource.longitude && disaster.latitude && disaster.longitude) {
          const distance = mapInstanceRef.current.distance(
            [resource.latitude, resource.longitude],
            [disaster.latitude, disaster.longitude]
          ) / 1000.0;
          
          const routeDetails = getSimulatedRouteSteps(resource, disaster, distance);
          
          const polyline = L.polyline(
            [[resource.latitude, resource.longitude], [disaster.latitude, disaster.longitude]],
            {
              color: '#00E5FF',
              weight: 3,
              dashArray: '8, 8',
              opacity: 0.85,
              className: 'animated-route-line'
            }
          );
          
          polyline.on('click', (e: any) => {
            L.DomEvent.stopPropagation(e);
            setSelectedEntity({
              type: 'route',
              data: {
                ...alloc,
                resourceName: resource.resource_name,
                resourceType: resource.resource_type,
                disasterTitle: disaster.title,
                distanceKm: distance,
                routeSteps: routeDetails
              }
            });
          });
          
          polyline.addTo(markerLayerGroup);
        }
      });
    }
  }, [showDisasters, showHospitals, showShelters, showResources, showRoutes, filteredDisasters, hospitals, shelters, resources, allocations]);

  // Fit bounds dynamically on initial data load
  useEffect(() => {
    const L = (window as any).L;
    if (!L || !mapInstanceRef.current) return;

    const points: Array<[number, number]> = [];
    if (showDisasters) filteredDisasters.forEach(d => points.push([d.latitude, d.longitude]));
    if (showHospitals) hospitals.forEach(h => points.push([h.latitude, h.longitude]));
    if (showShelters) shelters.forEach(s => points.push([s.latitude, s.longitude]));
    if (showResources) resources.forEach(r => { if (r.latitude && r.longitude) points.push([r.latitude, r.longitude]); });

    if (points.length > 0) {
      mapInstanceRef.current.fitBounds(points, { padding: [50, 50], maxZoom: 8 });
    }
  }, [disasters.length, hospitals.length, shelters.length, resources.length]);

  return (
    <PageContainer>
      <SectionHeader 
        title="Tactical Incident Map" 
        description="Geospatial overlay of live disasters, hospitals, shelters, and resource allocations."
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[calc(100vh-210px)] min-h-[550px]">
        
        {/* Map Interface Area */}
        <div className="lg:col-span-3 glass-panel border border-gray-800 rounded-xl relative overflow-hidden flex flex-col bg-adcc-secondary/40">
          
          {/* Map Top Bar (Filters & Layers) */}
          <div className="p-3 border-b border-gray-800 bg-adcc-secondary flex flex-wrap items-center justify-between gap-3 z-[1001]">
            <div className="flex items-center gap-2 text-xs font-mono">
              {disasters.some(d => d.source === 'DEMO') && (
                <div className="flex items-center gap-1.5 px-2 py-0.5 bg-amber-500/10 border border-amber-500/30 rounded text-amber-500 font-mono text-[10px] font-bold tracking-wider mr-2">
                  <span className="flex h-1.5 w-1.5 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500"></span>
                  </span>
                  DEMO MODE ACTIVE
                </div>
              )}
              <Filter size={14} className="text-adcc-accent" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="bg-adcc-bg border border-gray-850 text-adcc-textPrimary text-xs rounded px-2.5 py-1 font-mono outline-none focus:border-adcc-accent"
              >
                <option value="all">ALL HAZARDS</option>
                <option value="cyclone">CYCLONES</option>
                <option value="wildfire">WILDFIRES</option>
                <option value="flood">FLOODS</option>
                <option value="earthquake">EARTHQUAKES</option>
              </select>

              <select
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value)}
                className="bg-adcc-bg border border-gray-850 text-adcc-textPrimary text-xs rounded px-2.5 py-1 font-mono outline-none focus:border-adcc-accent"
              >
                <option value="all">ALL SEVERITY</option>
                <option value="critical">CRITICAL</option>
                <option value="high">HIGH</option>
                <option value="medium">MEDIUM</option>
                <option value="low">LOW</option>
              </select>

              <button 
                disabled={syncMutation.isPending}
                onClick={() => syncMutation.mutate()}
                className="flex items-center gap-1.5 px-2.5 py-1 bg-adcc-accent/10 border border-adcc-accent/25 hover:bg-adcc-accent hover:text-adcc-bg text-[10px] font-mono font-bold uppercase tracking-wider rounded transition-all duration-200 ml-2 disabled:opacity-50"
              >
                <RefreshCw size={11} className={syncMutation.isPending ? 'animate-spin' : ''} />
                {syncMutation.isPending ? 'Syncing...' : 'Sync Live'}
              </button>
            </div>

            {/* Layer Toggles */}
            <div className="flex flex-wrap gap-3 text-[10px] font-mono select-none">
              <label className="flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={showDisasters} onChange={() => setShowDisasters(!showDisasters)} className="rounded text-adcc-accent bg-adcc-bg border-gray-850" />
                <span className="text-adcc-danger">HAZARDS</span>
              </label>
              <label className="flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={showHospitals} onChange={() => setShowHospitals(!showHospitals)} className="rounded text-adcc-accent bg-adcc-bg border-gray-850" />
                <span className="text-[#00E5FF]">HOSPITALS</span>
              </label>
              <label className="flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={showShelters} onChange={() => setShowShelters(!showShelters)} className="rounded text-adcc-accent bg-adcc-bg border-gray-850" />
                <span className="text-purple-400">SHELTERS</span>
              </label>
              <label className="flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={showResources} onChange={() => setShowResources(!showResources)} className="rounded text-adcc-accent bg-adcc-bg border-gray-850" />
                <span className="text-green-400">RESOURCES</span>
              </label>
              <label className="flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={showRoutes} onChange={() => setShowRoutes(!showRoutes)} className="rounded text-adcc-accent bg-adcc-bg border-gray-850" />
                <span className="text-adcc-accent">ROUTES</span>
              </label>
            </div>
          </div>

          {/* Interactive Map Visual */}
          <div className="flex-1 relative bg-[#060A13] overflow-hidden select-none">
            {/* Leaflet Map Div container */}
            <div ref={mapContainerRef} className="absolute inset-0 z-0 w-full h-full" />

            {/* Grid Overlay on top of background map slightly */}
            <div className="absolute inset-0 grid-bg opacity-15 pointer-events-none z-10" />

            {/* Tactical Compass Overlay */}
            <div className="absolute bottom-6 right-6 flex flex-col items-center gap-1 bg-adcc-bg/85 border border-gray-800/80 p-2.5 rounded-lg z-[1000] pointer-events-none font-mono">
              <Compass className="text-adcc-accent animate-[spin_30s_linear_infinite]" size={24} />
              <span className="text-[8px] font-mono text-adcc-textMuted uppercase tracking-widest">TACTICAL GRID</span>
            </div>

            {/* Top-Left Telemetry Coordinates */}
            <div className="absolute top-4 left-4 bg-adcc-bg/85 border border-gray-800/80 p-3 rounded-lg z-[1000] pointer-events-none font-mono text-[9px] text-adcc-textMuted flex flex-col gap-0.5">
              <span className="text-adcc-accent font-bold uppercase tracking-wider">MAP VIEW TELEMETRY</span>
              <span>BOUNDS: [{bounds.minLat.toFixed(2)}N, {bounds.minLng.toFixed(2)}E] TO [{bounds.maxLat.toFixed(2)}N, {bounds.maxLng.toFixed(2)}E]</span>
              <span>Ingested: {disasters.length} records</span>
            </div>
          </div>
        </div>

        {/* Selected Entity Details Panel */}
        <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4 bg-adcc-secondary/20">
          <div className="border-b border-gray-800 pb-3">
            <h3 className="font-bold text-sm tracking-wider font-mono uppercase text-adcc-textPrimary flex items-center gap-1.5">
              <MapIcon size={15} className="text-adcc-accent" />
              GIS Tactical Layer
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto pr-1">
            <AnimatePresence mode="wait">
              {selectedEntity ? (
                <motion.div
                  key={selectedEntity.data.id}
                  initial={{ opacity: 0, x: 15 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -15 }}
                  transition={{ duration: 0.2 }}
                  className="flex flex-col gap-4 font-mono text-xs"
                >
                  {/* Category Badge */}
                  <span className={`px-2 py-0.5 self-start text-[9px] uppercase font-bold border rounded tracking-wider ${
                    selectedEntity.type === 'disaster' ? getSeverityBorderColor((selectedEntity.data as BackendDisaster).severity) :
                    selectedEntity.type === 'hospital' ? 'border-[#00E5FF] text-[#00E5FF]' :
                    selectedEntity.type === 'shelter' ? 'border-purple-500 text-purple-400' :
                    'border-green-500 text-green-400'
                  }`}>
                    {selectedEntity.type.toUpperCase()}
                  </span>

                  {/* Title / Name */}
                  <h4 className="text-sm font-bold text-adcc-textPrimary flex items-center gap-1.5">
                    {selectedEntity.type === 'disaster' && getDisasterIcon((selectedEntity.data as BackendDisaster).disaster_type)}
                    {selectedEntity.type === 'hospital' && <HeartPulse size={15} className="text-[#00E5FF]" />}
                    {selectedEntity.type === 'shelter' && <Home size={15} className="text-purple-400" />}
                    {selectedEntity.type === 'resource' && <Boxes size={15} className="text-green-400" />}
                    {selectedEntity.type === 'disaster' ? (selectedEntity.data as BackendDisaster).title :
                     selectedEntity.type === 'hospital' ? (selectedEntity.data as BackendHospital).name :
                     selectedEntity.type === 'shelter' ? (selectedEntity.data as BackendShelter).name :
                     (selectedEntity.data as BackendResource).resource_name}
                  </h4>

                  {/* Coordinates Info */}
                  <div className="grid grid-cols-2 gap-2 bg-adcc-secondary border border-gray-850 p-2.5 rounded-lg text-[10px]">
                    <div className="flex flex-col">
                      <span className="text-adcc-textMuted uppercase text-[8px]">LATITUDE</span>
                      <span className="text-adcc-textPrimary font-semibold">{selectedEntity.data.latitude?.toFixed(4) ?? '--'}° N</span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-adcc-textMuted uppercase text-[8px]">LONGITUDE</span>
                      <span className="text-adcc-textPrimary font-semibold">{selectedEntity.data.longitude?.toFixed(4) ?? '--'}° E</span>
                    </div>
                  </div>

                  {/* Detailed Specs based on category */}
                  {selectedEntity.type === 'disaster' && (
                    <div className="space-y-2.5 mt-2">
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Hazard Type:</span>
                        <span className="font-semibold text-adcc-textPrimary">{(selectedEntity.data as BackendDisaster).disaster_type}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Severity:</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${getSeverityBadgeColor((selectedEntity.data as BackendDisaster).severity)}`}>
                          {(selectedEntity.data as BackendDisaster).severity}
                        </span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Affected Citizens:</span>
                        <span className="font-bold text-adcc-textPrimary">{(selectedEntity.data as BackendDisaster).affected_population?.toLocaleString() ?? 'Unknown'}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Confidence Rating:</span>
                        <span className="text-adcc-accent">{(selectedEntity.data as BackendDisaster).confidence_score ? `${Math.round((selectedEntity.data as BackendDisaster).confidence_score! * 100)}%` : '--'}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Verification Status:</span>
                        <span className="text-adcc-success">{(selectedEntity.data as BackendDisaster).verification_status}</span>
                      </div>
                    </div>
                  )}

                  {selectedEntity.type === 'hospital' && (
                    <div className="space-y-2.5 mt-2">
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">City Location:</span>
                        <span className="font-semibold text-adcc-textPrimary">{(selectedEntity.data as BackendHospital).city}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Available Beds:</span>
                        <span className="font-bold text-adcc-success">{(selectedEntity.data as BackendHospital).available_beds} slots</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Total Bed Capacity:</span>
                        <span className="text-adcc-textPrimary">{(selectedEntity.data as BackendHospital).total_beds} slots</span>
                      </div>
                    </div>
                  )}

                  {selectedEntity.type === 'shelter' && (
                    <div className="space-y-2.5 mt-2">
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">City Location:</span>
                        <span className="font-semibold text-adcc-textPrimary">{(selectedEntity.data as BackendShelter).city}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Occupied Slots:</span>
                        <span className="font-bold text-adcc-warning">{(selectedEntity.data as BackendShelter).occupied} citizens</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Vacant Capacity:</span>
                        <span className="font-bold text-adcc-success">
                          {Math.max(0, (selectedEntity.data as BackendShelter).capacity - (selectedEntity.data as BackendShelter).occupied)} slots
                        </span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Total Volume:</span>
                        <span className="text-adcc-textPrimary">{(selectedEntity.data as BackendShelter).capacity} slots</span>
                      </div>
                    </div>
                  )}

                  {selectedEntity.type === 'resource' && (
                    <div className="space-y-2.5 mt-2">
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Equipment Type:</span>
                        <span className="font-semibold text-adcc-textPrimary">{(selectedEntity.data as BackendResource).resource_type.replace('_', ' ')}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Current Status:</span>
                        <span className={`font-bold ${
                          (selectedEntity.data as BackendResource).status === 'Available' ? 'text-adcc-success' : 'text-adcc-warning'
                        }`}>
                          {(selectedEntity.data as BackendResource).status}
                        </span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Reserves Quantity:</span>
                        <span className="font-bold text-adcc-textPrimary">{(selectedEntity.data as BackendResource).quantity} units</span>
                      </div>
                    </div>
                  )}

                  {selectedEntity.type === 'route' && (
                    <div className="space-y-3 mt-2">
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Dispatched Asset:</span>
                        <span className="font-bold text-adcc-textPrimary">{(selectedEntity.data as any).resourceName}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Disaster Incident:</span>
                        <span className="font-bold text-adcc-textPrimary">{(selectedEntity.data as any).disasterTitle}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Direct Distance:</span>
                        <span className="font-bold text-adcc-accent">{(selectedEntity.data as any).distanceKm.toFixed(1)} km</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Transit Corridor:</span>
                        <span className="font-bold text-adcc-warning">{(selectedEntity.data as any).routeSteps.routeName}</span>
                      </div>
                      <div className="flex justify-between border-b border-gray-850 pb-1.5">
                        <span className="text-adcc-textMuted">Status:</span>
                        <span className="font-bold text-adcc-success uppercase">{(selectedEntity.data as any).status}</span>
                      </div>
                      
                      <div className="flex flex-col gap-1 mt-2">
                        <span className="text-adcc-textMuted uppercase text-[8px] font-bold tracking-wider">Tactical Routing Waypoints:</span>
                        <div className="p-2.5 bg-adcc-secondary/40 border border-gray-850 rounded-lg flex flex-col gap-2 text-[10px] leading-relaxed font-sans">
                          {(selectedEntity.data as any).routeSteps.steps.map((step: string, idx: number) => (
                            <div key={idx} className="flex gap-1.5">
                              <span className="text-adcc-accent font-bold font-mono">{idx + 1}.</span>
                              <span className="text-adcc-textPrimary">{step}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      <div className="flex flex-col gap-1 mt-1">
                        <span className="text-adcc-textMuted uppercase text-[8px] font-bold tracking-wider">Deployment Dispatch Logic:</span>
                        <div className="p-3 bg-adcc-accent/5 border border-adcc-accent/25 rounded-lg text-adcc-textPrimary italic text-[11px] leading-relaxed">
                          "{(selectedEntity.data as any).allocation_reason || 'Manual override deployment registered.'}"
                        </div>
                      </div>
                    </div>
                  )}

                </motion.div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center gap-2 border border-dashed border-gray-800 rounded-lg text-xs font-mono text-adcc-textMuted p-4 text-center animate-pulse">
                  <MapPin size={24} className="text-adcc-accent" />
                  <span>SELECT PIN ON TACTICAL GRID FOR SATELLITE DIAGNOSTICS OVERLAYS</span>
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>

      </div>
    </PageContainer>
  );
};
export default DisasterMap;
