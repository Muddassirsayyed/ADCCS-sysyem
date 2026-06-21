import React from 'react';

interface SectionHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({ title, description, actions }) => {
  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-adcc-accentBorder/20 pb-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-adcc-textPrimary flex items-center gap-2">
          <span className="w-1 h-6 bg-adcc-accent rounded-full inline-block"></span>
          {title}
        </h1>
        {description && (
          <p className="text-sm text-adcc-textMuted mt-1 font-sans">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
    </div>
  );
};
export default SectionHeader;
