# UI Component Library + Dashboard Shell

A reusable React + TypeScript UI Component Library for building consistent, accessible, and dashboard-ready applications.

The library provides reusable components, advanced DataTable features, forms, theming, charts, accessibility, performance optimizations, and documentation.

## Project Location

```text
frontend/packages/ui/
```

## Tech Stack

- React
- TypeScript
- Vite
- CSS
- React Hooks
- React Hook Form
- Zod
- Recharts
- Vitest
- Testing Library
- Storybook

# Main Components

## Basic Components

- Button
- Card
- Badge
- KpiCard
- KpiGrid
- AlertBanner
- StatusIndicator
- Table
- Spinner

## Advanced Components

DataTable:

- Sorting
- Filtering
- Pagination
- Row selection
- Loading state
- Empty state
- Overflow handling

Modal:

- Keyboard navigation
- Escape key support
- Focus trap
- Focus restoration
- ARIA support

Tabs:

- Controlled and uncontrolled modes
- Disabled tabs
- Keyboard navigation
- ARIA support

Toast:

- Success
- Error
- Warning
- Info
- Auto dismiss
- `useToast` hook

## Form Components

- Input
- Select
- Textarea
- Checkbox
- Form
- FormField

Forms use:

- React Hook Form
- Zod validation
- Typed form values
- Validation error messages

## Chart Components

- TrendLine
- MiniBarChart
- DonutChart

These are reusable wrappers built using Recharts.

# Theme System

The library supports:

- Light mode
- Dark mode
- System mode

The theme uses centralized design tokens and CSS variables.

```text
src/theme/tokens.ts
```

Tokens include:

- Colors
- Spacing
- Typography
- Border radius
- Shadows
- Transitions

# Accessibility

Accessibility improvements were made for Modal, Tabs, and DataTable.

The library supports:

- Keyboard navigation
- Visible focus indicators
- ARIA roles and labels
- Focus management
- Focus trapping
- Focus restoration
- Accessible dialogs
- Accessible tabs
- Keyboard-accessible controls

The components were tested using keyboard-only navigation.

# Performance

Performance improvements include:

- `React.memo`
- `useMemo`
- Memoized DataTable filtering
- Memoized DataTable sorting
- Memoized pagination calculations
- Reduced unnecessary renders
- React DevTools Profiler analysis

The DataTable was profiled before and after optimization to identify unnecessary renders and repeated calculations.

# Importable Package

The UI library is available as:

```text
@eaicsp/ui
```

Components can be imported using:

```tsx
import { Button } from "@eaicsp/ui";
```

Example:

```tsx
import { Button } from "@eaicsp/ui";

function App() {
  return <Button variant="primary">Save</Button>;
}
```

This allows applications to use the library without depending on internal file paths.

# Documentation / Showcase

The Showcase page provides live examples of the components.

It demonstrates:

- Component variants
- Loading states
- Empty states
- Disabled states
- Long and overflow text
- DataTable filtering and sorting
- Pagination
- Row selection
- Form validation
- Keyboard interaction
- Theme switching

Location:

```text
src/docs/Docspage.tsx
```
# Storybook

Storybook is included for isolated component development and documentation.

Stories are available for key components such as:

- Button
- DataTable
- Modal
- Tabs

# Challenges & Solutions

# 1. TypeScript Errors

Challenge:
Incorrect prop types, imports, and file-name casing caused TypeScript errors.

Solution:
I corrected the prop types, fixed casing and import issues, enabled strict TypeScript checks, and kept the components fully typed without using `any`.

# 2. Modal Accessibility

Challenge:
The Modal needed to work correctly for keyboard users and manage focus properly.

Solution:
I added:

- Focus trapping
- `Tab` / `Shift + Tab`
- `Escape` key support
- Focus restoration
- `useId()`
- `aria-labelledby`
- Dialog ARIA support
- Visible focus states

# 3. DataTable Complexity

