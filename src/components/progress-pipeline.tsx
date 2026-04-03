import { CaseStatus } from '@/types/case';

interface ProgressPipelineProps {
  status: CaseStatus;
}

const stages = [
  { percent: 20, label: 'Analyzing', status: 'ANALYZING' as CaseStatus },
  { percent: 30, label: 'Ready to Report', status: 'READY_TO_REPORT' as CaseStatus },
  { percent: 40, label: 'Sending Report', status: 'REPORTING' as CaseStatus },
  { percent: 50, label: 'Report Sent', status: 'REPORTED' as CaseStatus },
  { percent: 80, label: 'Monitoring', status: 'MONITORING' as CaseStatus },
  { percent: 100, label: 'Resolved', status: 'RESOLVED' as CaseStatus },
];

const statusOrder: Record<CaseStatus, number> = {
  ANALYZING: 1,
  READY_TO_REPORT: 2,
  REPORTING: 3,
  REPORTED: 4,
  MONITORING: 5,
  RESOLVED: 6,
  FAILED: 0,
};

export function ProgressPipeline({ status }: ProgressPipelineProps) {
  const currentStage = statusOrder[status];
  const totalStages = stages.length;
  const progressPercent = status === 'FAILED' ? 0 : ((currentStage - 1) / totalStages) * 100;

  return (
    <div className="w-full">
      <div className="flex justify-between mb-2">
        {stages.map((stage) => {
          const isCompleted = statusOrder[stage.status] <= currentStage;
          const isCurrent = stage.status === status;

          return (
            <div
              key={stage.status}
              className={`flex flex-col items-center ${
                isCompleted ? 'text-foreground' : 'text-muted-foreground'
              }`}
            >
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-colors ${
                  isCurrent
                    ? 'border-primary bg-primary text-primary-foreground'
                    : isCompleted
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-muted'
                }`}
              >
                {stage.percent}%
              </div>
              <span className="text-xs mt-1 hidden sm:block max-w-[80px] text-center">
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="relative h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="absolute top-0 left-0 h-full bg-primary transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="mt-2 text-center">
        <span className="text-sm font-medium">Current Stage: </span>
        <span className="text-sm text-primary">
          {stages.find((s) => s.status === status)?.label}
        </span>
      </div>
    </div>
  );
}
