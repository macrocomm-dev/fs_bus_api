import { Component, OnInit, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import type { EChartsOption } from 'echarts';
import { NgxEchartsDirective } from 'ngx-echarts';

import { AuthService } from '../../core/services/auth.service';
import { AnalyticsService } from '../../core/api/api/analytics.service';
import type { AnalyticsDrilldownResponse } from '../../core/api/model/analyticsDrilldownResponse';
import type { AnalyticsReportingSummaryResponse } from '../../core/api/model/analyticsReportingSummaryResponse';
import type { AnalyticsReportingTileResponse } from '../../core/api/model/analyticsReportingTileResponse';
import type { AnalyticsTopKpiResponse } from '../../core/api/model/analyticsTopKpiResponse';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { DividerModule } from 'primeng/divider';
import { FloatLabelModule } from 'primeng/floatlabel';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { MultiSelectModule } from 'primeng/multiselect';
import { DrawerModule } from 'primeng/drawer';
import { MenuModule } from 'primeng/menu';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';
import type { MenuItem } from 'primeng/api';

// ─── Types ──────────────────────────────────────────────────────────────────

export type TileStatus = 'good' | 'warning' | 'critical';

export interface SummaryItem {
  label: string;
  value: number | string;
  drillKey: string | null;
}

export interface KpiTile {
  id: string;
  title: string;
  metric: string;
  value: number | string;
  secondaryText?: string;
  status: TileStatus;
  icon: string;
  summaryItems: SummaryItem[];
  trendData?: {
    dates: string[];
    series: { name: string; data: number[] }[];
  };
}

export interface TableColumn {
  field: string;
  header: string;
}

export interface DrillConfig {
  title: string;
  columns: TableColumn[];
  data: Record<string, string | number>[];
}

type TopKpiApiValue = {
  value: string;
  secondaryText?: string;
  status?: TileStatus;
  summaryItems?: SummaryItem[];
  trendData?: {
    dates: string[];
    series: { name: string; data: number[] }[];
  };
};

// ─── Filter enrichment ───────────────────────────────────────────────────────

const TERMINAL_NAME_TO_CODE: Record<string, string> = {
  Bloemfontein: 'bfn',
  Welkom: 'welkom',
  Botshabelo: 'botshabelo',
  'Thaba Nchu': 'thabaNchu',
};

const ROUTE_TO_TERMINAL: Record<string, string> = {
  R03: 'bfn',
  R04: 'welkom',
  R05: 'welkom',
  R07: 'welkom',
  R08: 'botshabelo',
  R11: 'bfn',
  R12: 'botshabelo',
  R14: 'botshabelo',
  R15: 'bfn',
  R16: 'bfn',
  R18: 'thabaNchu',
  R19: 'thabaNchu',
  R22: 'thabaNchu',
  R23: 'welkom',
  R26: 'botshabelo',
  R30: 'bfn',
};

const TERMINAL_TO_OPERATOR: Record<string, string> = {
  bfn: 'interstate',
  welkom: 'welkom',
  botshabelo: 'bophelong',
  thabaNchu: 'mangaung',
};

const OPERATOR_NAME_TO_CODE: Record<string, string> = {
  'Interstate Bus Lines': 'interstate',
  'Free State Express': 'fse',
  'Bophelong Transport': 'bophelong',
  'Mangaung City Bus': 'mangaung',
  'Motheo Bus Service': 'motheo',
  'Welkom Transport Co': 'welkom',
  'SA Roadlink FS': 'saroadlink',
};

function enrichRecord(row: Record<string, string | number>): Record<string, string | number> {
  const terminalCode =
    (row['terminal'] ? TERMINAL_NAME_TO_CODE[String(row['terminal'])] : undefined) ??
    (row['route'] ? ROUTE_TO_TERMINAL[String(row['route'])] : undefined) ??
    '';
  const operatorCode =
    (row['operator'] ? OPERATOR_NAME_TO_CODE[String(row['operator'])] : undefined) ??
    (terminalCode ? TERMINAL_TO_OPERATOR[terminalCode] : undefined) ??
    '';
  const dateStr = String(row['date'] ?? row['inspectionDate'] ?? '2026-06-11');
  return {
    ...row,
    _terminal: terminalCode,
    _route: row['route'] ? String(row['route']).toLowerCase() : '',
    _operator: operatorCode,
    _date: dateStr,
  };
}

type AppliedFilters = {
  operators: string[];
  terminals: string[];
  routes: string[];
  dateFrom: Date;
  dateTo: Date;
};

function filterRecordsForKey(
  drillKey: string,
  f: AppliedFilters,
): Record<string, string | number>[] {
  const config = DRILL_CONFIGS[drillKey];
  if (!config) return [];
  const dtFrom = new Date(f.dateFrom);
  dtFrom.setHours(0, 0, 0, 0);
  const dtTo = new Date(f.dateTo);
  dtTo.setHours(23, 59, 59, 999);
  return config.data.map(enrichRecord).filter((row) => {
    if (f.operators.length > 0 && !f.operators.includes(String(row['_operator']))) return false;
    if (f.terminals.length > 0 && !f.terminals.includes(String(row['_terminal']))) return false;
    if (f.routes.length > 0 && !f.routes.includes(String(row['_route']))) return false;
    const d = new Date(String(row['_date']));
    if (!isNaN(d.getTime()) && (d < dtFrom || d > dtTo)) return false;
    return true;
  });
}

const INSPECTION_DRILL_KEYS = [
  'external-inspections',
  'internal-inspections',
  'driver-inspections',
  'technical-inspections',
];

const INSPECTION_TREND_CONFIG = [
  { key: 'external-inspections', label: 'External' },
  { key: 'internal-inspections', label: 'Internal' },
  { key: 'driver-inspections', label: 'Driver' },
  { key: 'passenger-counts-drill', label: 'Passenger' },
  { key: 'technical-inspections', label: 'Technical' },
];

const CHART_OPERATORS = ['Interstate Bus Lines', 'Bophelong Transport'];

const INSPECTION_TREND_DUMMY_DATA = {
  dates: ['2026-06-03', '2026-06-06', '2026-06-09', '2026-06-12', '2026-06-15'],
  series: [
    { name: 'External', data: [4, 6, 5, 7, 6] },
    { name: 'Internal', data: [3, 5, 4, 6, 5] },
    { name: 'Driver', data: [2, 3, 5, 4, 4] },
    { name: 'Passenger', data: [5, 4, 6, 7, 8] },
    { name: 'Technical', data: [1, 2, 2, 3, 4] },
  ],
};

const DELAYED_STARTS_DUMMY_DATA = {
  dates: ['2026-06-03', '2026-06-06', '2026-06-09', '2026-06-12', '2026-06-15'],
  series: [
    { name: 'Delayed Route Starts', data: [2, 4, 3, 5, 4] },
    { name: 'Major Delays', data: [1, 1, 2, 2, 1] },
  ],
};

const OPERATOR_COMPLIANCE_ROWS = [
  {
    operator: 'Interstate Bus Lines',
    drillKey: 'operator-compliance-interstate',
    shifts: 18,
    inspections: 85,
    passed: 82,
    failed: 3,
  },
  {
    operator: 'Bophelong Transport',
    drillKey: 'operator-compliance-bophelong',
    shifts: 14,
    inspections: 60,
    passed: 57,
    failed: 3,
  },
];

const OPERATOR_COMPLIANCE_TOTALS = OPERATOR_COMPLIANCE_ROWS.reduce(
  (totals, row) => ({
    shifts: totals.shifts + row.shifts,
    inspections: totals.inspections + row.inspections,
    passed: totals.passed + row.passed,
    failed: totals.failed + row.failed,
  }),
  { shifts: 0, inspections: 0, passed: 0, failed: 0 },
);

const OPERATOR_COMPLIANCE_SUMMARY_ITEMS: SummaryItem[] = [
  ...OPERATOR_COMPLIANCE_ROWS.map((row) => ({
    label: row.operator,
    value: `${row.shifts} shifts, ${row.inspections} inspections, ${row.passed} passed, ${row.failed} failed`,
    drillKey: row.drillKey,
  })),
  {
    label: 'Total',
    value: `${OPERATOR_COMPLIANCE_TOTALS.shifts} shifts, ${OPERATOR_COMPLIANCE_TOTALS.inspections} inspections, ${OPERATOR_COMPLIANCE_TOTALS.passed} passed, ${OPERATOR_COMPLIANCE_TOTALS.failed} failed`,
    drillKey: null,
  },
];

const TOP_KPI_DUMMY_VALUES: Record<string, string> = {
  'service-reliability': '94.8%',
  'operator-compliance': '91.6%',
  'photo-evidence': '4.1%',
  'fleet-health': '87.4%',
};

const FLEET_HEALTH_SCORE_BUCKETS = [
  { label: 'Under 50% Score', interstate: 2, bophelong: 3 },
  { label: 'Over 50% Score', interstate: 18, bophelong: 14 },
  { label: 'Over 80% Score', interstate: 13, bophelong: 9 },
  { label: 'Over 95% Score', interstate: 5, bophelong: 3 },
];

const FLEET_HEALTH_SUMMARY_ITEMS: SummaryItem[] = [
  ...FLEET_HEALTH_SCORE_BUCKETS.map((bucket) => ({
    label: bucket.label,
    value: bucket.interstate + bucket.bophelong,
    drillKey: null,
  })),
  {
    label: 'Overall Analytics Score',
    value: TOP_KPI_DUMMY_VALUES['fleet-health'],
    drillKey: null,
  },
];

function buildOperatorComplianceDrillData(row: (typeof OPERATOR_COMPLIANCE_ROWS)[number]) {
  return [
    { metric: 'Shifts', count: row.shifts },
    { metric: 'Inspections', count: row.inspections },
    { metric: 'Passed Inspections', count: row.passed },
    { metric: 'Failed Inspections', count: row.failed },
  ];
}

function isFailedInspectionTypeRow(
  sourceKey: string,
  row: Record<string, string | number>,
): boolean {
  if (sourceKey === 'passenger-counts-drill') {
    return Number(row['overloadedCount'] ?? 0) > 0;
  }
  return hasFailedInspectionValue(row);
}

function hasFailedInspectionValue(row: Record<string, string | number>): boolean {
  if (row['defectType']) return true;

  const failureValues = new Set(['fail', 'missing', 'no', 'high', 'critical']);
  return Object.entries(row).some(([field, value]) => {
    if (field.startsWith('_')) return false;
    if (
      [
        'busReg',
        'fleetNo',
        'inspector',
        'driver',
        'terminal',
        'date',
        'gps',
        'startTime',
        'endTime',
      ].includes(field)
    ) {
      return false;
    }
    return failureValues.has(String(value).trim().toLowerCase());
  });
}

// ─── Drill-down data ─────────────────────────────────────────────────────────

const DRILL_CONFIGS: Record<string, DrillConfig> = {
  // ── Tile 1: Daily Bus Monitoring ──────────────────────────────────────────
  completed: {
    title: 'Completed Inspections',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'startTime', header: 'Start' },
      { field: 'endTime', header: 'End' },
      { field: 'gps', header: 'GPS' },
      { field: 'status', header: 'Status' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        inspector: 'John Smith',
        terminal: 'Bloemfontein',
        startTime: '07:10',
        endTime: '07:18',
        gps: '-29.1187, 26.2145',
        status: 'Complete',
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        inspector: 'Jane Doe',
        terminal: 'Welkom',
        startTime: '07:20',
        endTime: '07:31',
        gps: '-27.9874, 26.7343',
        status: 'Complete',
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        inspector: 'James Nkosi',
        terminal: 'Bloemfontein',
        startTime: '08:05',
        endTime: '08:14',
        gps: '-29.1190, 26.2148',
        status: 'Complete',
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        inspector: 'Sarah Mokoena',
        terminal: 'Botshabelo',
        startTime: '08:30',
        endTime: '08:41',
        gps: '-29.2645, 26.7150',
        status: 'Complete',
      },
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        inspector: 'Peter Dlamini',
        terminal: 'Thaba Nchu',
        startTime: '09:00',
        endTime: '09:11',
        gps: '-29.3200, 26.8420',
        status: 'Complete',
      },
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        inspector: 'Zanele Mokoena',
        terminal: 'Bloemfontein',
        startTime: '09:30',
        endTime: '09:42',
        gps: '-29.1191, 26.2150',
        status: 'Complete',
      },
    ],
  },
  // ── Tile 1: Inspection Type Breakdowns ────────────────────────────────────
  'external-inspections': {
    title: 'External Inspections',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'tyres', header: 'Tyres' },
      { field: 'windows', header: 'Windows' },
      { field: 'other', header: 'Other' },
      { field: 'gps', header: 'GPS' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        inspector: 'John Smith',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        tyres: 'Pass',
        windows: 'Pass',
        other: 'Pass',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        inspector: 'Jane Doe',
        terminal: 'Welkom',
        date: '2026-06-11',
        tyres: 'Pass',
        windows: 'Fail',
        other: 'Pass',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        inspector: 'James Nkosi',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        tyres: 'Pass',
        windows: 'Pass',
        other: 'Pass',
        gps: '-29.1190, 26.2148',
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        inspector: 'Sarah Mokoena',
        terminal: 'Botshabelo',
        date: '2026-06-10',
        tyres: 'Fail',
        windows: 'Pass',
        other: 'Pass',
        gps: '-29.2645, 26.7150',
      },
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        inspector: 'Peter Dlamini',
        terminal: 'Thaba Nchu',
        date: '2026-06-10',
        tyres: 'Pass',
        windows: 'Pass',
        other: 'Fail',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        inspector: 'Zanele Mokoena',
        terminal: 'Bloemfontein',
        date: '2026-06-10',
        tyres: 'Pass',
        windows: 'Pass',
        other: 'Pass',
        gps: '-29.1191, 26.2150',
      },
    ],
  },
  'internal-inspections': {
    title: 'Internal Inspections',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'fireExtinguisher', header: 'Fire Extinguisher' },
      { field: 'seats', header: 'Seats' },
      { field: 'aisle', header: 'Aisle' },
      { field: 'gps', header: 'GPS' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        inspector: 'John Smith',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        fireExtinguisher: 'Present',
        seats: 'Pass',
        aisle: 'Pass',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        inspector: 'Jane Doe',
        terminal: 'Welkom',
        date: '2026-06-11',
        fireExtinguisher: 'Present',
        seats: 'Fail',
        aisle: 'Pass',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        inspector: 'James Nkosi',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        fireExtinguisher: 'Missing',
        seats: 'Pass',
        aisle: 'Pass',
        gps: '-29.1190, 26.2148',
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        inspector: 'Sarah Mokoena',
        terminal: 'Botshabelo',
        date: '2026-06-10',
        fireExtinguisher: 'Present',
        seats: 'Pass',
        aisle: 'Fail',
        gps: '-29.2645, 26.7150',
      },
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        inspector: 'Peter Dlamini',
        terminal: 'Thaba Nchu',
        date: '2026-06-10',
        fireExtinguisher: 'Present',
        seats: 'Pass',
        aisle: 'Pass',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        inspector: 'Zanele Mokoena',
        terminal: 'Bloemfontein',
        date: '2026-06-10',
        fireExtinguisher: 'Present',
        seats: 'Fail',
        aisle: 'Pass',
        gps: '-29.1191, 26.2150',
      },
    ],
  },
  'driver-inspections': {
    title: 'Driver Inspections',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'driver', header: 'Driver' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'pdpExpiry', header: 'PDP Expiry' },
      { field: 'driverIdentified', header: 'Identified' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        driver: 'Thabo Khumalo',
        inspector: 'John Smith',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        pdpExpiry: '2027-03-15',
        driverIdentified: 'Yes',
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        driver: 'Nomsa Dlamini',
        inspector: 'Jane Doe',
        terminal: 'Welkom',
        date: '2026-06-11',
        pdpExpiry: '2026-11-20',
        driverIdentified: 'Yes',
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        driver: 'Bongani Mthembu',
        inspector: 'James Nkosi',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        pdpExpiry: '2027-01-05',
        driverIdentified: 'Yes',
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        driver: 'Sipho Radebe',
        inspector: 'Sarah Mokoena',
        terminal: 'Botshabelo',
        date: '2026-06-10',
        pdpExpiry: '2026-08-30',
        driverIdentified: 'Yes',
      },
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        driver: 'Andile Molefe',
        inspector: 'Peter Dlamini',
        terminal: 'Thaba Nchu',
        date: '2026-06-10',
        pdpExpiry: '2027-05-12',
        driverIdentified: 'No',
      },
    ],
  },
  'passenger-counts-drill': {
    title: 'Passenger Counts',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'time', header: 'Time' },
      { field: 'seated', header: 'Seated' },
      { field: 'standing', header: 'Standing' },
      { field: 'total', header: 'Total Pax' },
      { field: 'overloadedCount', header: 'Overloaded Count' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        route: 'R03',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        time: '07:15',
        seated: 42,
        standing: 0,
        total: 42,
        overloadedCount: 0,
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        route: 'R07',
        terminal: 'Welkom',
        date: '2026-06-11',
        time: '07:35',
        seated: 54,
        standing: 8,
        total: 62,
        overloadedCount: 8,
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        route: 'R11',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        time: '08:10',
        seated: 48,
        standing: 0,
        total: 48,
        overloadedCount: 0,
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        route: 'R12',
        terminal: 'Botshabelo',
        date: '2026-06-10',
        time: '08:45',
        seated: 54,
        standing: 12,
        total: 66,
        overloadedCount: 12,
      },
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        route: 'R19',
        terminal: 'Thaba Nchu',
        date: '2026-06-10',
        time: '09:05',
        seated: 38,
        standing: 0,
        total: 38,
        overloadedCount: 0,
      },
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        route: 'R15',
        terminal: 'Bloemfontein',
        date: '2026-06-10',
        time: '09:40',
        seated: 51,
        standing: 4,
        total: 55,
        overloadedCount: 1,
      },
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        route: 'R03',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        time: '11:15',
        seated: 45,
        standing: 0,
        total: 45,
        overloadedCount: 0,
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        route: 'R07',
        terminal: 'Welkom',
        date: '2026-06-11',
        time: '12:35',
        seated: 52,
        standing: 2,
        total: 54,
        overloadedCount: 0,
      },
    ],
  },
  'behind-schedule-drill': {
    title: 'Behind Schedule Reports',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'interval', header: 'Delay Interval' },
    ],
    data: [
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        route: 'R07',
        driver: 'Nomsa Dlamini',
        terminal: 'Welkom',
        date: '2026-06-11',
        interval: '5-10 mins',
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        route: 'R12',
        driver: 'Sipho Radebe',
        terminal: 'Botshabelo',
        date: '2026-06-10',
        interval: '10-15 mins',
      },
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        route: 'R15',
        driver: 'Zanele Mokoena',
        terminal: 'Bloemfontein',
        date: '2026-06-10',
        interval: '15+ mins',
      },
    ],
  },
  'behind-schedule-0-5': {
    title: 'Behind Schedule (0–5 mins)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'interval', header: 'Delay Interval' },
    ],
    data: [],
  },
  'behind-schedule-5-10': {
    title: 'Behind Schedule (5–10 mins)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'interval', header: 'Delay Interval' },
    ],
    data: [
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        route: 'R07',
        driver: 'Nomsa Dlamini',
        terminal: 'Welkom',
        date: '2026-06-11',
        interval: '5-10 mins',
      },
    ],
  },
  'behind-schedule-10-15': {
    title: 'Behind Schedule (10–15 mins)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'interval', header: 'Delay Interval' },
    ],
    data: [
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        route: 'R12',
        driver: 'Sipho Radebe',
        terminal: 'Botshabelo',
        date: '2026-06-10',
        interval: '10-15 mins',
      },
    ],
  },
  'behind-schedule-15-plus': {
    title: 'Behind Schedule (15+ mins)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'interval', header: 'Delay Interval' },
    ],
    data: [
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        route: 'R15',
        driver: 'Zanele Mokoena',
        terminal: 'Bloemfontein',
        date: '2026-06-10',
        interval: '15+ mins',
      },
    ],
  },
  'technical-inspections': {
    title: 'Technical Inspections',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'date', header: 'Date' },
      { field: 'defectType', header: 'Defect Type' },
      { field: 'severity', header: 'Severity' },
      { field: 'gps', header: 'GPS' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        inspector: 'John Smith',
        terminal: 'Bloemfontein',
        date: '2026-06-11',
        defectType: 'Engine Warning Light',
        severity: 'Medium',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        inspector: 'Jane Doe',
        terminal: 'Welkom',
        date: '2026-06-11',
        defectType: 'Oil Leak',
        severity: 'High',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        inspector: 'James Nkosi',
        terminal: 'Bloemfontein',
        date: '2026-06-10',
        defectType: 'AC Malfunction',
        severity: 'Low',
        gps: '-29.1190, 26.2148',
      },
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        inspector: 'Peter Dlamini',
        terminal: 'Thaba Nchu',
        date: '2026-06-10',
        defectType: 'Brake Fluid Low',
        severity: 'High',
        gps: '-29.3200, 26.8420',
      },
    ],
  },

  // ── Tile 2: Route Exceptions ──────────────────────────────────────────────
  'route-deviation-events': {
    title: 'Route Deviations',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'date', header: 'Date' },
      { field: 'time', header: 'Time' },
      { field: 'deviation', header: 'Deviation' },
      { field: 'gps', header: 'GPS' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        route: 'R12',
        driver: 'John Smith',
        date: '2026-06-11',
        time: '07:14',
        deviation: '4.2 km',
        gps: '-29.2645, 26.7150',
      },
      {
        busReg: 'FSB234FS',
        fleetNo: '1033',
        route: 'R08',
        driver: 'David Motaung',
        date: '2026-06-11',
        time: '09:22',
        deviation: '6.7 km',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB765FS',
        fleetNo: '1066',
        route: 'R22',
        driver: 'Sipho Radebe',
        date: '2026-06-11',
        time: '10:05',
        deviation: '3.1 km',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB432FS',
        fleetNo: '1077',
        route: 'R04',
        driver: 'Andile Molefe',
        date: '2026-06-11',
        time: '11:15',
        deviation: '8.4 km',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB155FS',
        fleetNo: '1022',
        route: 'R03',
        driver: 'Thabo Khumalo',
        date: '2026-06-11',
        time: '06:55',
        deviation: '0.8 km',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB266FS',
        fleetNo: '1031',
        route: 'R07',
        driver: 'Nomsa Dlamini',
        date: '2026-06-11',
        time: '07:42',
        deviation: '1.2 km',
        gps: '-27.9874, 26.7343',
      },
    ],
  },
  'missed-stops': {
    title: 'Missed Stops',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'missedStop', header: 'Missed Stop' },
      { field: 'driver', header: 'Driver' },
      { field: 'date', header: 'Date' },
      { field: 'time', header: 'Time' },
      { field: 'gps', header: 'GPS' },
    ],
    data: [
      {
        busReg: 'FSB888FS',
        fleetNo: '1187',
        route: 'R15',
        missedStop: 'Hamilton Depot',
        driver: 'Peter Jones',
        date: '2026-06-11',
        time: '08:33',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB444FS',
        fleetNo: '1190',
        route: 'R22',
        missedStop: 'Thaba Nchu Rank',
        driver: 'Peter Sithole',
        date: '2026-06-11',
        time: '09:02',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB555FS',
        fleetNo: '1201',
        route: 'R05',
        missedStop: 'Welkom Central',
        driver: 'Jan Booysen',
        date: '2026-06-11',
        time: '10:15',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB666FS',
        fleetNo: '1215',
        route: 'R14',
        missedStop: 'Botshabelo Mall',
        driver: 'Kelebogile Mosia',
        date: '2026-06-10',
        time: '11:30',
        gps: '-29.2645, 26.7150',
      },
    ],
  },
  'route-deviations': {
    title: 'Route Deviations',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'date', header: 'Date' },
      { field: 'time', header: 'Time' },
      { field: 'exceptionType', header: 'Exception Type' },
      { field: 'deviation', header: 'Deviation (km)' },
      { field: 'gps', header: 'GPS' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        route: 'R12',
        driver: 'John Smith',
        date: '2026-06-11',
        time: '07:14',
        exceptionType: 'Route Deviation',
        deviation: '4.2',
        gps: '-29.2645, 26.7150',
      },
      {
        busReg: 'FSB888FS',
        fleetNo: '1187',
        route: 'R15',
        driver: 'Peter Jones',
        date: '2026-06-11',
        time: '08:33',
        exceptionType: 'Unauthorised Stop',
        deviation: '0.0',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB234FS',
        fleetNo: '1033',
        route: 'R08',
        driver: 'David Motaung',
        date: '2026-06-11',
        time: '09:22',
        exceptionType: 'Route Deviation',
        deviation: '6.7',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB765FS',
        fleetNo: '1066',
        route: 'R22',
        driver: 'Sipho Radebe',
        date: '2026-06-11',
        time: '10:05',
        exceptionType: 'Route Deviation',
        deviation: '3.1',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB432FS',
        fleetNo: '1077',
        route: 'R04',
        driver: 'Andile Molefe',
        date: '2026-06-11',
        time: '11:15',
        exceptionType: 'Route Deviation',
        deviation: '8.4',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB155FS',
        fleetNo: '1022',
        route: 'R03',
        driver: 'Thabo Khumalo',
        date: '2026-06-11',
        time: '06:55',
        exceptionType: 'Minor Deviation',
        deviation: '0.8',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB266FS',
        fleetNo: '1031',
        route: 'R07',
        driver: 'Nomsa Dlamini',
        date: '2026-06-11',
        time: '07:42',
        exceptionType: 'Minor Deviation',
        deviation: '1.2',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB377FS',
        fleetNo: '1048',
        route: 'R11',
        driver: 'Bongani Mthembu',
        date: '2026-06-11',
        time: '08:18',
        exceptionType: 'Minor Deviation',
        deviation: '0.5',
        gps: '-29.1190, 26.2148',
      },
      {
        busReg: 'FSB488FS',
        fleetNo: '1059',
        route: 'R16',
        driver: 'Zanele Mokoena',
        date: '2026-06-10',
        time: '09:00',
        exceptionType: 'Late Stop',
        deviation: '0.0',
        gps: '-29.1187, 26.2145',
      },
      {
        busReg: 'FSB599FS',
        fleetNo: '1071',
        route: 'R19',
        driver: 'Lucky Sithole',
        date: '2026-06-10',
        time: '09:30',
        exceptionType: 'Minor Deviation',
        deviation: '1.5',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB611FS',
        fleetNo: '1083',
        route: 'R23',
        driver: 'Faith Leballo',
        date: '2026-06-10',
        time: '10:15',
        exceptionType: 'Early Stop',
        deviation: '0.0',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB722FS',
        fleetNo: '1094',
        route: 'R26',
        driver: 'Moses Ntuli',
        date: '2026-06-10',
        time: '11:00',
        exceptionType: 'Minor Deviation',
        deviation: '0.9',
        gps: '-29.2645, 26.7150',
      },
      {
        busReg: 'FSB833FS',
        fleetNo: '1102',
        route: 'R30',
        driver: 'Grace Nkosi',
        date: '2026-06-10',
        time: '11:45',
        exceptionType: 'Minor Deviation',
        deviation: '1.1',
        gps: '-29.1191, 26.2150',
      },
      {
        busReg: 'FSB444FS',
        fleetNo: '1190',
        route: 'R22',
        driver: 'Peter Sithole',
        date: '2026-06-11',
        time: '09:02',
        exceptionType: 'Unauthorised Stop',
        deviation: '8 min stop',
        gps: '-29.3200, 26.8420',
      },
      {
        busReg: 'FSB555FS',
        fleetNo: '1201',
        route: 'R05',
        driver: 'Jan Booysen',
        date: '2026-06-11',
        time: '10:15',
        exceptionType: 'Unauthorised Stop',
        deviation: '12 min stop',
        gps: '-27.9874, 26.7343',
      },
      {
        busReg: 'FSB666FS',
        fleetNo: '1215',
        route: 'R14',
        driver: 'Kelebogile Mosia',
        date: '2026-06-10',
        time: '11:30',
        exceptionType: 'Unauthorised Stop',
        deviation: '5 min stop',
        gps: '-29.2645, 26.7150',
      },
      {
        busReg: 'FSB777FS',
        fleetNo: '1230',
        route: 'R18',
        driver: 'Thuto Maleka',
        date: '2026-06-10',
        time: '12:00',
        exceptionType: 'Unauthorised Stop',
        deviation: '15 min stop',
        gps: '-29.1187, 26.2145',
      },
    ],
  },

  // ── Tile 3: Compliance Violations ────────────────────────────────────────
  'expired-pdp': {
    title: 'Expired PDP',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'driver', header: 'Driver' },
      { field: 'pdpExpiry', header: 'PDP Expiry' },
      { field: 'daysOverdue', header: 'Days Overdue' },
      { field: 'terminal', header: 'Terminal' },
    ],
    data: [
      {
        busReg: 'FSB101FS',
        fleetNo: '1011',
        driver: 'John Molefe',
        pdpExpiry: '2026-05-15',
        daysOverdue: 27,
        terminal: 'Bloemfontein',
      },
      {
        busReg: 'FSB202FS',
        fleetNo: '1022',
        driver: 'Sarah Mthembu',
        pdpExpiry: '2026-04-30',
        daysOverdue: 42,
        terminal: 'Welkom',
      },
      {
        busReg: 'FSB303FS',
        fleetNo: '1033',
        driver: 'Tom Khumalo',
        pdpExpiry: '2026-05-20',
        daysOverdue: 22,
        terminal: 'Botshabelo',
      },
    ],
  },
  'expired-driver-licence': {
    title: 'Expired Driver Licences',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'driver', header: 'Driver' },
      { field: 'licenceExpiry', header: 'Licence Expiry' },
      { field: 'daysOverdue', header: 'Days Overdue' },
      { field: 'terminal', header: 'Terminal' },
    ],
    data: [
      {
        busReg: 'FSB404FS',
        fleetNo: '1044',
        driver: 'Mike Radebe',
        licenceExpiry: '2026-05-01',
        daysOverdue: 41,
        terminal: 'Thaba Nchu',
      },
      {
        busReg: 'FSB505FS',
        fleetNo: '1055',
        driver: 'Linda Dlamini',
        licenceExpiry: '2026-05-25',
        daysOverdue: 17,
        terminal: 'Bloemfontein',
      },
    ],
  },
  'expired-route-licence': {
    title: 'Expired Route Licences',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'operator', header: 'Operator' },
      { field: 'licenceExpiry', header: 'Licence Expiry' },
      { field: 'daysOverdue', header: 'Days Overdue' },
    ],
    data: [
      {
        busReg: 'FSB606FS',
        fleetNo: '1066',
        route: 'R12',
        operator: 'Interstate Bus Lines',
        licenceExpiry: '2026-05-31',
        daysOverdue: 11,
      },
    ],
  },
  'expired-bus-license-disk': {
    title: 'Expired Bus Licence Disks',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'operator', header: 'Operator' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'diskExpiry', header: 'Disk Expiry' },
      { field: 'daysOverdue', header: 'Days Overdue' },
    ],
    data: [
      {
        busReg: 'FSB707FS',
        fleetNo: '1077',
        operator: 'Bophelong Transport',
        terminal: 'Botshabelo',
        diskExpiry: '2026-05-18',
        daysOverdue: 24,
      },
      {
        busReg: 'FSB808FS',
        fleetNo: '1088',
        operator: 'Interstate Bus Lines',
        terminal: 'Bloemfontein',
        diskExpiry: '2026-06-01',
        daysOverdue: 10,
      },
    ],
  },
  roadworthiness: {
    title: 'Roadworthiness Failures',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'defectType', header: 'Defect Type' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'inspectionDate', header: 'Inspection Date' },
      { field: 'severity', header: 'Severity' },
    ],
    data: [
      {
        busReg: 'FSB444FS',
        fleetNo: '1044',
        defectType: 'Tyre Wear',
        inspector: 'Joe Bloggs',
        inspectionDate: '2026-06-11',
        severity: 'High',
      },
      {
        busReg: 'FSB887FS',
        fleetNo: '1120',
        defectType: 'Cracked Windscreen',
        inspector: 'Jane Smith',
        inspectionDate: '2026-06-11',
        severity: 'Medium',
      },
      {
        busReg: 'FSB110FS',
        fleetNo: '1010',
        defectType: 'Faulty Brakes',
        inspector: 'Mark Nkosi',
        inspectionDate: '2026-06-10',
        severity: 'Critical',
      },
      {
        busReg: 'FSB220FS',
        fleetNo: '1021',
        defectType: 'Lights Failure',
        inspector: 'Anne Dlamini',
        inspectionDate: '2026-06-10',
        severity: 'High',
      },
      {
        busReg: 'FSB330FS',
        fleetNo: '1032',
        defectType: 'Door Malfunction',
        inspector: 'Paul Sithole',
        inspectionDate: '2026-06-09',
        severity: 'Medium',
      },
    ],
  },

  // ── Tile 4: Interior Defects ──────────────────────────────────────────────
  'fire-extinguisher-defects': {
    title: 'Fire Extinguisher Defects',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'defectDescription', header: 'Description' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
    ],
    data: [
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        defectDescription: 'Fire extinguisher missing',
        inspector: 'James Nkosi',
        date: '2026-06-11',
      },
      {
        busReg: 'FSB606FS',
        fleetNo: '1066',
        defectDescription: 'Fire extinguisher pressure gauge low',
        inspector: 'Mike Radebe',
        date: '2026-06-10',
      },
    ],
  },
  'seat-defects': {
    title: 'Seat Defects',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'defectDescription', header: 'Description' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        seatNumbers: '14, 15',
        defectDescription: 'Torn upholstery',
        inspector: 'John Smith',
        date: '2026-06-11',
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        seatNumbers: '03',
        defectDescription: 'Broken armrest',
        inspector: 'Jane Doe',
        date: '2026-06-11',
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        seatNumbers: '22, 23, 24',
        defectDescription: 'Missing headrests',
        inspector: 'James Nkosi',
        date: '2026-06-10',
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        seatNumbers: '07',
        defectDescription: 'Broken seat frame',
        inspector: 'Sarah Mokoena',
        date: '2026-06-10',
      },
    ],
  },
  'tyre-defects': {
    title: 'Tyre Defects',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'defectDescription', header: 'Description' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
    ],
    data: [
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        defectDescription: 'Tyre tread below threshold',
        inspector: 'Sarah Mokoena',
        date: '2026-06-10',
      },
      {
        busReg: 'FSB444FS',
        fleetNo: '1044',
        defectDescription: 'Uneven front tyre wear',
        inspector: 'Joe Bloggs',
        date: '2026-06-11',
      },
    ],
  },
  'window-defects': {
    title: 'Window Defects',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'defectDescription', header: 'Description' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
    ],
    data: [
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        defectDescription: 'Passenger window latch failed',
        inspector: 'Jane Doe',
        date: '2026-06-11',
      },
      {
        busReg: 'FSB887FS',
        fleetNo: '1120',
        defectDescription: 'Cracked windscreen',
        inspector: 'Jane Smith',
        date: '2026-06-11',
      },
    ],
  },
  'aisle-obstructions': {
    title: 'Aisle Obstructions',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'location', header: 'Location' },
      { field: 'description', header: 'Description' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
    ],
    data: [
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        location: 'Middle aisle',
        description: 'Damaged floor panel',
        inspector: 'Peter Dlamini',
        date: '2026-06-11',
      },
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        location: 'Rear aisle',
        description: 'Luggage blocking exit',
        inspector: 'Zanele Mokoena',
        date: '2026-06-10',
      },
    ],
  },
  'other-defects': {
    title: 'Other Defects',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'area', header: 'Area' },
      { field: 'description', header: 'Description' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
    ],
    data: [
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        area: 'Exterior other',
        description: 'Loose body panel',
        inspector: 'Peter Dlamini',
        date: '2026-06-10',
      },
      {
        busReg: 'FSB111FS',
        fleetNo: '1099',
        area: 'Interior other',
        description: 'Damaged fare signage',
        inspector: 'Tom Leballo',
        date: '2026-06-11',
      },
    ],
  },
  'general-condition': {
    title: 'General Condition Issues',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'area', header: 'Area' },
      { field: 'description', header: 'Description' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
    ],
    data: [
      {
        busReg: 'FSB111FS',
        fleetNo: '1099',
        area: 'Interior windows',
        description: 'Excessive graffiti',
        inspector: 'Tom Leballo',
        date: '2026-06-11',
      },
      {
        busReg: 'FSB222FS',
        fleetNo: '1102',
        area: 'Ceiling',
        description: 'Water stains and damp',
        inspector: 'Mary Sithole',
        date: '2026-06-09',
      },
    ],
  },

  // ── Tile 5: Overloaded Trips ──────────────────────────────────────────────
  'critical-overload': {
    title: 'Critical Overloaded Trips (>30%)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'capacity', header: 'Capacity' },
      { field: 'count', header: 'Pax Count' },
      { field: 'overloadPct', header: 'Overload %' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        route: 'R03',
        driver: 'Thabo Khumalo',
        terminal: 'Bloemfontein',
        capacity: 54,
        count: 73,
        overloadPct: '35%',
      },
      {
        busReg: 'FSB456FS',
        fleetNo: '1045',
        route: 'R07',
        driver: 'Nomsa Dlamini',
        terminal: 'Welkom',
        capacity: 54,
        count: 78,
        overloadPct: '44%',
      },
      {
        busReg: 'FSB789FS',
        fleetNo: '1187',
        route: 'R12',
        driver: 'Bongani Mthembu',
        terminal: 'Botshabelo',
        capacity: 54,
        count: 72,
        overloadPct: '33%',
      },
      {
        busReg: 'FSB321FS',
        fleetNo: '1056',
        route: 'R15',
        driver: 'John Smith',
        terminal: 'Bloemfontein',
        capacity: 54,
        count: 76,
        overloadPct: '41%',
      },
      {
        busReg: 'FSB654FS',
        fleetNo: '1078',
        route: 'R19',
        driver: 'Jane Doe',
        terminal: 'Welkom',
        capacity: 54,
        count: 71,
        overloadPct: '31%',
      },
      {
        busReg: 'FSB987FS',
        fleetNo: '1090',
        route: 'R22',
        driver: 'James Nkosi',
        terminal: 'Thaba Nchu',
        capacity: 54,
        count: 82,
        overloadPct: '52%',
      },
      {
        busReg: 'FSB111FS',
        fleetNo: '1099',
        route: 'R26',
        driver: 'Sarah Mokoena',
        terminal: 'Bloemfontein',
        capacity: 54,
        count: 75,
        overloadPct: '39%',
      },
      {
        busReg: 'FSB222FS',
        fleetNo: '1102',
        route: 'R30',
        driver: 'Peter Dlamini',
        terminal: 'Welkom',
        capacity: 54,
        count: 73,
        overloadPct: '35%',
      },
    ],
  },
  'moderate-overload': {
    title: 'Moderate Overloaded Trips (10–30%)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'capacity', header: 'Capacity' },
      { field: 'count', header: 'Pax Count' },
      { field: 'overloadPct', header: 'Overload %' },
    ],
    data: [
      {
        busReg: 'FSB333FS',
        fleetNo: '1115',
        route: 'R04',
        driver: 'Tom Khumalo',
        terminal: 'Botshabelo',
        capacity: 54,
        count: 61,
        overloadPct: '13%',
      },
      {
        busReg: 'FSB444FS',
        fleetNo: '1044',
        route: 'R08',
        driver: 'Zanele Mokoena',
        terminal: 'Welkom',
        capacity: 54,
        count: 64,
        overloadPct: '19%',
      },
      {
        busReg: 'FSB555FS',
        fleetNo: '1055',
        route: 'R11',
        driver: 'Lucky Sithole',
        terminal: 'Bloemfontein',
        capacity: 54,
        count: 67,
        overloadPct: '24%',
      },
    ],
  },

  // ── Tile 6: Delayed Departures ────────────────────────────────────────────
  'minor-delay': {
    title: 'Minor Delayed Departures (5–15 min)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'scheduled', header: 'Scheduled' },
      { field: 'actual', header: 'Actual' },
      { field: 'delayMins', header: 'Delay (min)' },
      { field: 'terminal', header: 'Terminal' },
    ],
    data: [
      {
        busReg: 'FSB101FS',
        fleetNo: '1011',
        route: 'R03',
        driver: 'John Molefe',
        scheduled: '06:00',
        actual: '06:08',
        delayMins: 8,
        terminal: 'Bloemfontein',
      },
      {
        busReg: 'FSB202FS',
        fleetNo: '1022',
        route: 'R07',
        driver: 'Sarah Mthembu',
        scheduled: '06:15',
        actual: '06:22',
        delayMins: 7,
        terminal: 'Welkom',
      },
      {
        busReg: 'FSB303FS',
        fleetNo: '1033',
        route: 'R12',
        driver: 'Tom Khumalo',
        scheduled: '06:30',
        actual: '06:43',
        delayMins: 13,
        terminal: 'Botshabelo',
      },
      {
        busReg: 'FSB404FS',
        fleetNo: '1044',
        route: 'R15',
        driver: 'Sipho Radebe',
        scheduled: '07:00',
        actual: '07:10',
        delayMins: 10,
        terminal: 'Thaba Nchu',
      },
      {
        busReg: 'FSB505FS',
        fleetNo: '1055',
        route: 'R19',
        driver: 'Andile Molefe',
        scheduled: '07:15',
        actual: '07:26',
        delayMins: 11,
        terminal: 'Bloemfontein',
      },
    ],
  },
  'major-delay': {
    title: 'Major Delayed Departures (>15 min)',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'scheduled', header: 'Scheduled' },
      { field: 'actual', header: 'Actual' },
      { field: 'delayMins', header: 'Delay (min)' },
      { field: 'reason', header: 'Reason' },
      { field: 'terminal', header: 'Terminal' },
    ],
    data: [
      {
        busReg: 'FSB606FS',
        fleetNo: '1066',
        route: 'R22',
        driver: 'Mike Radebe',
        scheduled: '06:00',
        actual: '06:25',
        delayMins: 25,
        reason: 'Mechanical Fault',
        terminal: 'Welkom',
      },
      {
        busReg: 'FSB707FS',
        fleetNo: '1077',
        route: 'R26',
        driver: 'Linda Dlamini',
        scheduled: '06:30',
        actual: '07:05',
        delayMins: 35,
        reason: 'Driver Late',
        terminal: 'Bloemfontein',
      },
      {
        busReg: 'FSB808FS',
        fleetNo: '1088',
        route: 'R30',
        driver: 'Kelebogile Mosia',
        scheduled: '07:00',
        actual: '07:20',
        delayMins: 20,
        reason: 'Traffic Incident',
        terminal: 'Botshabelo',
      },
      {
        busReg: 'FSB909FS',
        fleetNo: '1099',
        route: 'R04',
        driver: 'Thuto Maleka',
        scheduled: '07:30',
        actual: '08:05',
        delayMins: 35,
        reason: 'Bus Breakdown',
        terminal: 'Welkom',
      },
    ],
  },

  // ── Tile 7: Service Reliability ───────────────────────────────────────────
  'on-time': {
    title: 'On-Time Departures by Route',
    columns: [
      { field: 'route', header: 'Route' },
      { field: 'onTime', header: 'On-Time' },
      { field: 'delayed', header: 'Delayed' },
      { field: 'cancelled', header: 'Cancelled' },
      { field: 'total', header: 'Total' },
      { field: 'reliabilityPct', header: 'Reliability %' },
    ],
    data: [
      { route: 'R03', onTime: 28, delayed: 1, cancelled: 0, total: 29, reliabilityPct: '96.6%' },
      { route: 'R07', onTime: 25, delayed: 0, cancelled: 0, total: 25, reliabilityPct: '100%' },
      { route: 'R12', onTime: 30, delayed: 2, cancelled: 0, total: 32, reliabilityPct: '93.8%' },
      { route: 'R15', onTime: 27, delayed: 1, cancelled: 0, total: 28, reliabilityPct: '96.4%' },
      { route: 'R19', onTime: 26, delayed: 0, cancelled: 0, total: 26, reliabilityPct: '100%' },
      { route: 'R22', onTime: 29, delayed: 3, cancelled: 0, total: 32, reliabilityPct: '90.6%' },
      { route: 'R26', onTime: 22, delayed: 2, cancelled: 0, total: 24, reliabilityPct: '91.7%' },
      { route: 'R30', onTime: 31, delayed: 1, cancelled: 0, total: 32, reliabilityPct: '96.9%' },
    ],
  },
  'reliability-delayed': {
    title: 'Delayed Services',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'scheduled', header: 'Scheduled' },
      { field: 'actual', header: 'Actual' },
      { field: 'delayMins', header: 'Delay (min)' },
      { field: 'terminal', header: 'Terminal' },
    ],
    data: [
      {
        busReg: 'FSB606FS',
        fleetNo: '1066',
        route: 'R12',
        driver: 'Mike Radebe',
        scheduled: '07:00',
        actual: '07:18',
        delayMins: 18,
        terminal: 'Welkom',
      },
      {
        busReg: 'FSB707FS',
        fleetNo: '1077',
        route: 'R22',
        driver: 'Linda Dlamini',
        scheduled: '08:00',
        actual: '08:22',
        delayMins: 22,
        terminal: 'Bloemfontein',
      },
      {
        busReg: 'FSB808FS',
        fleetNo: '1088',
        route: 'R22',
        driver: 'Kelebogile Mosia',
        scheduled: '09:00',
        actual: '09:08',
        delayMins: 8,
        terminal: 'Botshabelo',
      },
    ],
  },
  cancelled: {
    title: 'Cancelled Services',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'route', header: 'Route' },
      { field: 'scheduledTime', header: 'Scheduled Time' },
      { field: 'reason', header: 'Reason' },
      { field: 'terminal', header: 'Terminal' },
    ],
    data: [],
  },

  // ── Tile 8: Operator Compliance ───────────────────────────────────────────
  'operator-compliance-interstate': {
    title: 'Interstate Bus Lines Compliance',
    columns: [
      { field: 'metric', header: 'Metric' },
      { field: 'count', header: 'Count' },
    ],
    data: buildOperatorComplianceDrillData(OPERATOR_COMPLIANCE_ROWS[0]),
  },
  'operator-compliance-bophelong': {
    title: 'Bophelong Transport Compliance',
    columns: [
      { field: 'metric', header: 'Metric' },
      { field: 'count', header: 'Count' },
    ],
    data: buildOperatorComplianceDrillData(OPERATOR_COMPLIANCE_ROWS[1]),
  },
  'compliant-operators': {
    title: 'Compliant Operators',
    columns: [
      { field: 'operator', header: 'Operator' },
      { field: 'inspections', header: 'Inspections' },
      { field: 'violations', header: 'Violations' },
      { field: 'kpiScore', header: 'KPI Score' },
      { field: 'compliancePct', header: 'Compliance %' },
      { field: 'rank', header: 'Rank' },
    ],
    data: [
      {
        operator: 'Interstate Bus Lines',
        inspections: 85,
        violations: 1,
        kpiScore: 97,
        compliancePct: '98.8%',
        rank: 1,
      },
      {
        operator: 'Free State Express',
        inspections: 72,
        violations: 2,
        kpiScore: 94,
        compliancePct: '97.2%',
        rank: 2,
      },
      {
        operator: 'Bophelong Transport',
        inspections: 60,
        violations: 0,
        kpiScore: 100,
        compliancePct: '100%',
        rank: 3,
      },
      {
        operator: 'Mangaung City Bus',
        inspections: 95,
        violations: 3,
        kpiScore: 91,
        compliancePct: '96.8%',
        rank: 4,
      },
      {
        operator: 'Motheo Bus Service',
        inspections: 48,
        violations: 1,
        kpiScore: 96,
        compliancePct: '97.9%',
        rank: 5,
      },
      {
        operator: 'Welkom Transport Co',
        inspections: 55,
        violations: 2,
        kpiScore: 93,
        compliancePct: '96.4%',
        rank: 6,
      },
    ],
  },
  'non-compliant-operators': {
    title: 'Non-Compliant Operators',
    columns: [
      { field: 'operator', header: 'Operator' },
      { field: 'inspections', header: 'Inspections' },
      { field: 'violations', header: 'Violations' },
      { field: 'kpiScore', header: 'KPI Score' },
      { field: 'compliancePct', header: 'Compliance %' },
      { field: 'reason', header: 'Non-Compliance Reason' },
    ],
    data: [
      {
        operator: 'SA Roadlink FS',
        inspections: 40,
        violations: 8,
        kpiScore: 73,
        compliancePct: '80.0%',
        reason: 'Multiple roadworthiness failures',
      },
    ],
  },

  // ── Tile 9: Photo Evidence ────────────────────────────────────────────────
  'critical-defects-photo': {
    title: 'Critical Defects – Photo Evidence',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'defectType', header: 'Defect Type' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
      { field: 'gps', header: 'GPS' },
      { field: 'photoRef', header: 'Photo Ref' },
    ],
    data: [
      {
        busReg: 'FSB110FS',
        fleetNo: '1010',
        defectType: 'Faulty Brakes',
        inspector: 'Mark Nkosi',
        date: '2026-06-11',
        gps: '-29.1187, 26.2145',
        photoRef: 'IMG-2026-0611-001',
      },
      {
        busReg: 'FSB220FS',
        fleetNo: '1021',
        defectType: 'Tyre Burst',
        inspector: 'Anne Dlamini',
        date: '2026-06-11',
        gps: '-27.9874, 26.7343',
        photoRef: 'IMG-2026-0611-002',
      },
      {
        busReg: 'FSB330FS',
        fleetNo: '1032',
        defectType: 'Fire Extinguisher Missing',
        inspector: 'Paul Sithole',
        date: '2026-06-10',
        gps: '-29.3200, 26.8420',
        photoRef: 'IMG-2026-0610-003',
      },
      {
        busReg: 'FSB440FS',
        fleetNo: '1043',
        defectType: 'Emergency Exit Blocked',
        inspector: 'John Smith',
        date: '2026-06-10',
        gps: '-29.2645, 26.7150',
        photoRef: 'IMG-2026-0610-004',
      },
      {
        busReg: 'FSB550FS',
        fleetNo: '1054',
        defectType: 'Cracked Windscreen',
        inspector: 'Jane Doe',
        date: '2026-06-09',
        gps: '-29.1190, 26.2148',
        photoRef: 'IMG-2026-0609-005',
      },
    ],
  },
  'minor-defects-photo': {
    title: 'Minor Defects – Photo Evidence',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'defectType', header: 'Defect Type' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'date', header: 'Date' },
      { field: 'gps', header: 'GPS' },
      { field: 'photoRef', header: 'Photo Ref' },
    ],
    data: [
      {
        busReg: 'FSB660FS',
        fleetNo: '1065',
        defectType: 'Torn Seat',
        inspector: 'James Nkosi',
        date: '2026-06-11',
        gps: '-29.1187, 26.2145',
        photoRef: 'IMG-2026-0611-006',
      },
      {
        busReg: 'FSB770FS',
        fleetNo: '1076',
        defectType: 'Graffiti on Interior',
        inspector: 'Sarah Mokoena',
        date: '2026-06-11',
        gps: '-27.9874, 26.7343',
        photoRef: 'IMG-2026-0611-007',
      },
      {
        busReg: 'FSB880FS',
        fleetNo: '1087',
        defectType: 'Broken Window Handle',
        inspector: 'Peter Dlamini',
        date: '2026-06-10',
        gps: '-29.3200, 26.8420',
        photoRef: 'IMG-2026-0610-008',
      },
      {
        busReg: 'FSB990FS',
        fleetNo: '1098',
        defectType: 'Loose Seat Bolt',
        inspector: 'Tom Leballo',
        date: '2026-06-10',
        gps: '-29.2645, 26.7150',
        photoRef: 'IMG-2026-0610-009',
      },
      {
        busReg: 'FSB112FS',
        fleetNo: '1109',
        defectType: 'Dirty Interior',
        inspector: 'Mary Sithole',
        date: '2026-06-09',
        gps: '-29.1190, 26.2148',
        photoRef: 'IMG-2026-0609-010',
      },
    ],
  },
};

