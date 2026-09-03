# Supplier Portal

A mobile-first Supplier Portal built with **React, TypeScript, Vite, Apollo Client, and GraphQL**. The application allows suppliers to securely manage Purchase Orders, acknowledge orders, and create and submit invoices.

The project implements authentication, protected routes, token management, GraphQL communication, pagination, search and filtering, optimistic UI updates, invoice form validation, offline action queuing, responsive UI, and automated unit/component testing.

---

# Project Overview

The Supplier Portal provides a complete supplier workflow:

```text
Login
  ↓
Purchase Orders
  ↓
Purchase Order Details
  ↓
Acknowledge Purchase Order
  ↓
Updated Order Status
  ↓
Create Invoice
  ↓
Select Acknowledged Purchase Order
  ↓
Upload Invoice PDF
  ↓
Validate Invoice
  ↓
Submit Invoice
```

The application is designed with a **mobile-first approach**, targeting a minimum viewport of approximately **375px** for supplier and warehouse users.

---

# Technology Stack

## Frontend

* React
* TypeScript
* Vite
* React Router DOM
* Apollo Client
* GraphQL
* React Toastify
* CSS
* PWA / Service Worker support

## Backend

* Apollo Server
* GraphQL
* Mock Purchase Order data
* Authentication Service
* FastAPI Authentication API
* JWT Access Tokens
* JWT Refresh Tokens

## Testing

* Vitest
* React Testing Library
* jsdom

## Development Tools

* Node.js
* npm
* VS Code
* Chrome DevTools
* Git

---

# Main Features

## Authentication

* Supplier Login
* Email validation
* Password validation
* JWT Access Token
* JWT Refresh Token
* Remember Me
* Local Storage token persistence
* Session Storage token persistence
* Protected Routes
* Automatic Authorization Header
* Silent Token Refresh
* Token Expiry Detection
* Logout
* Token Cleanup
* Apollo Cache Clear on Logout
* Redirect to Login for unauthenticated users

---

# Authentication Flow

```text
User Login
    ↓
Authentication API
    ↓
Access Token + Refresh Token
    ↓
Token Storage
    ↓
Remember Me?
    ├── Yes → localStorage
    └── No  → sessionStorage
    ↓
Protected Routes
    ↓
Apollo Auth Link
    ↓
Authorization Header
    ↓
GraphQL Request
    ↓
Token Expiry Check
    ↓
Silent Refresh
    ↓
Updated Access Token
```

### Remember Me

When Remember Me is enabled:

```text
localStorage
```

is used so the session can persist.

When Remember Me is disabled:

```text
sessionStorage
```

is used so the session is limited to the browser tab/session.

---

# Purchase Orders

Suppliers can manage Purchase Orders from the Orders page.

## Features

* View Purchase Orders
* Purchase Order Details
* Purchase Order Number
* Supplier Information
* Order Items
* Quantity
* Unit Price
* Total Amount
* Order Status
* Search by PO Number
* Filter by Status
* Filter by Minimum Amount
* Filter by Maximum Amount
* Filter by Date Range
* Cursor-Based Pagination
* Load More
* Loading State
* Error State
* Empty State

---

# Purchase Order Acknowledgement

Suppliers can acknowledge Purchase Orders that are in the appropriate state.

## Acknowledgement Flow

```text
Purchase Order
      ↓
Order Details
      ↓
Click Acknowledge
      ↓
Optimistic UI Update
      ↓
GraphQL Mutation
      ↓
Apollo Server
      ↓
Resolver
      ↓
Purchase Order Status Updated
```

## Features

* Acknowledge Purchase Order
* Optimistic UI
* Apollo Cache Update
* GraphQL Mutation
* Success Notification
* Error Handling
* Offline Queue Support

---

# Invoice Management

Suppliers can create invoices for acknowledged Purchase Orders.

## Invoice Features

* Invoice Number
* Purchase Order Selection
* Invoice Amount
* Invoice Date
* Form Validation
* Purchase Order Validation
* Amount Validation
* Date Validation
* PDF Validation
* File Size Validation
* Drag and Drop
* File Preview
* Remove Selected File
* Submit Invoice
* Success Notification
* Error Notification

Only **acknowledged Purchase Orders** are available for invoice creation.

---

# File Upload

The `FileUpload` component currently handles invoice file selection and validation.

## Current Features

- PDF-only validation
- Maximum file size: **10 MB**
- Drag-and-drop file selection
- File selection
- File preview
- Remove selected file
- File validation errors
- File input reset handling

