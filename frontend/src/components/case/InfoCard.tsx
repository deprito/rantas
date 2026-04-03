import { ReactNode } from 'react';

interface InfoCardProps {
  icon: ReactNode;
  label: string;
  value: string | number | undefined;
}

export function InfoCard({ icon, label, value }: InfoCardProps) {
  return (
    <div className="bg-muted/50 p-3 rounded-lg space-y-1">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <p className="text-sm font-medium truncate" title={String(value ?? 'N/A')}>
        {value ?? <span className="text-muted-foreground">N/A</span>}
      </p>
    </div>
  );
}
