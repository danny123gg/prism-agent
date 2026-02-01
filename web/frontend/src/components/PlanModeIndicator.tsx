/**
 * PlanModeIndicator - Plan Mode status indicator
 *
 * Shows current permission mode status
 */

interface PlanModeIndicatorProps {
  active: boolean;
  reason?: string;
  permissionMode: string;
}

export function PlanModeIndicator({ active, reason, permissionMode }: PlanModeIndicatorProps) {
  const getModeDescription = (mode: string) => {
    switch (mode) {
      case 'plan':
        return {
          label: 'Plan Mode',
          description: 'Claude creates a plan and waits for approval before execution',
          color: 'bg-purple-50 text-purple-700 border-purple-200',
          icon: '◇',
        };
      case 'acceptEdits':
        return {
          label: 'Accept Edits',
          description: 'Claude auto-executes file edits, user reviews results',
          color: 'bg-blue-50 text-blue-700 border-blue-200',
          icon: '◈',
        };
      case 'bypassPermissions':
        return {
          label: 'Bypass',
          description: 'Claude auto-executes all operations without confirmation',
          color: 'bg-amber-50 text-amber-700 border-amber-200',
          icon: '▸',
        };
      case 'default':
      default:
        return {
          label: 'Default',
          description: 'Sensitive operations require user confirmation',
          color: 'bg-stone-50 text-stone-700 border-stone-200',
          icon: '○',
        };
    }
  };

  const modeInfo = getModeDescription(permissionMode);

  return (
    <div className={`rounded-lg border p-3 ${modeInfo.color}`}>
      <div className="flex items-center gap-2">
        <span className="text-sm text-stone-400">{modeInfo.icon}</span>
        <span className="font-medium text-sm">{modeInfo.label}</span>
        {active && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500 text-white">
            Active
          </span>
        )}
      </div>
      <p className="text-xs mt-1 opacity-80">{modeInfo.description}</p>
      {reason && (
        <p className="text-xs mt-2 opacity-60">
          <strong>Reason:</strong> {reason}
        </p>
      )}

      {permissionMode === 'plan' && (
        <div className="mt-3 pt-3 border-t border-purple-100">
          <div className="text-xs space-y-1">
            <div className="font-medium">Workflow:</div>
            <ol className="list-decimal list-inside space-y-0.5 opacity-80">
              <li>Claude analyzes the task and creates a plan</li>
              <li>User reviews the plan</li>
              <li>User approves or modifies</li>
              <li>Claude executes the plan</li>
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * PermissionModeSelector - Permission mode comparison (for education)
 *
 * Shows all available permission modes and their differences
 */
export function PermissionModeSelector() {
  const modes = [
    {
      mode: 'default',
      icon: '○',
      label: 'Default',
      description: 'Requires confirmation for sensitive ops',
      features: ['File writes need approval', 'Commands need approval', 'Most secure'],
    },
    {
      mode: 'acceptEdits',
      icon: '◈',
      label: 'Accept Edits',
      description: 'Auto-executes file edits',
      features: ['File edits auto-run', 'Commands still need approval', 'Good for dev'],
    },
    {
      mode: 'plan',
      icon: '◇',
      label: 'Plan Mode',
      description: 'Plan first, then execute',
      features: ['Creates detailed plan', 'Executes after approval', 'Collaborative'],
    },
    {
      mode: 'bypassPermissions',
      icon: '▸',
      label: 'Bypass',
      description: 'Skips all permission checks',
      features: ['All ops auto-execute', 'Maximum efficiency', 'Sandbox only'],
    },
  ];

  return (
    <div className="border border-stone-200 rounded-lg p-4 bg-white">
      <h3 className="font-medium text-stone-800 mb-3">Permission Modes</h3>
      <div className="grid grid-cols-2 gap-3">
        {modes.map((m) => (
          <div
            key={m.mode}
            className="border border-stone-200 rounded p-2 text-sm"
          >
            <div className="flex items-center gap-1.5 font-medium text-stone-700">
              <span className="text-stone-400">{m.icon}</span>
              <span>{m.label}</span>
            </div>
            <p className="text-xs text-stone-500 mt-1">{m.description}</p>
            <ul className="text-xs text-stone-400 mt-1">
              {m.features.map((f, i) => (
                <li key={i}>• {f}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
