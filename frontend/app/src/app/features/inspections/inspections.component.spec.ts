import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { Router } from '@angular/router';
import { describe, expect, it, beforeEach } from 'vitest';
import { InspectionsComponent } from './inspections.component';
import { AuthService } from '../../core/services/auth.service';
import { InspectionService } from '../../core/api/api/inspection.service';
import { VehicleService } from '../../core/api/api/vehicle.service';
import { DashboardFilterService } from '../../core/services/dashboard-filter.service';

describe('inspection type and violation filtering', () => {
  let component: InspectionsComponent;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [
      { provide: AuthService, useValue: { session: signal(null) } },
      { provide: Router, useValue: {} },
      { provide: InspectionService, useValue: {} },
      { provide: VehicleService, useValue: {} },
      DashboardFilterService,
    ] });
    component = TestBed.runInInjectionContext(() => new InspectionsComponent());
    const common = { shiftId: 1, busId: 'bus', fleetNumber: '3002', registrationNumber: '', operatorName: '', dutyNumber: '504', inspectionTime: '2026-11-24T09:00:00', gps: '', notes: null, summary: '', details: [] };
    component.inspections.set([
      { ...common, inspectionId: 1, type: 'External', pass: true },
      { ...common, inspectionId: 2, type: 'External', pass: false },
      { ...common, inspectionId: 3, type: 'Passenger Count', pass: false },
      { ...common, inspectionId: 4, type: 'Schedule Check', pass: true },
    ]);
  });
  it('type selection includes both compliant and violation records', () => {
    component.selectedInspectionType.set('External');
    expect(component.visibleInspections().map(row => row.inspectionId)).toEqual([1, 2]);
  });
  it('clicking a violation tile replaces a conflicting type selection', () => {
    component.selectedInspectionType.set('External');
    component.filterFailedType('Passenger Count');
    expect(component.visibleInspections().map(row => row.inspectionId)).toEqual([3]);
    component.filterFailedType('Passenger Count');
    expect(component.visibleInspections()).toHaveLength(4);
  });
  it('changing type clears the violation-only filter', () => {
    component.filterFailedType('External');
    component.selectedInspectionType.set('Schedule Check');
    component.clearInspectionTypeViolationFilter();
    expect(component.visibleInspections().map(row => row.inspectionId)).toEqual([4]);
  });
});
