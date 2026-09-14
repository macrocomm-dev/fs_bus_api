/** Current mobile choices. Historical labels are retained for older reports. */
export const CURRENT_SCHEDULE_BANDS = [
  { value: 'Early departure', label: 'Early departure', drillKey: 'behind-schedule-early' },
  { value: '0-5 mins', label: 'On time (0-5 mins)', drillKey: 'behind-schedule-0-5' },
  { value: '6-15 mins late', label: '6–15 minutes late', drillKey: 'behind-schedule-6-15' },
  { value: '15-30 mins late', label: '15–30 minutes late', drillKey: 'behind-schedule-15-30' },
  { value: '30+ mins late', label: '30 minutes or more late', drillKey: 'behind-schedule-30-plus' },
] as const;

const LABELS: Record<string, string> = {
  ...Object.fromEntries(CURRENT_SCHEDULE_BANDS.map((band) => [band.value, band.label])),
  '5-10 mins': '5–10 mins late (legacy)',
  '10-15 mins': '10–15 mins late (legacy)',
  '15+ mins': '15+ mins late (legacy)',
};

export function scheduleIntervalLabel(value: string | null | undefined): string {
  return value ? LABELS[value] ?? value : 'Not set';
}
