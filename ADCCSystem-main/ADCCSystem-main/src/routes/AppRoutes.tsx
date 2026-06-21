import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import Dashboard from '../pages/Dashboard';
import DisasterMap from '../pages/DisasterMap';
import Resources from '../pages/Resources';
import Agents from '../pages/Agents';
import Simulation from '../pages/Simulation';
import AICommandCenter from '../pages/AICommandCenter';
import Analytics from '../pages/Analytics';
import Settings from '../pages/Settings';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<DashboardLayout />}>
        {/* Child Views */}
        <Route index element={<Dashboard />} />
        <Route path="map" element={<DisasterMap />} />
        <Route path="resources" element={<Resources />} />
        <Route path="agents" element={<Agents />} />
        <Route path="simulation" element={<Simulation />} />
        <Route path="ai-command" element={<AICommandCenter />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="settings" element={<Settings />} />
        
        {/* Redirect unknown routes */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};
export default AppRoutes;
