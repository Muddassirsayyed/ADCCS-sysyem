import React from 'react';
import { motion } from 'framer-motion';

interface PageContainerProps {
  children: React.ReactNode;
}

export const PageContainer: React.FC<PageContainerProps> = ({ children }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      transition={{ duration: 0.35, ease: 'easeOut' as const }}
      className="min-h-[calc(100vh-64px)] w-full p-4 lg:p-6 grid-bg relative flex flex-col gap-6"
    >
      {/* Tactical scanner lines for military-grade command aesthetic */}
      <div className="absolute inset-0 scanner-overlay opacity-30 pointer-events-none" />
      <div className="relative z-10 flex flex-col gap-6 w-full max-w-[1600px] mx-auto">
        {children}
      </div>
    </motion.div>
  );
};
export default PageContainer;
