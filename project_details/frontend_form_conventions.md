# Frontend Form Conventions

## PrimeNG Float Labels

Use PrimeNG float labels for app form fields and search inputs.

Preferred pattern:

```html
<p-floatlabel variant="on" class="app-float-label">
  <input pInputText id="example-field" />
  <label for="example-field">Example Field</label>
</p-floatlabel>
```

For PrimeNG controls such as `p-datepicker`, `p-multiselect`, and `p-password`, set the component `inputId` and match the label `for` value.

```html
<p-floatlabel variant="on" class="app-float-label">
  <p-multiselect inputId="operator-filter" />
  <label for="operator-filter">Operator</label>
</p-floatlabel>
```

Keep the shared width and label helpers in `frontend/app/src/styles.css`.

## Shared Dashboard Filters

Reports and Analytics must use the shared dashboard filter implementation instead of owning separate local filter forms.

Shared service:

```text
frontend/app/src/app/core/services/dashboard-filter.service.ts
```

Shared component:

```text
frontend/app/src/app/core/components/dashboard-filters/
```

Usage pattern:

```html
<app-dashboard-filters idPrefix="report" (filtersApplied)="onFiltersApplied($event)" />
```

Rules:

- Keep date range and operator filter state in `DashboardFilterService`.
- Pages should read `filterService.appliedFilters` on load so navigating between Reports and Analytics does not reset the selected values.
- The shared component owns the PrimeNG float-label date range and `p-select` operator controls.
- Pages should reload API data from the emitted `DashboardFilters` value after Apply or Reset.
- Use the helper methods on `DashboardFilterService` when calling generated API services:
  - `toAnalyticsSummaryRequestParams(...)`
  - `toReportingSummaryRequestParams(...)`
- Date range should be sent to backend endpoints where supported.
- Operator filtering can be applied client-side only for datasets that include an operator field unless the backend endpoint explicitly supports operator parameters.
- The helper methods must return the OpenAPI-generated request interfaces, currently:
  - `GetAnalyticsSummaryRequestParams`
  - `GetReportingSummaryRequestParams`
