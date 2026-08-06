# UI Component Library

A reusable **React + TypeScript UI Component Library** designed for building scalable and consistent dashboard applications.

This library provides reusable UI primitives, complex components, dashboard-specific composites, and documentation examples so developers can build applications without recreating common UI patterns.

---

## Features

- Fully typed React components using TypeScript
- Reusable and composable components
- No usage of `any`
- Centralized design tokens
- Consistent UI patterns
- Accessible components
- Dashboard-ready components
- Interactive component documentation

---

## Tech Stack

- React
- TypeScript
- Vite
- CSS
- React Hooks

---

# Project Structure

```
src
│
├── components
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Badge.tsx
│   ├── KpiCard.tsx
│   ├── KpiGrid.tsx
│   ├── AlertBanner.tsx
│   ├── StatusIndicator.tsx
│   ├── Table.tsx
│   ├── DataTable.tsx
│   ├── Modal.tsx
│   ├── Tabs.tsxcd C:\Users\Dell\Desktop\Frontend_task\ui-lib\eaicsp-platform\frontend

│   ├── Toast.tsx
│   └── Spinner.tsx
│
├── docs
│   └── DocsPage.tsx
│
├── theme
│   └── tokens.ts
│
├── hooks
│
├── providers
│
├── forms
│
├── App.tsx
└── main.tsx
```

---

# Installation

Install dependencies:

```bash
npm install
```

Run development server:

```bash
npm run dev
```

Build project:

```bash
npm run build
```

---

# Components

## Button

Reusable button component for user actions.

### Supported Features

- Primary button
- Secondary button
- Danger button
- Loading state
- Disabled state
- Small and medium sizes


Example:

```tsx
<Button
  variant="primary"
  size="md"
>
  Save
</Button>
```

---

## Card

Reusable container component for displaying grouped content.

### Features

- Optional title
- Optional actions
- Custom content support


Example:

```tsx
<Card title="Inventory">

  <p>
    Product details
  </p>

</Card>
```

---

## Badge

Displays status labels and indicators.

### Variants

- Success
- Warning
- Danger
- Info
- Neutral


Example:

```tsx
<Badge status="success">
 Active
</Badge>
```

---

## KPI Card

Displays important dashboard metrics.

### Features

- Label
- Value
- Percentage change
- Positive and negative indicators


Example:

```tsx
<KpiCard
 label="Revenue"
 value="₹5M"
 delta={5}
/>
```

---

## KPI Grid

Dashboard composite component built using KPI Cards.

### Features

- Multiple KPI display
- Configurable columns
- Responsive grid layout


Example:

```tsx
<KpiGrid
 items={kpis}
 columns={4}
/>
```

---

## Status Indicator

Displays application or system status.

### Supported Status

- Online
- Offline
- Pending
- Success
- Warning
- Error


Example:

```tsx
<StatusIndicator
 status="online"
 label="Server Online"
/>
```

---

## Alert Banner

Dashboard notification component built using existing primitives.

Built with:

- Card
- Badge
- Button


### Supported Types

- Info
- Success
- Warning
- Danger


Example:

```tsx
<AlertBanner
 type="warning"
 title="Low Stock"
 message="Some products are below minimum quantity"
/>
```

---

## Table

Generic TypeScript table component.

### Features

- Type-safe columns
- Custom rendering
- Loading state
- Empty state


Example:

```tsx
<Table
 columns={columns}
 data={data}
 rowKey={(row)=>row.id}
/>
```

---

## DataTable

Advanced table component for daily dashboard usage.

### Features

- Sorting
- Filtering
- Pagination
- Row selection
- TypeScript generics


Example:

```tsx
<DataTable
 columns={columns}
 data={users}
/>
```

---

## Modal

Accessible dialog component.

### Features

- Escape key close
- Overlay click close
- ARIA dialog support
- Custom footer support


Example:

```tsx
<Modal
 isOpen={true}
 title="Delete Item"
 onClose={()=>{}}
>
 Content
</Modal>
```

---

## Tabs

Content navigation component.

### Features

- Controlled mode
- Uncontrolled mode
- Disabled tabs


Example:

```tsx
<Tabs
 items={tabs}
/>
```

---

## Toast

Notification component.

### Features

- Success notification
- Error notification
- Warning notification
- Info notification
- Auto dismiss
- Pause on hover


Example:

```tsx
<Toast
 id={1}
 title="Saved Successfully"
 variant="success"
 onClose={()=>{}}
/>
```

---

## Spinner

Loading indicator component.

### Sizes

- Small
- Medium
- Large


Example:

```tsx
<Spinner size="md"/>
```

---

# Design System

All components use centralized design tokens.

Location:

```
src/theme/tokens.ts
```

Tokens include:

- Colors
- Spacing
- Border radius
- Font sizes
- Shadows
- Transitions


Example:

```ts
colors.primary

spacing.md

radius.md
```

---

# Documentation

The component library includes a documentation page:

```
src/docs/DocsPage.tsx
```

Documentation provides:

- Live examples
- Component usage
- Supported variants
- Component behavior

---

# Dashboard Component Usage

Developers can create dashboards using only library components.

Example:

```
Dashboard

 |
 |
 UI Library

 ├── Button
 ├── Card
 ├── Badge
 ├── KPI Components
 ├── Tables
 ├── Modal
 ├── Toast
 ├── Tabs
 └── Status Components
```

---

# Future Enhancements

Planned improvements:

- Storybook integration
- ThemeProvider
- Dark mode support
- CSS variable based tokens
- Form components
- React Hook Form integration
- Zod validation support

---

# Definition of Done

The UI Component Library is complete when developers can build their daily dashboard work using only reusable library components.

Developers should not need to recreate:

- Buttons
- Cards
- Tables
- Modals
- Notifications
- KPI layouts
- Status indicators

The library becomes the single source of truth for UI development.

---

# Author

Built using React + TypeScript.