## Not Yet Implemented

The actual PDF document transfer is deferred to the next implementation round.

- Real PDF upload
- Real upload progress tracking
- Chunked upload for files larger than 5 MB
- Upload retry mechanism

---

# Offline Support

The application supports offline-friendly user actions.

When the browser is offline, supported actions can be stored in an offline queue instead of being immediately sent to the backend.

```text
User Action
    ↓
Browser Offline?
    ├── No
    │    ↓
    │  Execute GraphQL/API Request
    │
    └── Yes
         ↓
      Add Action to Queue
         ↓
      Store in localStorage
         ↓
      Browser Comes Online
         ↓
      Offline Sync
         ↓
      Execute Queued Actions
         ↓
      Remove Successfully Synced Actions
```

## Offline Modules

### `src/utils/offlineQueue.ts`

Responsible for:

* Adding offline actions
* Reading queued actions
* Removing individual actions
* Clearing queued actions
* Handling invalid stored data

### `src/utils/offlineSync.ts`

Responsible for:

* Reading queued actions
* Executing queued actions
* Removing successfully processed actions
* Handling synchronization errors

### `src/hooks/useOfflineSync.ts`

Responsible for:

* Detecting online status
* Synchronizing when the application starts online
* Synchronizing when the browser comes back online
* Registering and removing the `online` event listener

---

# GraphQL

The application uses **Apollo Client** for GraphQL communication.

## GraphQL Flow

```text
React Page
    ↓
Custom Hook
    ↓
Apollo Client
    ↓
GraphQL Query / Mutation
    ↓
Apollo Server
    ↓
Resolver
    ↓
Mock Data
    ↓
Response
    ↓
Apollo Cache
    ↓
React UI
```

---

# Apollo Client

Location:

```text
src/graphql/apollo.ts
```

Responsibilities:

* Configure Apollo Client
* Connect to GraphQL server
* Configure InMemoryCache
* Configure pagination cache behavior
* Support GraphQL queries and mutations
* Integrate authentication

---

# Authentication Link

Location:

```text
src/graphql/authLink.ts
```

Responsibilities:

* Read Access Token from token storage
* Add token to GraphQL requests
* Automatically create the Authorization header

Example:

```text
Authorization: Bearer <access-token>
```

---

# GraphQL Queries

Location:

```text
src/graphql/queries.ts
```

Contains GraphQL queries such as:

```text
GET_PURCHASE_ORDERS
```

The Purchase Order query supports:

* Cursor pagination
* Search
* Status filtering
* Amount filtering
* Date filtering

---

# GraphQL Mutations

Location:

```text
src/graphql/mutations.ts
```

Contains mutations such as:

```text
ACKNOWLEDGE_PO
SUBMIT_INVOICE
```

### `ACKNOWLEDGE_PO`

Updates the Purchase Order acknowledgement status.

### `SUBMIT_INVOICE`

Submits invoice information for an acknowledged Purchase Order.

---

# Cursor-Based Pagination

Purchase Orders are fetched using cursor-based pagination instead of loading all records at once.

Example:

```text
first: 20
after: <cursor>
```

Flow:

```text
Page 1
20 Purchase Orders
      ↓
next cursor
      ↓
Load More
      ↓
Next 20 Purchase Orders
```

This approach is more suitable for large datasets than loading thousands of Purchase Orders in a single request.

---

# Search and Filtering

Purchase Orders support multiple filters.

Available filters:

* PO Number
* Status
* Minimum Amount
* Maximum Amount
* Start Date
* End Date

These filters are passed through the GraphQL query.

---

# Apollo Cache

Apollo Client uses `InMemoryCache` to store GraphQL results.

The cache helps:

* Avoid unnecessary requests
* Update UI efficiently
* Support optimistic updates
* Merge paginated results
* Maintain client-side GraphQL state

---

# Optimistic UI

When a supplier acknowledges a Purchase Order, the UI updates immediately before the backend response is received.

Apollo Client uses an optimistic response in `useAcknowledgePO.ts` to update the normalized `PurchaseOrder` cache immediately.The Purchase Order is normalized using `poNumber` as its cache key.
```text
User clicks Acknowledge
        ↓
Apollo applies optimistic response
        ↓
UI immediately shows ACKNOWLEDGED
        ↓
GraphQL mutation sent
        ↓
Server processes request
        ↓
Success → Keep update
        ↓
Failure → Apollo rolls back optimistic update
```