const FAILED_INSPECTION_TYPES = [
  {
    label: 'External Inspections',
    drillKey: 'failed-external-inspections',
    sourceKey: 'external-inspections',
  },
  {
    label: 'Internal Inspections',
    drillKey: 'failed-internal-inspections',
    sourceKey: 'internal-inspections',
  },
  {
    label: 'Driver Inspections',
    drillKey: 'failed-driver-inspections',
    sourceKey: 'driver-inspections',
  },
  {
    label: 'Passenger Counts',
    drillKey: 'failed-passenger-counts',
    sourceKey: 'passenger-counts-drill',
  },
  {
    label: 'Technical Inspections',
    drillKey: 'failed-technical-inspections',
    sourceKey: 'technical-inspections',
  },
];

for (const type of FAILED_INSPECTION_TYPES) {
  const source = DRILL_CONFIGS[type.sourceKey];
  DRILL_CONFIGS[type.drillKey] = {
    title: `Failed ${type.label}`,
    columns: source.columns,
    data: source.data.filter((row) => isFailedInspectionTypeRow(type.sourceKey, row)),
  };
}

const FAILED_INSPECTION_SUMMARY_ITEMS: SummaryItem[] = [
  ...FAILED_INSPECTION_TYPES.map((type) => ({
    label: type.label,
    value: DRILL_CONFIGS[type.drillKey].data.length,
    drillKey: type.drillKey,
  })),
  {
    label: 'Total Failed Inspections',
    value: FAILED_INSPECTION_TYPES.reduce(
      (total, type) => total + DRILL_CONFIGS[type.drillKey].data.length,
      0,
    ),
    drillKey: null,
  },
];