Challenge:
The DataTable needed sorting, filtering, pagination, row selection, loading, and empty states while remaining reusable.

Solution:
I separated the table functionality into reusable logic and used TypeScript generics to keep the component type-safe.

# 4. Unnecessary Re-renders

Challenge:
DataTable filtering, sorting, pagination, and row rendering could cause repeated calculations and unnecessary renders.

Solution:
I used `React.memo` and `useMemo` for suitable components and derived DataTable calculations. I also used React DevTools Profiler to compare the component before and after optimization.

# 5. Recharts Configuration

Challenge:
Using Recharts directly in every dashboard would require repeating chart configuration and styling.

Solution:
I created reusable chart wrappers:

- `TrendLine`
- `MiniBarChart`
- `DonutChart`

This gives dashboard developers a simple and consistent API.

# 6. Package Import

Challenge:
The UI library needed to be consumed as a real package instead of through internal relative paths.

Solution:
I configured the package as `@eaicsp/ui` and verified that a consuming application could import and render components using:

```tsx
import { Button } from "@eaicsp/ui";
```
# 7. Documentation Edge Cases

Challenge:
The documentation should show more than just successful or happy-path examples.

Solution:
I added examples for:

- Empty data
- Loading
- Disabled controls
- Long text
- Overflow content
- No matching filter results
- Form validation errors
- Disabled tabs
- Modal keyboard interaction
- Theme switching

# 8. Dependency and Build Issues

Challenge:
Missing dependencies and configuration issues caused development and build errors.

Solution:
I identified the missing dependencies, corrected the configuration and imports, and verified the project using the build and test commands.

# Project Structure

```text
frontend/
└── packages/
    └── ui/
        ├── src/
        │   ├── components/
        │   │   ├── Button.tsx
        │   │   ├── Card.tsx
        │   │   ├── Badge.tsx
        │   │   ├── KpiCard.tsx
        │   │   ├── KpiGrid.tsx
        │   │   ├── DataTable/
        │   │   ├── Modal/
        │   │   ├── Tabs/
        │   │   ├── Toast/
        │   │   └── charts/
        │   │       ├── TrendLine.tsx
        │   │       ├── MiniBarChart.tsx
        │   │       └── DonutChart.tsx
        │   │
        │   ├── forms/
        │   ├── hooks/
        │   ├── providers/
        │   ├── theme/
        │   ├── utils/
        │   ├── docs/
        │   └── index.ts
        │
        ├── storybook/
        ├── package.json
        ├── vite.config.ts
        └── tsconfig.build.json
```


# Installation

From the UI package directory:

```bash
cd frontend/packages/ui
npm install
```

## Run Development Server

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Run Tests

```bash
npm test
```

# Design Principles

The library follows these principles:

- **Reusable** — Components can be shared across applications.
- **Type-safe** — Components use TypeScript.
- **Accessible** — Components support keyboard navigation and ARIA.
- **Consistent** — Components use shared design tokens.
- **Performant** — Unnecessary renders and calculations are optimized.
- **Composable** — Components can be combined to build dashboards.
- **Maintainable** — Common UI behavior is implemented once.


# Definition of Done

The library provides:

- Reusable UI components
- Advanced DataTable
- Accessible Modal and Tabs
- Toast notification system
- Form primitives with Zod validation
- Light/Dark/System themes
- Centralized design tokens
- Keyboard navigation
- Performance optimization
- React DevTools profiling
- Reusable chart components
- Importable `@eaicsp/ui` package
- Showcase documentation
- Edge-case examples
- Storybook stories

The goal is to provide a reusable UI foundation so dashboard applications do not need to recreate common UI components.

# Future Enhancements

Possible future improvements:

- More automated accessibility tests
- Visual regression testing
- DataTable virtualization
- Server-side DataTable support
- Advanced filtering
- Column visibility controls
- Additional chart components
- More automated tests

# Author

Built with **React + TypeScript** for the EAICSP platform.
