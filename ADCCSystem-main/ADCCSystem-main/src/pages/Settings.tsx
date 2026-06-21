import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import SectionHeader from '../components/SectionHeader';
import { 
  ShieldCheck,
  Save,
  RefreshCw,
  BellRing,
  Globe,
  Brain
} from 'lucide-react';

export const Settings: React.FC = () => {
  // Local Form state
  const [pollingRate, setPollingRate] = useState<number>(30);
  const [simSpeed, setSimSpeed] = useState<number>(1);
  const [enableGDS, setEnableGDS] = useState<boolean>(true);
  const [enableSMS, setEnableSMS] = useState<boolean>(false);
  const [enableEmail, setEnableEmail] = useState<boolean>(true);
  const [aiModel, setAiModel] = useState<string>('gemini-3.5-pro');
  const [apiKey, setApiKey] = useState<string>('•••••••••••••••••••••••••••••');
  
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveStatus('syncing');
    
    setTimeout(() => {
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    }, 1500);
  };

  return (
    <PageContainer>
      <SectionHeader 
        title="Command Settings" 
        description="Configure GIS sensor feeds, AI cognitive models, notification integration APIs, and simulator speeds."
      />

      <form onSubmit={handleSave} className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Left Side: Sensor & Model config (2 Cols) */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          
          {/* GIS sensor settings */}
          <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-5">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <h3 className="font-bold text-sm tracking-wider font-mono uppercase text-adcc-textPrimary flex items-center gap-2">
                <Globe size={16} className="text-adcc-accent" />
                GIS Sensor Stream settings
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 font-mono text-xs">
              
              {/* Polling rate slider */}
              <div className="flex flex-col gap-2">
                <div className="flex justify-between">
                  <span className="text-adcc-textMuted uppercase">Satellite Poll Rate (sec)</span>
                  <span className="text-adcc-accent font-bold">{pollingRate}s</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="300"
                  step="5"
                  value={pollingRate}
                  onChange={(e) => setPollingRate(parseInt(e.target.value))}
                  className="w-full accent-adcc-accent cursor-pointer bg-gray-850 h-1.5 rounded-lg appearance-none"
                />
              </div>

              {/* Simulation speed slider */}
              <div className="flex flex-col gap-2">
                <div className="flex justify-between">
                  <span className="text-adcc-textMuted uppercase">Simulation speed index</span>
                  <span className="text-adcc-accent font-bold">{simSpeed}x</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="5"
                  step="0.5"
                  value={simSpeed}
                  onChange={(e) => setSimSpeed(parseFloat(e.target.value))}
                  className="w-full accent-adcc-accent cursor-pointer bg-gray-850 h-1.5 rounded-lg appearance-none"
                />
              </div>

            </div>

            <div className="flex flex-col gap-3.5 pt-3 border-t border-gray-800/40 text-xs">
              <label className="flex items-center gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={enableGDS}
                  onChange={(e) => setEnableGDS(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-800 text-adcc-accent focus:ring-0 focus:ring-offset-0 bg-adcc-bg"
                />
                <div className="flex flex-col">
                  <span className="font-semibold text-adcc-textPrimary font-sans">GDACS API Integration</span>
                  <span className="text-[10px] font-mono text-adcc-textMuted mt-0.5">Stream global alert data automatically from United Nations nodes.</span>
                </div>
              </label>
            </div>
          </div>

          {/* AI Orchestrator Settings */}
          <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-5">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <h3 className="font-bold text-sm tracking-wider font-mono uppercase text-adcc-textPrimary flex items-center gap-2">
                <Brain size={16} className="text-adcc-accent" />
                AI Cognitive Layer Parameters
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 font-mono text-xs">
              
              {/* Model select */}
              <div className="flex flex-col gap-2">
                <label className="text-[10px] text-adcc-textMuted uppercase tracking-wider">Orchestration Model</label>
                <select
                  value={aiModel}
                  onChange={(e) => setAiModel(e.target.value)}
                  className="w-full bg-adcc-bg border border-gray-800 text-adcc-textPrimary text-xs rounded-lg p-2.5 outline-none focus:border-adcc-accent font-mono"
                >
                  <option value="gemini-3.5-pro">Gemini 3.5 Pro (Recommended)</option>
                  <option value="gemini-3.5-flash">Gemini 3.5 Flash</option>
                  <option value="custom-disaster-llama">Fine-tuned DisasterLlama-70B</option>
                </select>
              </div>

              {/* API Key input */}
              <div className="flex flex-col gap-2">
                <label className="text-[10px] text-adcc-textMuted uppercase tracking-wider">API Auth Token</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full bg-adcc-bg border border-gray-800 text-adcc-textPrimary text-xs rounded-lg px-3 py-2.5 outline-none focus:border-adcc-accent font-mono"
                  placeholder="Enter API key..."
                />
              </div>

            </div>
          </div>

        </div>

        {/* Right Side: Alert notification route toggles (1 Col) */}
        <div className="flex flex-col gap-6">
          
          {/* Notification routes settings */}
          <div className="glass-panel border border-gray-800 rounded-xl p-5 flex flex-col gap-5 bg-adcc-secondary/20">
            <div className="border-b border-gray-800 pb-3">
              <h3 className="font-bold text-sm tracking-wider font-mono uppercase text-adcc-textPrimary flex items-center gap-1.5">
                <BellRing size={15} className="text-adcc-accent" />
                Notification Broadcasters
              </h3>
            </div>

            <div className="flex flex-col gap-4 text-xs font-mono">
              
              {/* Broadcast channels checkboxes */}
              <label className="flex items-start gap-3 cursor-pointer select-none border-b border-gray-850 pb-3">
                <input
                  type="checkbox"
                  checked={enableSMS}
                  onChange={(e) => setEnableSMS(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-800 text-adcc-accent focus:ring-0 focus:ring-offset-0 bg-adcc-bg mt-0.5"
                />
                <div className="flex flex-col gap-0.5 font-sans">
                  <span className="font-semibold text-adcc-textPrimary">SMS Responder Broadcasts</span>
                  <span className="text-[10px] text-adcc-textMuted font-mono">Dispatches automated cellular messages to NDRF rescue teams.</span>
                </div>
              </label>

              <label className="flex items-start gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={enableEmail}
                  onChange={(e) => setEnableEmail(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-800 text-adcc-accent focus:ring-0 focus:ring-offset-0 bg-adcc-bg mt-0.5"
                />
                <div className="flex flex-col gap-0.5 font-sans">
                  <span className="font-semibold text-adcc-textPrimary">Command Center Email Digests</span>
                  <span className="text-[10px] text-adcc-textMuted font-mono">Sends hourly status emails to government relief departments.</span>
                </div>
              </label>

            </div>

            {/* Save Buttons Panel */}
            <div className="flex flex-col gap-3 mt-4 pt-4 border-t border-gray-800">
              
              {saveStatus === 'syncing' && (
                <div className="flex items-center justify-center gap-2 p-2 bg-adcc-accent/10 border border-adcc-accent/25 text-adcc-accent text-[10px] font-mono rounded">
                  <RefreshCw size={12} className="animate-spin" />
                  <span>SYNCHRONIZING CONFIG PARAMETERS WITH CLUSTER...</span>
                </div>
              )}

              {saveStatus === 'saved' && (
                <div className="flex items-center justify-center gap-2 p-2 bg-adcc-success/15 border border-adcc-success/30 text-adcc-success text-[10px] font-mono rounded">
                  <ShieldCheck size={12} />
                  <span>SETTINGS SUCCESSFULLY SYNCHRONIZED</span>
                </div>
              )}

              <button
                type="submit"
                disabled={saveStatus === 'syncing'}
                className="w-full flex items-center justify-center gap-2 py-3 bg-adcc-accent/15 border border-adcc-accent/30 hover:bg-adcc-accent hover:text-adcc-bg text-xs font-mono font-bold uppercase tracking-wider rounded-lg transition-all duration-200"
              >
                <Save size={14} /> Synchronize Config
              </button>
            </div>
          </div>

        </div>

      </form>
    </PageContainer>
  );
};
export default Settings;