This improves perceived application performance.

---

# Project Structure

```text
supplier-portal/
│
├── public/
│   ├── favicon.ico
│   ├── pwa-192.png
│   └── pwa-512.png
│
├── server/
│   └── index.js
│
├── src/
│   │
│   ├── api/
│   │   └── auth.ts
│   │
│   ├── auth/
│   │   ├── tokenStorage.ts
│   │   ├── refreshToken.ts
│   │   └── tokenUtils.ts
│   │
│   ├── components/
│   │   ├── POCard.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── FileUpload.tsx
│   │   ├── Loading.tsx
│   │   ├── ErrorState.tsx
│   │   └── EmptyState.tsx
│   │
│   ├── constants/
│   │
│   ├── graphql/
│   │   ├── apollo.ts
│   │   ├── authLink.ts
│   │   ├── queries.ts
│   │   └── mutations.ts
│   │
│   ├── hooks/
│   │   ├── usePurchaseOrders.ts
│   │   ├── useOrderDetails.ts
│   │   ├── useInvoice.ts
│   │   ├── useAcknowledgePO.ts
│   │   └── useOfflineSync.ts
│   │
│   ├── mocks/
│   │   └── purchaseOrders.ts
│   │
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Orders.tsx
│   │   ├── OrderDetails.tsx
│   │   └── Invoice.tsx
│   │
│   ├── routes/
│   │   ├── AppRoutes.tsx
│   │   └── ProtectedRoute.tsx
│   │
│   ├── types/
│   │   └── po.ts
│   │
│   ├── utils/
│   │   ├── offlineQueue.ts
│   │   ├── offlineSync.ts
│   │   ├── currency.ts
│   │   └── date.ts
│   │
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   └── tokens.ts
│
├── package.json
├── vite.config.ts
├── tsconfig.json
└── README.md
```

---

# Important Files

## `src/auth/tokenStorage.ts`

Responsible for token storage.

Functions include:

```text
saveTokens()
getAccessToken()
getRefreshToken()
clearTokens()
```

Supports:

```text
localStorage
sessionStorage
```

---

## `src/auth/tokenUtils.ts`

Responsible for token-related utility operations such as:

* Reading token expiry
* Checking whether a token is expired
* Supporting refresh timing logic

---

## `src/auth/refreshToken.ts`

Responsible for:

* Refresh token requests
* Obtaining a new access token
* Updating stored access token

---

## `src/api/auth.ts`

Responsible for authentication API communication.

Handles:

```text
Login
Refresh Token
Logout
```

---

## `src/routes/ProtectedRoute.tsx`

Protects authenticated pages.

If a user is not authenticated:

```text
Protected Page
      ↓
Authentication Check
      ↓
Not Authenticated
      ↓
Redirect to /login
```

---

# Pages

## Login Page

Location:

```text
src/pages/Login.tsx
```

Responsibilities:

* Supplier login
* Email validation
* Password validation
* Remember Me
* Token storage
* Authentication
* Redirect to Orders

---

## Orders Page

Location:

```text
src/pages/Orders.tsx
```

Responsibilities:

* Fetch Purchase Orders
* Display Purchase Orders
* Search
* Filters
* Cursor pagination
* Load More
* Loading state
* Error state
* Empty state
* Logout

---

## Order Details Page

Location:

```text
src/pages/OrderDetails.tsx
```

Responsibilities:

* Display complete Purchase Order
* Display items
* Display amount
* Display status
* Acknowledge Purchase Order
* Optimistic UI

---

## Invoice Page

Location:

```text
src/pages/Invoice.tsx
```

Responsibilities:

- Create invoice
- Select acknowledged Purchase Order
- Validate invoice
- Select and validate invoice PDF
- Submit invoice information

Note: Real PDF document upload and real upload progress are not yet implemented and are deferred to the next implementation round.

---

# Reusable Components

## `POCard`

Displays Purchase Order summary information.

---

## `StatusBadge`

Displays Purchase Order status.

Supported statuses:

```text
DRAFT
SENT
ACKNOWLEDGED
FULFILLED
CANCELLED
```

---

## `FileUpload`

Provides:

- File selection
- Drag and drop
- PDF validation
- File size validation
- File preview
- Remove file

Real PDF upload and upload progress are deferred to a future implementation round.

---

## `Loading`

Displays loading indicators during asynchronous operations.

---

## `ErrorState`

Displays user-friendly error information when an operation fails.

---

## `EmptyState`

