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