// ─── KPI Tiles (original document order) ─────────────────────────────────────

const TILES: KpiTile[] = [
  {
    id: 'daily-monitoring',
    title: 'Daily Bus Monitoring',
    metric: 'Total Completed Inspections',
    value: 32,
    status: 'good',
    icon: 'pi pi-check-circle',
    summaryItems: [
      { label: 'External Inspections', value: 6, drillKey: 'external-inspections' },
      { label: 'Internal Inspections', value: 6, drillKey: 'internal-inspections' },
      { label: 'Driver Inspections', value: 5, drillKey: 'driver-inspections' },
      { label: 'Passenger Counts', value: 8, drillKey: 'passenger-counts-drill' },
      { label: 'Technical Inspections', value: 4, drillKey: 'technical-inspections' },
      { label: 'Total Inspections', value: 29, drillKey: null },
    ],
  },
  {
    id: 'route-exceptions',
    title: 'Route Compliance',
    metric: 'Route Exceptions',
    value: 10,
    status: 'warning',
    icon: 'pi pi-map',
    summaryItems: [
      { label: 'Missed Stops', value: 4, drillKey: 'missed-stops' },
      { label: 'Route Deviations', value: 6, drillKey: 'route-deviation-events' },
      { label: 'Total Exceptions', value: 10, drillKey: null },
    ],
  },
  {
    id: 'compliance-violations',
    title: 'Driver & Bus Compliance',
    metric: 'Compliance Violations',
    value: 8,
    status: 'critical',
    icon: 'pi pi-exclamation-triangle',
    summaryItems: [
      { label: 'Expired PDP', value: 3, drillKey: 'expired-pdp' },
      { label: 'Expired Driver Licence', value: 2, drillKey: 'expired-driver-licence' },
      { label: 'Expired Route Licence', value: 1, drillKey: 'expired-route-licence' },
      { label: 'Expired Bus Licence Disk', value: 2, drillKey: 'expired-bus-license-disk' },
      { label: 'Total Violations', value: 8, drillKey: null },
    ],
  },
  {
    id: 'bus-defects',
    title: 'Bus Defects',
    metric: 'Total Bus Defects',
    value: 18,
    status: 'critical',
    icon: 'pi pi-exclamation-circle',
    summaryItems: [
      { label: 'Fire Extinguisher', value: 2, drillKey: 'fire-extinguisher-defects' },
      { label: 'Seats', value: 4, drillKey: 'seat-defects' },
      { label: 'Aisle', value: 2, drillKey: 'aisle-obstructions' },
      { label: 'Tyres', value: 2, drillKey: 'tyre-defects' },
      { label: 'Windows', value: 2, drillKey: 'window-defects' },
      { label: 'Other', value: 2, drillKey: 'other-defects' },
      { label: 'Technical', value: 4, drillKey: 'technical-inspections' },
      { label: 'Total Defects', value: 18, drillKey: null },
    ],
  },
  {
    id: 'overloaded-trips',
    title: 'Passenger Count',
    metric: 'Passenger Count',
    value: 8,
    status: 'good',
    icon: 'pi pi-users',
    summaryItems: [
      { label: 'Passenger Count', value: 8, drillKey: 'passenger-counts-drill' },
      { label: 'Total', value: 8, drillKey: null },
    ],
  },
  {
    id: 'delayed-departures',
    title: 'Schedule Adherence',
    metric: 'Delayed Departures',
    value: 12,
    status: 'warning',
    icon: 'pi pi-clock',
    summaryItems: [
      { label: 'Behind Schedule (0–5 mins)', value: 0, drillKey: 'behind-schedule-0-5' },
      { label: 'Behind Schedule (5–10 mins)', value: 3, drillKey: 'behind-schedule-5-10' },
      { label: 'Behind Schedule (10–15 mins)', value: 4, drillKey: 'behind-schedule-10-15' },
      { label: 'Behind Schedule (15+ mins)', value: 5, drillKey: 'behind-schedule-15-plus' },
      { label: 'Total Delayed', value: 12, drillKey: null },
    ],
  },
  {
    id: 'service-reliability',
    title: 'Service Reliability',
    metric: 'On-Time Performance',
    value: '96.4%',
    status: 'good',
    icon: 'pi pi-chart-line',
    summaryItems: [
      { label: 'Delayed Starts (0-5 mins)', value: 0, drillKey: 'behind-schedule-0-5' },
      { label: 'Delayed Starts (5-10 mins)', value: 1, drillKey: 'behind-schedule-5-10' },
      { label: 'Delayed Starts (10-15 mins)', value: 1, drillKey: 'behind-schedule-10-15' },
      { label: 'Delayed Starts (15+ mins)', value: 1, drillKey: 'behind-schedule-15-plus' },
      { label: 'Total Delayed Route Starts', value: 3, drillKey: null },
    ],
  },
  {
    id: 'operator-compliance',
    title: 'Monthly Contract Compliance',
    metric: 'Operator Compliance Score',
    value: '88.7%',
    status: 'warning',
    icon: 'pi pi-building',
    summaryItems: OPERATOR_COMPLIANCE_SUMMARY_ITEMS,
  },
  {
    id: 'photo-evidence',
    title: 'Failed Inspections',
    metric: 'Failed Inspections by Type',
    value: 15,
    status: 'critical',
    icon: 'pi pi-clipboard',
    summaryItems: FAILED_INSPECTION_SUMMARY_ITEMS,
  },
  {
    id: 'fleet-health',
    title: 'Fleet Health',
    metric: 'Overall Analytics Score',
    value: TOP_KPI_DUMMY_VALUES['fleet-health'],
    status: 'good',
    icon: 'pi pi-wave-pulse',
    summaryItems: FLEET_HEALTH_SUMMARY_ITEMS,
  },
];