Displays a meaningful message when no data is available.

---

# Routing

Location:

```text
src/routes/AppRoutes.tsx
```

Application routes:

```text
/login
/orders
/orders/:poNumber
/invoices/new
```

Route flow:

```text
/login
   ↓
/orders
   ↓
/orders/:poNumber
   ↓
/invoices/new
```

The Orders, Order Details, and Invoice pages are protected by `ProtectedRoute`.

---

# TypeScript Types

Location:

```text
src/types/po.ts
```

Contains TypeScript definitions for:

* Purchase Order
* Purchase Order Item
* Purchase Order Status
* Pagination-related data

TypeScript provides compile-time type safety across the application.

---

# Backend

Mock GraphQL server:

```text
server/index.js
```

Responsibilities:

* GraphQL schema
* Query definitions
* Mutation definitions
* Resolvers
* Mock Purchase Order data
* Purchase Order status updates
* Invoice submission handling

---

# Authentication Service

The frontend can communicate with the Authentication Service through:

```text
VITE_AUTH_URL
```

The authentication service is responsible for:

* Login
* Access Token generation
* Refresh Token generation
* Token refresh
* Logout/revocation

---

# Environment Variables

Create a `.env` file in the Supplier Portal project.

```env
VITE_GRAPHQL_URL=http://localhost:4000
VITE_AUTH_URL=http://localhost:8005
```

### `VITE_GRAPHQL_URL`

URL of the GraphQL server.

### `VITE_AUTH_URL`

URL of the authentication service.

Do not commit sensitive secrets to the repository.

---

# Installation

Clone or open the project and move into the Supplier Portal directory:

```bash
cd frontend/packages/supplier-portal
```

Install dependencies:

```bash
npm install
```

---

# Running the Application

## 1. Start Frontend

From the Supplier Portal directory:

```bash
npm run dev
```

The Vite development server normally runs at:

```text
http://localhost:5173
```

---

# 2. Start GraphQL Server

Open another terminal:

```bash
cd frontend/packages/supplier-portal
node server/index.js
```

The mock GraphQL server runs on:

```text
http://localhost:4000
```

---

# 3. Start Authentication Service

The authentication service is a separate backend service.

From the authentication service directory:

```bash
uvicorn app.main:app --reload --port 8005
```

The authentication service runs on:

```text
http://localhost:8005
```

---

# Testing

The project uses **Vitest** and **React Testing Library**.

Run all tests:

```bash
npm run test:run
```

The current test suite covers:

* Token Storage
* Token Utilities
* Offline Queue
* Offline Sync
* Offline Sync Hook
* File Upload
* Status Badge
* Acknowledge Purchase Order Hook

Current test result:

Test Files: 16 passed
Tests:      78 passed

All current automated tests are passing.

---

# Test Coverage Areas

## Token Storage Tests

Validates:

* Local Storage
* Session Storage
* Access Token
* Refresh Token
* Authentication state
* Token cleanup
* Access Token update

---

## Offline Queue Tests

Validates:

* Add action
* Read actions
* Multiple actions
* Remove action
* Clear queue
* Invalid JSON handling

---

## Offline Sync Tests

Validates:

* Synchronization
* Queued action processing
* Successful removal after synchronization

---

## Offline Sync Hook Tests

Validates:

* Initial online synchronization
* Synchronization when browser comes online
* Event listener cleanup

---

## File Upload Tests

Validates:

* Upload area
* PDF validation
* Invalid file rejection
* File size validation
* Selected file display
* File removal
* Error display

---

## Status Badge Tests

Validates:

* Draft status
* Sent status
* Acknowledged status
* Fulfilled status
* Cancelled status
* Status styling
* Uppercase display

---

## Acknowledge Purchase Order Tests

Validates:

* Offline acknowledgement queue
* Online GraphQL mutation

---

# Build

Create a production build:

```bash
npm run build
```

The build performs:

```text
TypeScript Compilation
        ↓
Vite Production Build
        ↓
dist/
```

A successful build means the application passes TypeScript compilation and Vite production bundling.

---

# Application Architecture

```text
                    Supplier
                       │
                       ▼
                 React Frontend
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
   Authentication API         Apollo Client
          │                         │
          ▼                         ▼
    JWT Tokens                 GraphQL API
                                    │
                                    ▼
                              Apollo Server
                                    │
                                    ▼
                                Resolvers
                                    │
                                    ▼
                                Mock Data
```

---

# Complete Purchase Order Flow

