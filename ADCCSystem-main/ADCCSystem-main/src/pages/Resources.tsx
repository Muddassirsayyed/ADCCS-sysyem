import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService, { BackendResource, BackendDisaster, BackendAllocation } from '../services/api';
import PageContainer from '../components/PageContainer';
import SectionHeader from '../components/SectionHeader';
import { 
  Boxes, 
  Truck, 
  Plus, 
  Minus, 
  ShieldAlert, 
  Navigation,
  Warehouse,
  HeartPulse,
  Ship,
  Ambulance,
  CheckCircle,
  FileSpreadsheet,
  Cpu
} from 'lucide-react';

export const Resources: React.FC = () => {
  const queryClient = useQueryClient();
  
  // 1. Fetch live data
  const { data: resources = [], isLoading: resourcesLoading } = useQuery<BackendResource[]>({
    queryKey: ['resources'],
    queryFn: apiService.getResources
  });

  const { data: disasters = [] } = useQuery<BackendDisaster[]>({
    queryKey: ['disasters'],
    queryFn: apiService.getDisasters
  });

  const { data: allocations = [] } = useQuery<BackendAllocation[]>({
    queryKey: ['allocations'],
    queryFn: apiService.getAllocations
  });

  // 2. Local State for Dispatch
  const [selectedDisasterId, setSelectedDisasterId] = useState<string>('');
  const [selectedResourceId, setSelectedResourceId] = useState<string>('');
  const [dispatchQty, setDispatchQty] = useState<number>(1);
  const [dispatchReason, setDispatchReason] = useState<string>('');
  const [dispatchError, setDispatchError] = useState<string | null>(null);
  const [dispatchSuccess, setDispatchSuccess] = useState<boolean>(false);
  const [isAiLoading, setIsAiLoading] = useState<boolean>(false);

  const handleAiRecommend = async () => {
    if (!selectedDisasterId) {
      setDispatchError('Please select a target disaster incident first.');
      return;
    }
    setIsAiLoading(true);
    setDispatchError(null);
    try {
      const rec = await apiService.recommendAllocation(selectedDisasterId);
      setSelectedResourceId(rec.resource_id);
      setDispatchQty(rec.quantity);
      setDispatchReason(rec.recommendation_reason);
      setDispatchSuccess(false);
    } catch (err: any) {
      setDispatchError(err.response?.data?.detail || 'Failed to fetch AI recommendation.');
    } finally {
      setIsAiLoading(false);
    }
  };

  const handleAiAutoDispatch = async () => {
    if (!selectedDisasterId) {
      setDispatchError('Please select a target disaster incident first.');
      return;
    }
    setIsAiLoading(true);
    setDispatchError(null);
    try {
      const rec = await apiService.recommendAllocation(selectedDisasterId);
      dispatchMutation.mutate({
        disaster_id: selectedDisasterId,
        resource_id: rec.resource_id,
        quantity: rec.quantity,
        allocation_reason: rec.recommendation_reason
      });
    } catch (err: any) {
      setDispatchError(err.response?.data?.detail || 'Failed to auto-dispatch.');
    } finally {
      setIsAiLoading(false);
    }
  };

  // 3. Dispatch Mutation (persists allocation to DB)
  const dispatchMutation = useMutation({
    mutationFn: async (payload: { disaster_id: string; resource_id: string; quantity: number; allocation_reason: string }) => {
      return apiService.createAllocation({
        disaster_id: payload.disaster_id,
        resource_id: payload.resource_id,
        quantity: payload.quantity,
        allocation_reason: payload.allocation_reason,
        status: 'Active'
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resources'] });
      queryClient.invalidateQueries({ queryKey: ['allocations'] });
      setDispatchSuccess(true);
      setDispatchError(null);
      setDispatchQty(1);
      setDispatchReason('');
      setTimeout(() => setDispatchSuccess(false), 4000);
    },
    onError: (err: any) => {
      setDispatchError(err.response?.data?.detail || 'Database dispatch failed.');
    }
  });

  const handleDispatchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDisasterId || !selectedResourceId || dispatchQty <= 0) {
      setDispatchError('Specify disaster, resource, and positive quantity.');
      return;
    }
    
    // Check stock
    const res = resources.find(r => r.id === selectedResourceId);
    if (!res || res.quantity < dispatchQty) {
      setDispatchError('Insufficient resource quantity in stock.');
      return;
    }

    dispatchMutation.mutate({
      disaster_id: selectedDisasterId,
      resource_id: selectedResourceId,
      quantity: dispatchQty,
      allocation_reason: dispatchReason || 'Command Center Manual Dispatch'
    });
  };

  // 4. Summaries and KPI Card Data
  const totalFleetUnits = resources.reduce((sum, r) => sum + r.quantity, 0);
  const availableUnits = resources.filter(r => r.status === 'Available').reduce((sum, r) => sum + r.quantity, 0);
  const busyUnits = resources.filter(r => r.status === 'Busy').reduce((sum, r) => sum + r.quantity, 0);
  const maintUnits = resources.filter(r => r.status === 'Maintenance').reduce((sum, r) => sum + r.quantity, 0);

  const getResourceIcon = (type: string, size = 18) => {
    switch (type.toLowerCase()) {
      case 'boat': return <Ship className="text-[#38BDF8]" size={size} />;
      case 'ambulance': return <Ambulance className="text-adcc-warning" size={size} />;
      case 'medical_team': return <HeartPulse className="text-adcc-accent" size={size} />;
      case 'ndrf_unit': return <Warehouse className="text-adcc-success" size={size} />;
      default: return <Boxes className="text-purple-400" size={size} />;
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'available': return 'text-adcc-success border-adcc-success/35 bg-adcc-success/5';
      case 'busy': return 'text-adcc-warning border-adcc-warning/30 bg-adcc-warning/5';
      default: return 'text-adcc-danger border-adcc-danger/30 bg-adcc-danger/5 animate-pulse';
    }
  };

  // Find where a resource is allocated
  const getAllocationLabel = (resourceId: string) => {
    const activeAlloc = allocations.find(a => a.resource_id === resourceId && a.status === 'Active');
    if (!activeAlloc) return 'Unallocated (Depot Reserves)';
    
    const disaster = disasters.find(d => d.id === activeAlloc.disaster_id);
    return disaster ? `Deployed: ${disaster.title}` : 'Deployed to Active Incident';
  };

  return (
    <PageContainer>
      <SectionHeader 
        title="Resource Ingestion & Deployment" 
        description="Monitor responder reserves, deploy manual overrides, and view log sheets."
      />

      {/* KPI Cards (Summary Cards) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6 font-mono text-xs">
        <div className="glass-panel border border-gray-800 p-4 rounded-xl flex flex-col gap-1">
          <span className="text-adcc-textMuted uppercase">Total Responders Fleet</span>
          <span className="text-2xl font-bold text-adcc-textPrimary">{totalFleetUnits} <span className="text-xs font-normal text-adcc-textMuted">units</span></span>
        </div>
        <div className="glass-panel border border-gray-800 p-4 rounded-xl flex flex-col gap-1">
          <span className="text-[#10B981] uppercase font-bold">Ready / Available</span>
          <span className="text-2xl font-bold text-[#10B981]">{availableUnits} <span className="text-xs font-normal text-adcc-textMuted">units</span></span>
        </div>
        <div className="glass-panel border border-gray-800 p-4 rounded-xl flex flex-col gap-1">
          <span className="text-adcc-warning uppercase font-bold">Deployed / Busy</span>
          <span className="text-2xl font-bold text-adcc-warning">{busyUnits} <span className="text-xs font-normal text-adcc-textMuted">units</span></span>
        </div>
        <div className="glass-panel border border-gray-800 p-4 rounded-xl flex flex-col gap-1">
          <span className="text-adcc-danger uppercase font-bold">In Maintenance</span>
          <span className="text-2xl font-bold text-adcc-danger">{maintUnits} <span className="text-xs font-normal text-adcc-textMuted">units</span></span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Resource Table Registry Sheets (2 Cols) */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          
          <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-gray-850 pb-3">
              <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
                <FileSpreadsheet size={14} className="text-adcc-accent" />
                Live Command Inventory Registry
              </h3>
              <span className="text-[9px] font-mono text-adcc-accent uppercase">Live Ingest ({resources.length} nodes)</span>
            </div>

            {/* Scrollable list of active resources */}
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-[11px] text-adcc-textMuted border-collapse">
                <thead>
                  <tr className="border-b border-gray-850 text-adcc-textPrimary bg-adcc-secondary/35 text-[9px] uppercase tracking-wider">
                    <th className="py-2.5 px-3">Resource Name</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Location</th>
                    <th className="py-2.5 px-3">Qty</th>
                    <th className="py-2.5 px-3">Deployment Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-900">
                  {resourcesLoading ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-xs text-adcc-textMuted animate-pulse">
                        TUNING LOGISTICS TELEMETRY LINKS...
                      </td>
                    </tr>
                  ) : resources.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-xs text-adcc-textMuted">
                        NO RESOURCE REGISTRIES DETECTED
                      </td>
                    </tr>
                  ) : (
                    resources.map((res) => (
                      <tr key={res.id} className="hover:bg-adcc-secondary/15 transition-colors">
                        <td className="py-3 px-3 font-semibold text-adcc-textPrimary flex items-center gap-1.5">
                          {getResourceIcon(res.resource_type, 13)}
                          {res.resource_name}
                        </td>
                        <td className="py-3 px-3 text-[10px] uppercase">{res.resource_type.replace('_', ' ')}</td>
                        <td className="py-3 px-3">
                          <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase border ${getStatusBadgeClass(res.status)}`}>
                            {res.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-[10px]">
                          {res.latitude ? `(${res.latitude.toFixed(3)}, ${res.longitude?.toFixed(3)})` : 'CENTRAL DEPOT'}
                        </td>
                        <td className="py-3 px-3 text-adcc-accent font-bold">{res.quantity}</td>
                        <td className="py-3 px-3 text-[10.5px] font-sans truncate max-w-[200px]" title={getAllocationLabel(res.id)}>
                          {getAllocationLabel(res.id)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Dispatch Console (1 Col) */}
        <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-4 bg-adcc-secondary/20 h-fit">
          <div className="border-b border-gray-850 pb-3">
            <h3 className="font-bold text-xs font-mono uppercase tracking-wider text-adcc-textPrimary flex items-center gap-1.5">
              <Truck size={14} className="text-adcc-accent animate-pulse" />
              Manual Dispatch Controller
            </h3>
          </div>

          <form onSubmit={handleDispatchSubmit} className="flex flex-col gap-4">
            {/* Disaster Target */}
            <div className="flex flex-col gap-1.5 font-mono text-[10px]">
              <label className="text-adcc-textMuted uppercase font-semibold">Target Disaster Incident</label>
              <select
                value={selectedDisasterId}
                onChange={(e) => setSelectedDisasterId(e.target.value)}
                className="w-full bg-adcc-bg border border-gray-850 text-adcc-textPrimary text-xs rounded-lg p-2.5 font-mono outline-none focus:border-adcc-accent"
              >
                <option value="">-- SELECT TACTICAL TARGET --</option>
                {disasters.filter(d => d.status === 'Active').map(d => (
                  <option key={d.id} value={d.id}>{d.title.toUpperCase()} ({d.severity})</option>
                ))}
              </select>
            </div>

            {/* AI Assistant Quick Actions */}
            {selectedDisasterId && (
              <div className="p-3.5 bg-adcc-accent/5 border border-adcc-accent/25 rounded-lg flex flex-col gap-2 font-mono text-[9px]">
                <span className="text-adcc-accent uppercase font-bold flex items-center gap-1">
                  <Cpu size={12} className="animate-pulse" /> Autonomous Dispatch AI
                </span>
                <span className="text-adcc-textMuted leading-relaxed">Let the AI autonomous system evaluate closest reserves, path routing, and deployment reasons.</span>
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <button
                    type="button"
                    disabled={isAiLoading}
                    onClick={handleAiRecommend}
                    className="py-2 px-2 bg-adcc-bg border border-adcc-accent/30 hover:border-adcc-accent hover:text-adcc-accent text-adcc-textMuted rounded font-bold uppercase transition-colors cursor-pointer text-center"
                  >
                    {isAiLoading ? 'Evaluating...' : '🤖 Suggest'}
                  </button>
                  <button
                    type="button"
                    disabled={isAiLoading || dispatchMutation.isPending}
                    onClick={handleAiAutoDispatch}
                    className="py-2 px-2 bg-adcc-accent/20 border border-adcc-accent/40 hover:bg-adcc-accent hover:text-adcc-bg text-adcc-textPrimary rounded font-bold uppercase transition-colors cursor-pointer text-center"
                  >
                    {dispatchMutation.isPending ? 'Deploying...' : '🤖 Dispatch'}
                  </button>
                </div>
              </div>
            )}

            {/* Resource Selector */}
            <div className="flex flex-col gap-1.5 font-mono text-[10px]">
              <label className="text-adcc-textMuted uppercase font-semibold">Select Available Responders</label>
              <select
                value={selectedResourceId}
                onChange={(e) => setSelectedResourceId(e.target.value)}
                className="w-full bg-adcc-bg border border-gray-850 text-adcc-textPrimary text-xs rounded-lg p-2.5 font-mono outline-none focus:border-adcc-accent"
              >
                <option value="">-- SELECT AVAILABLE EQUIPMENT --</option>
                {resources.filter(r => r.status === 'Available').map(r => (
                  <option key={r.id} value={r.id}>
                    {r.resource_name.toUpperCase()} (Qty: {r.quantity} | {r.resource_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Quantity */}
            <div className="flex flex-col gap-1.5 font-mono text-[10px]">
              <label className="text-adcc-textMuted uppercase font-semibold">Deploy Quantity</label>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setDispatchQty(prev => Math.max(1, prev - 1))}
                  className="p-2.5 border border-gray-800 bg-adcc-bg rounded hover:bg-gray-800 text-adcc-accent transition-colors"
                >
                  <Minus size={12} />
                </button>
                <input
                  type="number"
                  value={dispatchQty}
                  onChange={(e) => setDispatchQty(Math.max(1, parseInt(e.target.value) || 1))}
                  className="flex-1 text-center bg-adcc-bg border border-gray-850 text-adcc-textPrimary font-mono text-sm py-2 rounded-lg outline-none focus:border-adcc-accent"
                />
                <button
                  type="button"
                  onClick={() => setDispatchQty(prev => prev + 1)}
                  className="p-2.5 border border-gray-800 bg-adcc-bg rounded hover:bg-gray-800 text-adcc-accent transition-colors"
                >
                  <Plus size={12} />
                </button>
              </div>
            </div>

            {/* Reason */}
            <div className="flex flex-col gap-1.5 font-mono text-[10px]">
              <label className="text-adcc-textMuted uppercase font-semibold">Deployment Reason / Notes</label>
              <input
                type="text"
                value={dispatchReason}
                onChange={(e) => setDispatchReason(e.target.value)}
                placeholder="Tactical reinforcement backup..."
                className="bg-adcc-bg border border-gray-850 text-adcc-textPrimary text-xs rounded-lg px-3 py-2.5 outline-none focus:border-adcc-accent font-sans"
              />
            </div>

            {/* Response Alerts */}
            {dispatchError && (
              <div className="flex items-start gap-2 bg-adcc-danger/10 border border-adcc-danger/25 p-2.5 rounded text-[9px] text-adcc-danger font-mono uppercase">
                <ShieldAlert size={14} className="shrink-0" />
                <span>{dispatchError}</span>
              </div>
            )}

            {dispatchSuccess && (
              <div className="flex items-start gap-2 bg-adcc-success/10 border border-adcc-success/25 p-2.5 rounded text-[9px] text-adcc-success font-mono uppercase">
                <CheckCircle size={14} className="shrink-0" />
                <span>RELIEF FORCE DISPATCHED SUCCESSFULLY. REGISTERED IN COMMAND LEDGER.</span>
              </div>
            )}

            <button
              type="submit"
              disabled={dispatchMutation.isPending}
              className="w-full flex items-center justify-center gap-1.5 py-3 mt-2 bg-adcc-accent/15 border border-adcc-accent/30 hover:bg-adcc-accent hover:text-adcc-bg text-xs font-mono font-bold uppercase tracking-wider rounded-lg transition-all duration-200 disabled:opacity-50"
            >
              <Navigation size={13} /> Dispatch Tactical Override
            </button>
          </form>
        </div>

      </div>
    </PageContainer>
  );
};
export default Resources;