// ─── Component ────────────────────────────────────────────────────────────────

@Component({
  selector: 'app-reporting',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AvatarModule,
    ButtonModule,
    CardModule,
    DatePickerModule,
    DialogModule,
    DividerModule,
    FloatLabelModule,
    DrawerModule,
    IconFieldModule,
    InputIconModule,
    InputTextModule,
    MenuModule,
    MultiSelectModule,
    NgxEchartsDirective,
    SelectModule,
    TableModule,
    TagModule,
    ToolbarModule,
    TooltipModule,
  ],
  templateUrl: './reporting.component.html',
  styleUrl: './reporting.component.css',
})
export class ReportingComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly analyticsApi = inject(AnalyticsService);

  readonly session = this.auth.session;
  readonly reportTiles = signal<KpiTile[]>([]);
  readonly reportDrilldowns = signal<Record<string, DrillConfig>>({});
  readonly reportError = signal<string | null>(null);
  readonly topKpiApiValues = signal<Record<string, TopKpiApiValue>>({});
  readonly topKpiError = signal<string | null>(null);
  menuVisible = true;
  readonly navigationItems: MenuItem[] = [
    {
      label: 'Reports',
      icon: 'pi pi-chart-bar',
      styleClass: 'nav-item-active',
      command: () => this.openReporting(),
    },
    {
      label: 'Live Map',
      icon: 'pi pi-map',
      command: () => this.openSmartFleet(),
    },
    {
      label: 'Analytics',
      icon: 'pi pi-chart-line',
      command: () => this.openAnalytics(),
    },
    {
      label: 'Vehicles',
      icon: 'pi pi-car',
      command: () => this.openVehicles(),
    },
    {
      label: 'Inspections',
      icon: 'pi pi-search',
      command: () => this.openInspections(),
    },
    {
      label: 'Shifts',
      icon: 'pi pi-calendar',
      command: () => this.openShifts(),
    },
  ];

  // ── Tiles grouped by dashboard row (reactive to applied filters) ──────────
  readonly filteredTiles = computed(() => {
    const apiTiles = this.reportTiles();
    if (apiTiles.length > 0) return apiTiles;

    return TILES.map((tile): KpiTile => ({
      ...tile,
      value: 'Loading',
      summaryItems: tile.summaryItems.map((item) => ({ ...item, value: 0 })),
    }));
  });

  readonly filteredRow1 = computed(() => this.filteredTiles().slice(6, 10));
  readonly filteredRow2 = computed(() => this.filteredTiles().slice(0, 3));
  readonly filteredRow3 = computed(() => this.filteredTiles().slice(3, 6));

  readonly failedInspectionsPercentage = computed(() => {
    const f = this.appliedFilters();
    const inspectionRows = INSPECTION_DRILL_KEYS.flatMap((key) => filterRecordsForKey(key, f));
    if (inspectionRows.length === 0) return 'N/A';
    const failedRows = inspectionRows.filter(hasFailedInspectionValue).length;
    return `${((failedRows / inspectionRows.length) * 100).toFixed(1)}%`;
  });

  readonly topKpiRow = computed<KpiTile[]>(() => {
    const [onTimeTile, routeComplianceTile, failedTile, fleetHealthTile] = this.filteredRow1();
    const apiValues = this.topKpiApiValues();
    const onTimeApi = apiValues[onTimeTile.id];
    const routeComplianceApi = apiValues[routeComplianceTile.id];
    const failedApi = apiValues[failedTile.id];
    const fleetHealthApi = apiValues[fleetHealthTile.id];

    return [
      {
        ...onTimeTile,
        title: 'On Time Performance',
        metric: 'On Time Performance',
        value: onTimeApi?.value ?? 'Loading',
        secondaryText: onTimeApi?.secondaryText,
        status: onTimeApi?.status ?? onTimeTile.status,
        icon: 'pi pi-stopwatch',
        summaryItems: onTimeApi?.summaryItems ?? onTimeTile.summaryItems,
      },
      {
        ...routeComplianceTile,
        title: 'Route Compliance',
        metric: 'Route Compliance',
        value: routeComplianceApi?.value ?? 'Loading',
        secondaryText: routeComplianceApi?.secondaryText,
        status: routeComplianceApi?.status ?? routeComplianceTile.status,
        icon: 'pi pi-map',
        summaryItems: routeComplianceApi?.summaryItems ?? routeComplianceTile.summaryItems,
      },
      {
        ...failedTile,
        title: 'Failed Inspections',
        metric: 'Failed Inspections',
        value: failedApi?.value ?? 'Loading',
        secondaryText: failedApi?.secondaryText,
        status: failedApi?.status ?? failedTile.status,
        icon: 'pi pi-clipboard',
        summaryItems: failedApi?.summaryItems ?? failedTile.summaryItems,
      },
      {
        ...fleetHealthTile,
        title: 'Fleet Health',
        metric: 'Fleet Health',
        value: fleetHealthApi?.value ?? 'Loading',
        secondaryText: fleetHealthApi?.secondaryText,
        status: fleetHealthApi?.status ?? fleetHealthTile.status,
        icon: 'pi pi-wave-pulse',
        summaryItems: fleetHealthApi?.summaryItems ?? fleetHealthTile.summaryItems,
      },
    ];
  });

  readonly topKpiCounts = computed(() => {
    const f = this.appliedFilters();
    const onTimeRows = filterRecordsForKey('on-time', f);
    const onTimeTotal = onTimeRows.reduce((sum, row) => sum + Number(row['total'] ?? 0), 0);
    const onTimeCount = onTimeRows.reduce((sum, row) => sum + Number(row['onTime'] ?? 0), 0);

    const routeExceptionCount =
      filterRecordsForKey('missed-stops', f).length +
      filterRecordsForKey('route-deviation-events', f).length;
    const routeCompliantCount = Math.max(onTimeTotal - routeExceptionCount, 0);

    const inspectionRows = INSPECTION_DRILL_KEYS.flatMap((key) => filterRecordsForKey(key, f));
    const failedInspectionCount = inspectionRows.filter(hasFailedInspectionValue).length;

    return {
      onTime: `${onTimeCount}/${onTimeTotal}`,
      routeCompliance: `${routeCompliantCount}/${onTimeTotal}`,
      failedInspections: `${failedInspectionCount}/${inspectionRows.length}`,
    };
  });

  // ── Global filters – draft (bound to form controls) ──────────────────────
  draftDateRange: Date[] = [this.defaultDateFrom(), new Date()];
  draftOperator = 'all';
  draftTerminals: string[] = [];
  draftRoutes: string[] = [];

  // ── Applied filters (committed on Apply click) ────────────────────────────
  readonly appliedFilters = signal<AppliedFilters>({
    dateFrom: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
    dateTo: new Date(),
    operators: [],
    terminals: [],
    routes: [],
  });

  readonly activeFilterCount = computed(() => {
    const f = this.appliedFilters();
    return (
      (f.operators.length > 0 ? 1 : 0) +
      (f.terminals.length > 0 ? 1 : 0) +
      (f.routes.length > 0 ? 1 : 0)
    );
  });

  readonly operatorOptions = [
    { label: 'All Operators', value: 'all' },
    { label: 'Interstate Bus Lines', value: 'interstate' },
    { label: 'Free State Express', value: 'fse' },
    { label: 'Bophelong Transport', value: 'bophelong' },
    { label: 'Mangaung City Bus', value: 'mangaung' },
    { label: 'Motheo Bus Service', value: 'motheo' },
    { label: 'Welkom Transport Co', value: 'welkom' },
    { label: 'SA Roadlink FS', value: 'saroadlink' },
  ];

  readonly operators = [
    { label: 'Interstate Bus Lines', value: 'interstate' },
    { label: 'Free State Express', value: 'fse' },
    { label: 'Bophelong Transport', value: 'bophelong' },
    { label: 'Mangaung City Bus', value: 'mangaung' },
    { label: 'Motheo Bus Service', value: 'motheo' },
    { label: 'Welkom Transport Co', value: 'welkom' },
    { label: 'SA Roadlink FS', value: 'saroadlink' },
  ];

  readonly terminals = [
    { label: 'Bloemfontein', value: 'bfn' },
    { label: 'Welkom', value: 'welkom' },
    { label: 'Botshabelo', value: 'botshabelo' },
    { label: 'Thaba Nchu', value: 'thabaNchu' },
  ];

  readonly routes = [
    { label: 'R03', value: 'r03' },
    { label: 'R04', value: 'r04' },
    { label: 'R05', value: 'r05' },
    { label: 'R07', value: 'r07' },
    { label: 'R08', value: 'r08' },
    { label: 'R11', value: 'r11' },
    { label: 'R12', value: 'r12' },
    { label: 'R14', value: 'r14' },
    { label: 'R15', value: 'r15' },
    { label: 'R16', value: 'r16' },
    { label: 'R18', value: 'r18' },
    { label: 'R19', value: 'r19' },
    { label: 'R22', value: 'r22' },
    { label: 'R23', value: 'r23' },
    { label: 'R26', value: 'r26' },
    { label: 'R30', value: 'r30' },
  ];

  // ── Inline tile panel state ──────────────────────────────────────────────
  readonly activeTileId = signal<string | null>(null);

  readonly activeTile = computed<KpiTile | null>(() => {
    const id = this.activeTileId();
    if (!id) return null;
    const topKpiTile = this.topKpiRow().find((tile) => tile.id === id);
    if (topKpiTile) return topKpiTile;
    return this.filteredTiles().find((t) => t.id === id) ?? null;
  });

  /** 1, 2, or 3 – which dashboard row contains the active tile */
  readonly activeTileRow = computed<number | null>(() => {
    const id = this.activeTileId();
    if (!id) return null;
    if (this.filteredRow1().some((tile) => tile.id === id)) return 1;
    if (this.filteredRow2().some((tile) => tile.id === id)) return 2;
    if (this.filteredRow3().some((tile) => tile.id === id)) return 3;
    return null;
  });

  ngOnInit(): void {
    this.loadTopKpis();
    this.loadReportingSummary();
  }

  readonly tileBarChartOptions = computed<EChartsOption | null>(() => {
    const tile = this.activeTile();
    if (!tile) return null;

    const drillable = tile.summaryItems.filter((i) => i.drillKey !== null);
    const categories = drillable.map((i) => i.label);
    const totals = drillable.map((i) =>
      typeof i.value === 'number' ? i.value : parseFloat(String(i.value)) || 0,
    );
    if (categories.length === 0) return null;

    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: {
        top: 0,
        left: 0,
        textStyle: { fontSize: 10 },
      },
      grid: { left: 8, right: 46, bottom: 12, top: 34, containLabel: true },
      xAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { fontSize: 11 },
      },
      yAxis: {
        type: 'category',
        data: categories,
        inverse: true,
        axisLabel: {
          fontSize: 11,
          interval: 0,
          width: 135,
          overflow: 'break',
          lineHeight: 14,
        },
      },
      series: [
        {
          name: 'Total',
          type: 'bar',
          data: totals,
          itemStyle: { color: '#1d4ed8' },
          label: { show: true, position: 'right', fontSize: 12, fontWeight: 'bold' },
          barMaxWidth: 28,
        },
      ],
    };
  });

  readonly inspectionTrendChartOptions = computed<EChartsOption | null>(() => {
    const tile = this.activeTile();
    if (tile?.id !== 'daily-monitoring' && tile?.id !== 'service-reliability') return null;

    const chartData =
      tile.id === 'service-reliability'
        ? this.topKpiApiValues()['service-reliability']?.trendData
        : tile.trendData;

    if (!chartData || chartData.dates.length === 0) return null;

    return {
      color:
        tile.id === 'service-reliability'
          ? ['#dc2626', '#d97706']
          : ['#1d4ed8', '#16a34a', '#d97706', '#7c3aed', '#dc2626'],
      tooltip: { trigger: 'axis' },
      legend: {
        type: 'scroll',
        top: 0,
        left: 0,
        right: 0,
        textStyle: { fontSize: 10 },
      },
      grid: { left: 8, right: 16, bottom: 12, top: 42, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: chartData.dates,
        axisLabel: {
          fontSize: 10,
          interval: 0,
          formatter: (value: string) => value.slice(5),
        },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { fontSize: 11 },
      },
      series: chartData.series.map((item) => ({
        name: item.name,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: item.data,
      })),
    };
  });

  readonly secondaryLineChartLabel = computed(() =>
    this.activeTile()?.id === 'service-reliability'
      ? 'Delayed Route Starts Over Time'
      : 'Inspection Type Over Time',
  );

  readonly tilePieChartOptions = computed<EChartsOption | null>(() => {
    const tile = this.activeTile();
    if (!tile) return null;

    const drillable = tile.summaryItems.filter(
      (i) =>
        i.drillKey !== null &&
        (typeof i.value === 'number' ? i.value : parseFloat(String(i.value)) || 0) > 0,
    );
    if (drillable.length === 0) return null;
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', left: '58%', top: 'middle', textStyle: { fontSize: 11 } },
      series: [
        {
          type: 'pie',
          radius: ['40%', '68%'],
          center: ['28%', '50%'],
          data: drillable.map((i) => ({
            name: i.label,
            value: typeof i.value === 'number' ? i.value : parseFloat(String(i.value)) || 0,
          })),
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
        },
      ],
    };
  });

  // ── Drill-down modal state ────────────────────────────────────────────────
  readonly showDrillModal = signal(false);
  readonly activeDetailKey = signal<string | null>(null);
  readonly searchQuery = signal('');
  readonly selectedGpsCoords = signal<string | null>(null);

  readonly activeDetail = computed<DrillConfig | null>(() => {
    const key = this.activeDetailKey();
    if (!key) return null;
    return this.reportDrilldowns()[key] ?? this.emptyDrilldown(key);
  });

  readonly drillHasGps = computed(() => {
    const detail = this.activeDetail();
    if (!detail) return false;
    return detail.columns.some((c) => c.field === 'gps');
  });

  readonly gpsMapUrl = computed<SafeResourceUrl | null>(() => {
    const coords = this.selectedGpsCoords();
    if (!coords) return null;
    const parts = coords.split(',').map((s) => s.trim());
    if (parts.length < 2) return null;
    const lat = parseFloat(parts[0]);
    const lon = parseFloat(parts[1]);
    if (isNaN(lat) || isNaN(lon)) return null;
    const d = 0.008;
    const url =
      `https://www.openstreetmap.org/export/embed.html` +
      `?bbox=${lon - d},${lat - d},${lon + d},${lat + d}` +
      `&layer=mapnik&marker=${lat},${lon}`;
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  });

  readonly filteredData = computed(() => {
    const detail = this.activeDetail();
    if (!detail) return [];

    const q = this.searchQuery().toLowerCase().trim();
    const {
      operators: ops,
      terminals: terms,
      routes: rts,
      dateFrom,
      dateTo,
    } = this.appliedFilters();
    const dtFrom = new Date(dateFrom);
    dtFrom.setHours(0, 0, 0, 0);
    const dtTo = new Date(dateTo);
    dtTo.setHours(23, 59, 59, 999);

    return detail.data.map(enrichRecord).filter((row) => {
      if (q) {
        const hit = Object.entries(row)
          .filter(([k]) => !k.startsWith('_'))
          .some(([, v]) => String(v).toLowerCase().includes(q));
        if (!hit) return false;
      }
      if (ops.length > 0 && !ops.includes(String(row['_operator']))) return false;
      if (terms.length > 0 && !terms.includes(String(row['_terminal']))) return false;
      if (rts.length > 0 && !rts.includes(String(row['_route']))) return false;
      const d = new Date(String(row['_date']));
      if (!isNaN(d.getTime()) && (d < dtFrom || d > dtTo)) return false;
      return true;
    });
  });

  // ── Navigation ─────────────────────────────────────────────────────────────
  openTile(tile: KpiTile): void {
    // Toggle: clicking the same tile closes the panel
    if (this.activeTileId() === tile.id) {
      this.activeTileId.set(null);
    } else {
      this.activeTileId.set(tile.id);
    }
  }

  closeTilePanel(): void {
    this.activeTileId.set(null);
  }

  openDrill(item: SummaryItem): void {
    if (!item.drillKey) return;
    this.activeDetailKey.set(item.drillKey);
    this.searchQuery.set('');
    this.selectedGpsCoords.set(null);
    this.showDrillModal.set(true);
  }

  onDrillModalVisible(visible: boolean): void {
    if (!visible) {
      this.showDrillModal.set(false);
      this.activeDetailKey.set(null);
      this.selectedGpsCoords.set(null);
    }
  }

  selectGpsRow(row: Record<string, string | number>): void {
    const gps = String(row['gps'] ?? '');
    if (!gps) return;
    this.selectedGpsCoords.set(this.selectedGpsCoords() === gps ? null : gps);
  }

  // ── Status helpers ─────────────────────────────────────────────────────────
  statusSeverity(status: TileStatus): 'success' | 'warn' | 'danger' {
    return status === 'good' ? 'success' : status === 'warning' ? 'warn' : 'danger';
  }

  statusLabel(status: TileStatus): string {
    return status === 'good' ? 'Good' : status === 'warning' ? 'Warning' : 'Critical';
  }

  // ── Export ─────────────────────────────────────────────────────────────────
  exportCsv(): void {
    const detail = this.activeDetail();
    if (!detail) return;
    const cols = detail.columns;
    const header = cols.map((c) => `"${c.header}"`).join(',');
    const body = this.filteredData()
      .map((row) =>
        cols.map((c) => `"${String(row[c.field] ?? '').replace(/"/g, '""')}"`).join(','),
      )
      .join('\n');
    this.downloadFile(`${header}\n${body}`, `${detail.title}.csv`, 'text/csv');
  }

  exportExcel(): void {
    const detail = this.activeDetail();
    if (!detail) return;
    const cols = detail.columns;
    const header = cols.map((c) => c.header).join('\t');
    const body = this.filteredData()
      .map((row) => cols.map((c) => String(row[c.field] ?? '')).join('\t'))
      .join('\n');
    this.downloadFile(`${header}\n${body}`, `${detail.title}.xls`, 'application/vnd.ms-excel');
  }

  exportPdf(): void {
    window.print();
  }

  private downloadFile(content: string, filename: string, mimeType: string): void {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Filters ────────────────────────────────────────────────────────────────
  applyFilters(): void {
    const [dateFrom, dateTo] = this.normalizedDraftDateRange();
    this.appliedFilters.set({
      dateFrom,
      dateTo,
      operators: this.draftOperator === 'all' ? [] : [this.draftOperator],
      terminals: [...this.draftTerminals],
      routes: [...this.draftRoutes],
    });
    this.loadTopKpis({ dateFrom, dateTo });
    this.loadReportingSummary({ dateFrom, dateTo });
  }

  resetFilters(): void {
    const defaultFrom = this.defaultDateFrom();
    const defaultTo = new Date();
    this.draftDateRange = [defaultFrom, defaultTo];
    this.draftOperator = 'all';
    this.draftTerminals = [];
    this.draftRoutes = [];
    this.appliedFilters.set({
      dateFrom: defaultFrom,
      dateTo: defaultTo,
      operators: [],
      terminals: [],
      routes: [],
    });
    this.loadTopKpis({ dateFrom: defaultFrom, dateTo: defaultTo });
    this.loadReportingSummary({ dateFrom: defaultFrom, dateTo: defaultTo });
  }

  private loadReportingSummary(
    range: Pick<AppliedFilters, 'dateFrom' | 'dateTo'> = this.appliedFilters(),
  ): void {
    this.reportError.set(null);
    this.analyticsApi
      .getReportingSummary(
        {
          startDate: this.formatApiDate(range.dateFrom),
          endDate: this.formatApiDate(range.dateTo),
        },
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (summary) => this.applyReportingSummary(summary),
        error: (err) => {
          this.reportError.set(err?.error?.detail ?? 'Could not load reporting summary.');
          this.reportTiles.set([]);
          this.reportDrilldowns.set({});
        },
      });
  }

  private loadTopKpis(range: Pick<AppliedFilters, 'dateFrom' | 'dateTo'> = this.appliedFilters()): void {
    this.topKpiError.set(null);
    this.analyticsApi
      .getAnalyticsSummary(
        {
          startDate: this.formatApiDate(range.dateFrom),
          endDate: this.formatApiDate(range.dateTo),
        },
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (summary) => {
          this.topKpiApiValues.set(this.mapTopKpis(summary.top_kpis ?? []));
        },
        error: (err) => {
          this.topKpiError.set(err?.error?.detail ?? 'Could not load KPI summary.');
        },
      });
  }

  private mapTopKpis(kpis: AnalyticsTopKpiResponse[]): Record<string, TopKpiApiValue> {
    return kpis.reduce<Record<string, TopKpiApiValue>>((mapped, kpi) => {
      mapped[kpi.id] = {
        value: kpi.value,
        secondaryText: kpi.secondary_text ?? undefined,
        status: this.asTileStatus(kpi.status),
        summaryItems: (kpi.summary_items ?? []).map((item) => ({
          label: item.label,
          value: this.coerceSummaryValue(item.value),
          drillKey: item.drill_key ?? null,
        })),
        trendData: kpi.trend
          ? {
              dates: kpi.trend.dates ?? [],
              series: (kpi.trend.series ?? []).map((series) => ({
                name: series.name,
                data: series.data ?? [],
              })),
            }
          : undefined,
      };
      return mapped;
    }, {});
  }

  private applyReportingSummary(summary: AnalyticsReportingSummaryResponse): void {
    this.reportTiles.set((summary.tiles ?? []).map((tile) => this.mapReportingTile(tile)));
    this.reportDrilldowns.set(this.mapDrilldowns(summary.drilldowns ?? {}));
  }

  private mapReportingTile(tile: AnalyticsReportingTileResponse): KpiTile {
    return {
      id: tile.id,
      title: tile.title,
      metric: tile.metric,
      value: this.coerceSummaryValue(tile.value),
      status: this.asTileStatus(tile.status) ?? 'good',
      icon: tile.icon,
      summaryItems: (tile.summary_items ?? []).map((item) => ({
        label: item.label,
        value: this.coerceSummaryValue(item.value),
        drillKey: item.drill_key ?? null,
      })),
      trendData: tile.trend
        ? {
            dates: tile.trend.dates ?? [],
            series: (tile.trend.series ?? []).map((series) => ({
              name: series.name,
              data: series.data ?? [],
            })),
          }
        : undefined,
    };
  }

  private mapDrilldowns(
    drilldowns: Record<string, AnalyticsDrilldownResponse>,
  ): Record<string, DrillConfig> {
    return Object.entries(drilldowns).reduce<Record<string, DrillConfig>>((mapped, [key, value]) => {
      mapped[key] = {
        title: value.title,
        columns: (value.columns ?? []).map((column) => ({
          field: column.field,
          header: column.header,
        })),
        data: (value.data ?? []).map((row) => row as Record<string, string | number>),
      };
      return mapped;
    }, {});
  }

  private emptyDrilldown(key: string): DrillConfig {
    const title = key
      .split('-')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
    return {
      title,
      columns: [{ field: 'message', header: 'Status' }],
      data: [],
    };
  }

  private asTileStatus(status: string | null | undefined): TileStatus | undefined {
    if (status === 'good' || status === 'warning' || status === 'critical') {
      return status;
    }
    return undefined;
  }

  private coerceSummaryValue(value: unknown): string | number {
    if (typeof value === 'number' || typeof value === 'string') {
      return value;
    }
    return 0;
  }

  private formatApiDate(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private defaultDateFrom(): Date {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  }

  private normalizedDraftDateRange(): [Date, Date] {
    const [from, to] = this.draftDateRange ?? [];
    const dateFrom = from ? new Date(from) : this.defaultDateFrom();
    const dateTo = to ? new Date(to) : new Date(dateFrom);
    return dateFrom <= dateTo ? [dateFrom, dateTo] : [dateTo, dateFrom];
  }

  // ── Auth ───────────────────────────────────────────────────────────────────
  toggleMenu(): void {
    this.menuVisible = !this.menuVisible;
  }

  closeMenu(): void {
    this.menuVisible = false;
  }

  openVehicles(): void {
    this.menuVisible = false;
    this.router.navigate(['/vehicles']);
  }

  openSmartFleet(): void {
    this.menuVisible = false;
    this.router.navigate(['/smart-fleet']);
  }

  openAnalytics(): void {
    this.menuVisible = false;
    this.router.navigate(['/analytics']);
  }

  openInspections(): void {
    this.menuVisible = false;
    this.router.navigate(['/inspections']);
  }

  openShifts(): void {
    this.menuVisible = false;
    this.router.navigate(['/shifts']);
  }

  openReporting(): void {
    this.menuVisible = false;
    this.router.navigate(['/reporting']);
  }

  logout(): void {
    this.auth.logout();
  }
}