```text
Supplier Login
      ↓
Authentication API
      ↓
Access + Refresh Tokens
      ↓
Protected Orders Page
      ↓
Fetch Purchase Orders
      ↓
Search / Filter / Pagination
      ↓
Select Purchase Order
      ↓
Order Details
      ↓
Acknowledge Purchase Order
      ↓
Optimistic UI
      ↓
GraphQL Mutation
      ↓
Updated Status
```

---

# Complete Invoice Flow

```text
Orders
   ↓
Select Acknowledged PO
   ↓
Create Invoice
   ↓
Enter Invoice Number
   ↓
Enter Invoice Amount
   ↓
Select Invoice Date
   ↓
Upload PDF
   ↓
Validate PDF
   ↓
Preview File
   ↓
Submit Invoice
   ↓
GraphQL Mutation
   ↓
Success / Error Notification
```

---

# Error and Loading Handling

The application provides proper UI states for asynchronous operations.

## Loading

Displayed while:

* Login is processing
* Purchase Orders are loading
* Purchase Order details are loading
* Invoice is submitting
* File operations are processing

## Error

Displayed when:

* API request fails
* GraphQL request fails
* Authentication fails
* File validation fails
* Invoice validation fails
* Offline synchronization fails

## Empty

Displayed when:

* No Purchase Orders are available
* Search/filter returns no results

---

# Responsive Design

The application follows a mobile-first design approach.

Primary target:

```text
375px mobile viewport
```

The UI is responsive for:

* Mobile
* Tablet
* Desktop

The main supplier workflow is optimized for users who may access the application from mobile devices.

---

# PWA Support

The project is configured to support Progressive Web App capabilities where enabled.

PWA assets include:

```text
public/pwa-192.png
public/pwa-512.png
```

PWA functionality can provide:

* Installable application
* Service worker support
* Cached application shell
* Better experience in unreliable network conditions

---

# Current Implementation Status

## Authentication

* Login
* JWT Access Token
* Refresh Token
* Remember Me
* Local Storage
* Session Storage
* Protected Routes
* Authorization Header
* Silent Token Refresh
* Logout
* Token Cleanup
* Apollo Cache Clear

## Purchase Orders

* Purchase Order List
* Purchase Order Details
* Search
* Status Filter
* Amount Filter
* Date Filter
* Cursor-Based Pagination
* Load More
* Loading State
* Error State
* Empty State

## Purchase Order Acknowledgement

* Acknowledge Purchase Order
* GraphQL Mutation
* Optimistic UI
* Apollo Cache Update
* Success Notification
* Error Handling
* Offline Queue

## Invoice

- Invoice Form
- Purchase Order Selection
- Invoice Validation
- Invoice Number Validation
- Invoice Amount Validation
- Invoice Date Validation
- PDF Validation
- File Size Validation
- Drag and Drop
- File Preview
- Remove File
- Invoice GraphQL Mutation

### Deferred

- Real PDF document upload
- Real upload progress
- Chunked upload for large files

## Offline Support

* Offline Queue
* Local Storage Queue
* Online Detection
* Automatic Synchronization
* Online Event Listener
* Queue Cleanup
* Offline Acknowledgement Support

## Testing

* Vitest Configuration
* React Testing Library
* Token Storage Tests
* Token Utility Tests
* Offline Queue Tests
* Offline Sync Tests
* Hook Tests
* File Upload Tests
* Status Badge Tests
* Acknowledge PO Tests
* 16 Test Files / 78 Tests Passing

## UI

* Mobile-First Design
* Responsive Layout
* Loading State
* Error State
* Empty State
* Reusable Components
* Design Tokens

---

# Future Enhancements

The core Supplier Portal workflow is implemented. The following functionality is planned for a future implementation round:

- Real production Purchase Order API
- Real production Invoice API
- Real PDF document upload
- Real PDF storage service
- Real upload progress tracking
- Chunked uploads for files larger than 5 MB
- Upload retry mechanism
- WebSocket-based real-time Purchase Order updates
- Production database integration


---

# Development Guidelines

When adding new functionality:

1. Use TypeScript types instead of `any`.
2. Keep GraphQL queries and mutations inside `src/graphql/`.
3. Keep reusable business logic inside custom hooks.
4. Keep reusable UI inside `src/components/`.
5. Protect authenticated routes.
6. Handle loading, error, and empty states.
7. Validate user input before submission.
8. Keep authentication tokens out of application state when possible.
9. Test important utility functions and components.
10. Verify the UI at the 375px mobile viewport.
11. Avoid unnecessary API requests.
12. Use cursor pagination for large Purchase Order datasets.

