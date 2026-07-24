# UI Library

## Overview

This project is a reusable UI component library built using **React**, **TypeScript**, and **Vite**.

The goal was to build reusable, fully typed UI components without using `any`, maintain consistent styling using design tokens, and demonstrate all components in a showcase page.

---

# Components Implemented

The following reusable components have been implemented:

- Button
- Card
- Badge
- KPI Card
- Table
- Modal
- Tabs
- Spinner
- Toast

Each component is designed to be reusable and can be imported into other React applications.

---

# Features

- React + TypeScript
- Fully typed components
- No use of `any`
- Reusable UI components
- Shared design tokens (`tokens.ts`)
- Mock data stored in App.tsx
- Showcase page demonstrating all components
- Loading and empty states where applicable

---

# Project Structure

````
src/
├── components/
│   ├── Badge.tsx
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── KpiCard.tsx
│   ├── Modal.tsx
│   ├── Spinner.tsx
│   ├── Table.tsx
│   ├── Tabs.tsx
│   └── Toast.tsx
│
│
├── App.tsx
└── tokens.ts

---

# Technologies Used

- React
- TypeScript
- Vite
- CSS

---

# How to Run

### Install dependencies

```bash
npm install
````

### Start the development server

```bash
npm run dev
```

### Open in browser

```
http://localhost:5173
```

---

# What I Found

During this assignment, I learned:

- How to build reusable React components.
- How to define component props using TypeScript interfaces and types.
- How to avoid using `any` by using proper TypeScript types.
- How to use shared design tokens for colors, spacing, and border radius.
- How to build a generic Table component using TypeScript generics.
- How to organize components in a reusable project structure.
- How different UI components can be composed together in a showcase page.

---

# What I Got Stuck On

Some challenges I encountered during development were:

- Understanding TypeScript generics in the Table component.
- Managing component props and state with strict TypeScript typing.
- Organizing the project structure for a reusable UI library.
- Understanding how to prepare the project for submission in a shared Git repository and create a pull request.
- Resolving minor TypeScript and import errors while integrating components.
