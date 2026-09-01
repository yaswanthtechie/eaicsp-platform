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

Accessibility improvements were made for Modal, Tabs, and DataTable
and verified using keyboard-only navigation.

### Issues found and fixes

- **Modal focus could escape the dialog:** Focus was trapped between
  the first and last focusable elements so keyboard focus stays inside
  the open modal.

- **Modal focus was not restored after closing:** The previously focused
  element is stored when the modal opens and focus is restored to that
  element when the modal closes.

- **Tabs needed keyboard navigation:** Keyboard navigation was added so
  users can move between tabs using the keyboard.

- **Interactive controls needed accessible semantics:** ARIA roles,
  labels, and states were added where required to make controls
  understandable to assistive technologies.

- **Focus indicators were not consistent across the library:** A
  library-wide `:focus-visible` style was added using the existing
  `--color-primary` theme token.

### Accessibility capabilities

- Keyboard navigation
- Visible focus indicators
- ARIA roles and labels
- Focus management
- Focus trapping
- Focus restoration
- Accessible dialogs
- Accessible tabs
- Keyboard-accessible controls

# Performance

Performance improvements include:

- `React.memo`
- `useMemo`
- `useCallback`
- Memoized DataTable filtering
- Memoized DataTable sorting
- Memoized pagination calculations
- Reduced unnecessary renders
- Render-count analysis

The DataTable was tested before and after optimization to identify unnecessary renders and repeated calculations.
Before vs After Render Comparison

The TableRow component was tested with 5 visible rows to measure unnecessary re-renders.

A Test Re-render control was used to trigger a parent component re-render without changing the row data.

Before — without React.memo

Before optimization, all 5 visible rows re-rendered when the parent component re-rendered.

Console output showed additional renders for:

TableRow 1
TableRow 2
TableRow 3
TableRow 4
TableRow 5

Therefore:

Rows re-rendered: 5/5

The console also showed duplicate development renders because the application runs inside React StrictMode. These duplicate renders were not counted as the optimization result.

After — with React.memo

TableRow was wrapped with React.memo to prevent rows from rendering again when their props had not changed.

After triggering the same Test Re-render action:

TableRow 1 → no additional render
TableRow 2 → no additional render
TableRow 3 → no additional render
TableRow 4 → no additional render
TableRow 5 → no additional render

Therefore:

Rows re-rendered: 0/5
Performance Result
Measurement Before After
Visible rows 5 5
Rows re-rendered after parent update 5/5 0/5
React.memo Not used Used
Unnecessary row renders Present Prevented

This demonstrates that unchanged TableRow components are skipped during parent re-renders after applying React.memo.

The initial duplicate console renders are expected during development because the application uses React StrictMode

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

# R5 — Component Library Enhancements

R5 extends the UI component library with Storybook documentation and accessibility testing, additional chart primitives, a high-contrast theme, broader component tests, and a versioned changelog.

The Storybook setup provides the reference environment for the library's component stories, states, and variants. Storybook is configured with the React + Vite framework and the `@storybook/addon-a11y` addon. Component stories use Storybook autodocs where applicable, and the Storybook toolbar provides Light, Dark, and High Contrast theme options.

The chart collection was extended with two additional reusable primitives: `<Sparkline>` and `<Gauge>`. Sparkline provides a compact trend visualization, while Gauge provides a value/progress visualization. Both are included alongside the existing chart components and use the library's design-token system for styling.

A third theme, High Contrast, was added alongside the existing Light and Dark themes. The high-contrast theme is defined through the centralized token variables in `src/theme/variables.css` and can be selected from Storybook. The theme was demonstrated across multiple components, including Button, Badge, Card, Tabs, and StatusIndicator, to verify that the components use the shared theme tokens.

The component test suite was expanded using React Testing Library and Vitest. Tests cover the existing component library as well as the added chart primitives and key component behavior.

A versioned `CHANGELOG.md` was added to record library changes and provide a place for future breaking changes and releases.

## Verification

The implementation was verified with TypeScript, ESLint, Vitest, and the production build.

````bash
npx tsc --noEmit
npm run lint
npm test
npm run build.

Component tests were expanded using Vitest and React Testing Library. The current verification passes with:

```text
Test Files: 3 passed
Tests:      24 passed
````
     24 passed
````