---

# Project Summary

**Project Name**

Supplier Portal

**Purpose**

A mobile-first supplier application for Purchase Order management and Invoice submission.

**Frontend**

React + TypeScript + Vite

**API**

GraphQL + Apollo Client

**Backend**

Apollo Server + Authentication Service

**Authentication**

JWT Access Token + Refresh Token

**Testing**

Vitest + React Testing Library

**Core Workflow**

```text
Login
  ↓
Purchase Orders
  ↓
Order Details
  ↓
Acknowledge PO
  ↓
Create Invoice
  ↓
Upload PDF
  ↓
Submit Invoice
```

---



**Supplier Portal Frontend**

Built using:

```text
React
TypeScript
Vite
Apollo Client
GraphQL
Apollo Server
React Router
JWT Authentication
Vitest
React Testing Library 
```
## Round 4 Features

- JWT Access Token Authentication
- JWT Refresh Token Authentication
- Remember Me with Local Storage / Session Storage
- Protected Routes
- Automatic Authorization Header
- Silent Token Refresh
- Token Expiry Detection
- Logout and Token Cleanup
- Apollo Cache Clear on Logout
- Cursor-Based Pagination
- Purchase Order Search and Filtering
- Optimistic UI for Purchase Order Acknowledgement
- Offline Action Queue
- Offline Action Synchronization
- Duplicate Offline Action Prevention
- Offline Banner
- Keyboard Accessibility
- Purchase Order Notifications
- Automated Unit and Component Testing

## Round 5

## 1. Round 5 Objective

Round 5 focused on improving the Supplier Portal through:

* Contract-first GraphQL schema
* Expanded test coverage
* Error Boundary
* Purchase Order list virtualization
* Accessibility improvements

## 2. What I Implemented

### 2.1 Contract-first GraphQL Schema

Implemented and maintained `schema.graphql` as the frontend GraphQL contract.

* Added/updated `src/graphql/schema.graphql`
* Kept GraphQL queries and TypeScript types aligned with the schema
* Standardized Purchase Order fields using camelCase
* Standardized Purchase Order status values using the `POStatus` enum
* Used the connection-based Purchase Order structure
* Supported pagination through `edges` and `pageInfo`
* Configured Apollo cache normalization using `poNumber`
* Updated GraphQL tests to use the real `GET_PURCHASE_ORDERS` query and Apollo cache configuration

### 2.2 Expanded Test Coverage

Expanded automated test coverage across important application functionality.

Tests cover:

* Authentication and token storage
* Login and protected navigation
* Purchase Order rendering
* Purchase Order pagination
* Search and filters
* Date filters
* Logout
* Acknowledge PO behavior
* Offline queue
* Offline synchronization
* Invoice behavior
* File upload validation
* Status badge rendering
* GraphQL/Apollo behavior
* Error Boundary behavior

### 2.3 Error Boundary

Implemented an Error Boundary to prevent an unexpected React rendering error from breaking the complete application UI.

The Error Boundary:

* Catches render-time errors
* Displays fallback UI
* Prevents the application from showing a blank/broken screen
* Has automated test coverage

### 2.4 Purchase Order List Virtualization

Implemented virtualization for the Purchase Order list using `@tanstack/react-virtual`.

The Orders page:

* Renders only the visible/nearby PO items
* Uses a scrollable container
* Calculates virtual item positions
* Uses overscan for smoother scrolling
* Uses `poNumber` as the stable row key

### 2.5 Accessibility Improvements

Improved accessibility of the invoice PDF upload flow.

The file upload component now provides a dedicated:

**Browse files**

button.

This provides a keyboard-accessible way to open the file picker instead of depending only on drag-and-drop.

Also verified:

* Button has `type="button"`
* Button activation triggers the file picker
* PDF validation remains functional
* File size validation remains functional
* Preview and Remove actions remain functional

## 3. Test Coverage

### Final Test Result

```text
Test Files: 16 passed
Tests:      78 passed
Failed:     0
```

The production build also completes successfully with TypeScript compilation and Vite production bundling.

## Not Done

* The GraphQL schema is documentation-as-code for the target backend contract.
* The schema has not yet been validated against Rashida's live GraphQL backend implementation.
* Backend GraphQL integration is planned for a future round.
* The Supplier Portal continues to use frontend mocks during Round 5.
