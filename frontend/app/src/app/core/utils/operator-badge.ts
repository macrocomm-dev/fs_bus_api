export type OperatorBadge = {
  label: string;
  code: string;
  icon: string;
  color: string;
  background: string;
  borderColor: string;
};

const KNOWN_OPERATORS: Record<string, OperatorBadge> = {
  'interstate bus lines': {
    label: 'Interstate Bus Lines',
    code: 'IBL',
    icon: 'pi pi-building',
    color: '#1d4ed8',
    background: '#dbeafe',
    borderColor: '#bfdbfe',
  },
  'maluti bus services': {
    label: 'Maluti Bus Services',
    code: 'MBS',
    icon: 'pi pi-building-columns',
    color: '#f97316',
    background: '#ffedd5',
    borderColor: '#fed7aa',
  },
  'bophelong transport': {
    label: 'Bophelong Transport',
    code: 'BOP',
    icon: 'pi pi-warehouse',
    color: '#16a34a',
    background: '#dcfce7',
    borderColor: '#bbf7d0',
  },
  'free state express': {
    label: 'Free State Express',
    code: 'FSE',
    icon: 'pi pi-building',
    color: '#7c3aed',
    background: '#ede9fe',
    borderColor: '#ddd6fe',
  },
};

export function operatorBadgeFor(operator: string | null | undefined): OperatorBadge | null {
  const label = operator?.trim();
  if (!label) return null;

  const knownBadge = KNOWN_OPERATORS[label.toLowerCase()];
  if (knownBadge) return knownBadge;

  return {
    label,
    code: initialsFor(label),
    icon: 'pi pi-building',
    color: '#64748b',
    background: '#f1f5f9',
    borderColor: '#cbd5e1',
  };
}

function initialsFor(label: string): string {
  const initials = label
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0]?.toUpperCase())
    .join('')
    .slice(0, 3);

  return initials || 'OP';
}
