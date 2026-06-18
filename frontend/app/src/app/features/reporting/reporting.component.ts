import { Component, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import type { EChartsOption } from 'echarts';
import { NgxEchartsDirective } from 'ngx-echarts';

import { AuthService } from '../../core/services/auth.service';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { DividerModule } from 'primeng/divider';
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
  status: TileStatus;
  icon: string;
  summaryItems: SummaryItem[];
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
  incomplete: {
    title: 'Incomplete Inspections',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'inspector', header: 'Inspector' },
      { field: 'terminal', header: 'Terminal' },
      { field: 'scheduledTime', header: 'Scheduled' },
      { field: 'reason', header: 'Reason' },
      { field: 'status', header: 'Status' },
    ],
    data: [
      {
        busReg: 'FSB111FS',
        fleetNo: '1099',
        inspector: 'Tom Leballo',
        terminal: 'Welkom',
        scheduledTime: '07:00',
        reason: 'Inspector absent',
        status: 'Incomplete',
      },
      {
        busReg: 'FSB222FS',
        fleetNo: '1102',
        inspector: 'Unassigned',
        terminal: 'Bloemfontein',
        scheduledTime: '07:30',
        reason: 'Bus late to depot',
        status: 'Incomplete',
      },
      {
        busReg: 'FSB333FS',
        fleetNo: '1115',
        inspector: 'Mary Sithole',
        terminal: 'Botshabelo',
        scheduledTime: '08:00',
        reason: 'Form not submitted',
        status: 'Pending',
      },
    ],
  },

  // ── Tile 2: Route Exceptions ──────────────────────────────────────────────
  'major-deviations': {
    title: 'Major Route Deviations',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'time', header: 'Time' },
      { field: 'exceptionType', header: 'Exception Type' },
      { field: 'deviation', header: 'Deviation (km)' },
    ],
    data: [
      {
        busReg: 'FSB123FS',
        fleetNo: '1024',
        route: 'R12',
        driver: 'John Smith',
        time: '07:14',
        exceptionType: 'Route Deviation',
        deviation: '4.2',
      },
      {
        busReg: 'FSB888FS',
        fleetNo: '1187',
        route: 'R15',
        driver: 'Peter Jones',
        time: '08:33',
        exceptionType: 'Unauthorised Stop',
        deviation: '0.0',
      },
      {
        busReg: 'FSB234FS',
        fleetNo: '1033',
        route: 'R08',
        driver: 'David Motaung',
        time: '09:22',
        exceptionType: 'Route Deviation',
        deviation: '6.7',
      },
      {
        busReg: 'FSB765FS',
        fleetNo: '1066',
        route: 'R22',
        driver: 'Sipho Radebe',
        time: '10:05',
        exceptionType: 'Route Deviation',
        deviation: '3.1',
      },
      {
        busReg: 'FSB432FS',
        fleetNo: '1077',
        route: 'R04',
        driver: 'Andile Molefe',
        time: '11:15',
        exceptionType: 'Route Deviation',
        deviation: '8.4',
      },
    ],
  },
  'minor-deviations': {
    title: 'Minor Route Deviations',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'time', header: 'Time' },
      { field: 'exceptionType', header: 'Exception Type' },
      { field: 'deviation', header: 'Deviation (km)' },
    ],
    data: [
      {
        busReg: 'FSB155FS',
        fleetNo: '1022',
        route: 'R03',
        driver: 'Thabo Khumalo',
        time: '06:55',
        exceptionType: 'Minor Deviation',
        deviation: '0.8',
      },
      {
        busReg: 'FSB266FS',
        fleetNo: '1031',
        route: 'R07',
        driver: 'Nomsa Dlamini',
        time: '07:42',
        exceptionType: 'Minor Deviation',
        deviation: '1.2',
      },
      {
        busReg: 'FSB377FS',
        fleetNo: '1048',
        route: 'R11',
        driver: 'Bongani Mthembu',
        time: '08:18',
        exceptionType: 'Minor Deviation',
        deviation: '0.5',
      },
      {
        busReg: 'FSB488FS',
        fleetNo: '1059',
        route: 'R16',
        driver: 'Zanele Mokoena',
        time: '09:00',
        exceptionType: 'Late Stop',
        deviation: '0.0',
      },
      {
        busReg: 'FSB599FS',
        fleetNo: '1071',
        route: 'R19',
        driver: 'Lucky Sithole',
        time: '09:30',
        exceptionType: 'Minor Deviation',
        deviation: '1.5',
      },
      {
        busReg: 'FSB611FS',
        fleetNo: '1083',
        route: 'R23',
        driver: 'Faith Leballo',
        time: '10:15',
        exceptionType: 'Early Stop',
        deviation: '0.0',
      },
      {
        busReg: 'FSB722FS',
        fleetNo: '1094',
        route: 'R26',
        driver: 'Moses Ntuli',
        time: '11:00',
        exceptionType: 'Minor Deviation',
        deviation: '0.9',
      },
      {
        busReg: 'FSB833FS',
        fleetNo: '1102',
        route: 'R30',
        driver: 'Grace Nkosi',
        time: '11:45',
        exceptionType: 'Minor Deviation',
        deviation: '1.1',
      },
    ],
  },
  'unauthorised-stops': {
    title: 'Unauthorised Stops',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'route', header: 'Route' },
      { field: 'driver', header: 'Driver' },
      { field: 'time', header: 'Time' },
      { field: 'location', header: 'Location' },
      { field: 'duration', header: 'Duration (min)' },
    ],
    data: [
      {
        busReg: 'FSB444FS',
        fleetNo: '1190',
        route: 'R22',
        driver: 'Peter Sithole',
        time: '09:02',
        location: 'N1 Offramp, Brandfort',
        duration: '8',
      },
      {
        busReg: 'FSB555FS',
        fleetNo: '1201',
        route: 'R05',
        driver: 'Jan Booysen',
        time: '10:15',
        location: 'R30 Petrol Station',
        duration: '12',
      },
      {
        busReg: 'FSB666FS',
        fleetNo: '1215',
        route: 'R14',
        driver: 'Kelebogile Mosia',
        time: '11:30',
        location: 'Hospital Taxi Rank',
        duration: '5',
      },
      {
        busReg: 'FSB777FS',
        fleetNo: '1230',
        route: 'R18',
        driver: 'Thuto Maleka',
        time: '12:00',
        location: 'Spar Parking Lot, Welkom',
        duration: '15',
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
  'seat-defects': {
    title: 'Seat Defects',
    columns: [
      { field: 'busReg', header: 'Bus Reg' },
      { field: 'fleetNo', header: 'Fleet No' },
      { field: 'seatNumbers', header: 'Seat Numbers' },
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

// ─── KPI Tiles (original document order) ─────────────────────────────────────

const TILES: KpiTile[] = [
  {
    id: 'daily-monitoring',
    title: 'Daily Bus Monitoring',
    metric: 'Completed Inspections',
    value: 6,
    status: 'good',
    icon: 'pi pi-check-circle',
    summaryItems: [
      { label: 'Completed Inspections', value: 6, drillKey: 'completed' },
      { label: 'Incomplete Inspections', value: 3, drillKey: 'incomplete' },
      { label: 'Total Expected', value: 9, drillKey: null },
    ],
  },
  {
    id: 'route-exceptions',
    title: 'Route Compliance',
    metric: 'Route Exceptions',
    value: 17,
    status: 'warning',
    icon: 'pi pi-map',
    summaryItems: [
      { label: 'Major Deviations', value: 5, drillKey: 'major-deviations' },
      { label: 'Minor Deviations', value: 8, drillKey: 'minor-deviations' },
      { label: 'Unauthorised Stops', value: 4, drillKey: 'unauthorised-stops' },
      { label: 'Total Exceptions', value: 17, drillKey: null },
    ],
  },
  {
    id: 'compliance-violations',
    title: 'Driver & Bus Compliance',
    metric: 'Compliance Violations',
    value: 11,
    status: 'critical',
    icon: 'pi pi-exclamation-triangle',
    summaryItems: [
      { label: 'Expired PDP', value: 3, drillKey: 'expired-pdp' },
      { label: 'Expired Driver Licence', value: 2, drillKey: 'expired-driver-licence' },
      { label: 'Expired Route Licence', value: 1, drillKey: 'expired-route-licence' },
      { label: 'Roadworthiness Failures', value: 5, drillKey: 'roadworthiness' },
      { label: 'Total Violations', value: 11, drillKey: null },
    ],
  },
  {
    id: 'interior-defects',
    title: 'Interior Condition',
    metric: 'Interior Defects',
    value: 8,
    status: 'warning',
    icon: 'pi pi-eye',
    summaryItems: [
      { label: 'Seat Defects', value: 4, drillKey: 'seat-defects' },
      { label: 'Aisle Obstructions', value: 2, drillKey: 'aisle-obstructions' },
      { label: 'General Condition Issues', value: 2, drillKey: 'general-condition' },
      { label: 'Total Defects', value: 8, drillKey: null },
    ],
  },
  {
    id: 'overloaded-trips',
    title: 'Passenger Load',
    metric: 'Overloaded Trips',
    value: 11,
    status: 'critical',
    icon: 'pi pi-users',
    summaryItems: [
      { label: 'Critical Overload (>30%)', value: 8, drillKey: 'critical-overload' },
      { label: 'Moderate Overload (10–30%)', value: 3, drillKey: 'moderate-overload' },
      { label: 'Total Overloaded Trips', value: 11, drillKey: null },
    ],
  },
  {
    id: 'delayed-departures',
    title: 'Schedule Adherence',
    metric: 'Delayed Departures',
    value: 9,
    status: 'warning',
    icon: 'pi pi-clock',
    summaryItems: [
      { label: 'Minor Delay (5–15 min)', value: 5, drillKey: 'minor-delay' },
      { label: 'Major Delay (>15 min)', value: 4, drillKey: 'major-delay' },
      { label: 'Total Delayed', value: 9, drillKey: null },
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
      { label: 'Routes Assessed', value: 8, drillKey: 'on-time' },
      { label: 'Services Delayed', value: 3, drillKey: 'reliability-delayed' },
      { label: 'Services Cancelled', value: 0, drillKey: 'cancelled' },
      { label: 'Total Routes', value: 8, drillKey: null },
    ],
  },
  {
    id: 'operator-compliance',
    title: 'Monthly Contract Compliance',
    metric: 'Operator Compliance Score',
    value: '88.7%',
    status: 'warning',
    icon: 'pi pi-building',
    summaryItems: [
      { label: 'Compliant Operators', value: 6, drillKey: 'compliant-operators' },
      { label: 'Non-Compliant Operators', value: 1, drillKey: 'non-compliant-operators' },
      { label: 'Total Operators', value: 7, drillKey: null },
    ],
  },
  {
    id: 'photo-evidence',
    title: 'Photo Evidence',
    metric: 'Defects Requiring Attention',
    value: 10,
    status: 'critical',
    icon: 'pi pi-camera',
    summaryItems: [
      { label: 'Critical Defects', value: 5, drillKey: 'critical-defects-photo' },
      { label: 'Minor Defects', value: 5, drillKey: 'minor-defects-photo' },
      { label: 'Total Items', value: 10, drillKey: null },
    ],
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
export class ReportingComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly sanitizer = inject(DomSanitizer);

  readonly session = this.auth.session;
  menuVisible = true;
  readonly navigationItems: MenuItem[] = [
    {
      label: 'Vehicles',
      icon: 'pi pi-car',
      command: () => this.openVehicles(),
    },
    {
      label: 'Live Map',
      icon: 'pi pi-map',
      command: () => this.openSmartFleet(),
    },
    {
      label: 'Inspections',
      icon: 'pi pi-search',
      command: () => this.closeMenu(),
    },
    {
      label: 'Shifts',
      icon: 'pi pi-calendar',
      command: () => this.closeMenu(),
    },
    {
      label: 'Reports',
      icon: 'pi pi-chart-bar',
      command: () => this.openReporting(),
    },
  ];

  // ── Tiles grouped by dashboard row (reactive to applied filters) ──────────
  readonly filteredTiles = computed(() => {
    const f = this.appliedFilters();

    return TILES.map((tile): KpiTile => {
      // Recount each drillable summary item
      let newItems: SummaryItem[] = tile.summaryItems.map((item) => {
        if (!item.drillKey) return item;
        return { ...item, value: filterRecordsForKey(item.drillKey, f).length };
      });

      // Recompute the "Total" rows (drillKey === null) as sum of drillable items
      const drillableSum = newItems
        .filter((i) => i.drillKey !== null)
        .reduce((s, i) => s + (typeof i.value === 'number' ? i.value : 0), 0);
      newItems = newItems.map((i) => (i.drillKey === null ? { ...i, value: drillableSum } : i));

      // Default tile face value = drillable sum
      let tileValue: number | string = drillableSum;

      // Service Reliability: recalculate on-time %
      if (tile.id === 'service-reliability') {
        const rows = filterRecordsForKey('on-time', f);
        const totalSvcs = rows.reduce((s: number, r) => s + Number(r['total'] ?? 0), 0);
        const onTimeSvcs = rows.reduce((s: number, r) => s + Number(r['onTime'] ?? 0), 0);
        tileValue = totalSvcs > 0 ? `${((onTimeSvcs / totalSvcs) * 100).toFixed(1)}%` : 'N/A';
        newItems = newItems.map((i) => {
          if (i.drillKey === 'on-time') return { ...i, value: rows.length };
          if (i.drillKey === null) return { ...i, value: rows.length };
          return i;
        });
      }

      // Operator Compliance: recalculate compliance %
      if (tile.id === 'operator-compliance') {
        const compliant = filterRecordsForKey('compliant-operators', f).length;
        const nonCompliant = filterRecordsForKey('non-compliant-operators', f).length;
        const total = compliant + nonCompliant;
        tileValue = total > 0 ? `${((compliant / total) * 100).toFixed(1)}%` : 'N/A';
      }

      return { ...tile, value: tileValue, summaryItems: newItems };
    });
  });

  readonly filteredRow1 = computed(() => this.filteredTiles().slice(0, 3));
  readonly filteredRow2 = computed(() => this.filteredTiles().slice(3, 6));
  readonly filteredRow3 = computed(() => this.filteredTiles().slice(6, 9));

  // ── Global filters – draft (bound to form controls) ──────────────────────
  draftDateFrom: Date = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  draftDateTo: Date = new Date();
  draftOperators: string[] = [];
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
    return this.filteredTiles().find((t) => t.id === id) ?? null;
  });

  /** 1, 2, or 3 – which dashboard row contains the active tile */
  readonly activeTileRow = computed<number | null>(() => {
    const id = this.activeTileId();
    if (!id) return null;
    const idx = TILES.findIndex((t) => t.id === id);
    if (idx < 0) return null;
    return Math.floor(idx / 3) + 1;
  });

  readonly tileBarChartOptions = computed<EChartsOption | null>(() => {
    const tile = this.activeTile();
    if (!tile) return null;
    const drillable = tile.summaryItems.filter((i) => i.drillKey !== null);
    const colors = ['#1d4ed8', '#d97706', '#dc2626', '#16a34a', '#7c3aed', '#0891b2'];
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '8%', containLabel: true },
      xAxis: {
        type: 'category',
        data: drillable.map((i) => i.label),
        axisLabel: { rotate: 30, fontSize: 11, interval: 0 },
      },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          type: 'bar',
          data: drillable.map((i, idx) => ({
            value: typeof i.value === 'number' ? i.value : parseFloat(String(i.value)) || 0,
            itemStyle: { color: colors[idx % colors.length], borderRadius: [4, 4, 0, 0] },
          })),
          label: { show: true, position: 'top', fontSize: 12, fontWeight: 'bold' },
        },
      ],
    };
  });

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
      legend: { orient: 'vertical', right: '5%', top: 'center', textStyle: { fontSize: 11 } },
      series: [
        {
          type: 'pie',
          radius: ['40%', '68%'],
          center: ['38%', '50%'],
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
    return DRILL_CONFIGS[key] ?? null;
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
    this.appliedFilters.set({
      dateFrom: new Date(this.draftDateFrom),
      dateTo: new Date(this.draftDateTo),
      operators: [...this.draftOperators],
      terminals: [...this.draftTerminals],
      routes: [...this.draftRoutes],
    });
  }

  resetFilters(): void {
    const defaultFrom = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
    const defaultTo = new Date();
    this.draftDateFrom = defaultFrom;
    this.draftDateTo = defaultTo;
    this.draftOperators = [];
    this.draftTerminals = [];
    this.draftRoutes = [];
    this.appliedFilters.set({
      dateFrom: defaultFrom,
      dateTo: defaultTo,
      operators: [],
      terminals: [],
      routes: [],
    });
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

  openReporting(): void {
    this.menuVisible = false;
    this.router.navigate(['/reporting']);
  }

  logout(): void {
    this.auth.logout();
  }
}
