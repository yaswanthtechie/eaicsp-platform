# Supplier Portal

## Project Overview

Supplier Portal is a React + TypeScript application that allows suppliers to manage purchase orders and invoices.

This project demonstrates a complete supplier workflow using GraphQL and Apollo Client with a mocked GraphQL backend.

# Features

- Supplier Login
- View Purchase Orders
- View Purchase Order Details
- Acknowledge Purchase Orders
- Submit Invoice
- Upload Invoice PDF
- GraphQL Query
- GraphQL Mutation
- Apollo Client
- Mock Apollo Server
- Loading State
- Error State
- Empty State
- Responsive Mobile First UI
- PWA Ready (Optional Stretch Goal)

# Technology Stack

Frontend

- React
- TypeScript
- Vite
- React Router DOM
- Apollo Client
- CSS

Backend

- Apollo Server
- GraphQL
- Express (Mock Server)

Development Tools

- VS Code
- Node.js
- npm
- Chrome DevTools

# Folder Structure

supplier-portal/

```
public/
│
├── favicon.ico
├── pwa-192.png
├── pwa-512.png
│
server/
│
└── index.js
│
src/
│
├── components/
│
├── context/
│
├── graphql/
│
├── pages/
│
├── routes/
│
├── types/
│
├── utils/
│
├── App.tsx
├── main.tsx
├── index.css
└── tokens.ts
│
package.json
vite.config.ts
README.md
```

# Installation

Move into project

```bash
cd supplier-portal
```

Install Dependencies

```bash
npm install
```

# Packages Installed

## React Router

```bash
npm install react-router-dom
```

Purpose

Navigation between pages.

---

## Apollo Client

```bash
npm install @apollo/client graphql
```

Purpose

Connect React application to GraphQL server.

## Apollo Server

Inside server folder

```bash
npm install @apollo/server graphql express cors body-parser
```

Purpose

Creates Mock GraphQL Backend.

## PWA (Optional)

```bash
npm install vite-plugin-pwa --save-dev
```

Purpose

Makes application installable and offline friendly.

---

# Running the Project

## Terminal 1

Frontend

```bash
npm run dev
```

Runs

```
http://localhost:5173
```

---

## Terminal 2

Backend

```bash
cd server

node index.js
```

Runs

```
http://localhost:4000
```

---

# Application Flow

```
Login

↓

Purchase Orders

↓

View Details

↓

Acknowledge Purchase Order

↓

Status Updated

↓

Back to Orders

↓

New Invoice

↓

Upload Invoice

↓

Submit Invoice
```

---

# Pages

## Login Page

Purpose

Supplier Authentication.

Functions

- Enter Email
- Enter Password
- Login
- Navigate to Orders

Main Hook

```
useNavigate()
```

## Orders Page

Purpose

Display Purchase Orders.

Functions

- Fetch Orders
- Filter Orders
- Logout
- Open Invoice
- View Details

GraphQL

```
GET_PURCHASE_ORDERS
```

React Hook

```
useQuery()
```

---

## Order Details Page

Purpose

Display Complete Purchase Order.

Functions

- Show Items
- Show Total
- Show Status
- Acknowledge Purchase Order

GraphQL

```
ACKNOWLEDGE_PO
```

React Hooks

```
useParams()

useMutation()
```
## Invoice Page

Purpose

Create Invoice.

Functions

- Invoice Number
- Select Purchase Order
- Amount
- Date
- Upload PDF
- Submit Invoice

Only acknowledged Purchase Orders are shown.


# Components

## POCard

Displays one Purchase Order.

Reusable Component.

## StatusBadge

Displays

- Draft
- Sent
- Acknowledged
- Fulfilled
- Cancelled

## Loading

Displayed while GraphQL request is loading.

## ErrorState

Displayed when API request fails.

## EmptyState

Displayed when no Purchase Orders exist.

## FileUpload

Uploads Invoice PDF.

# GraphQL

## Apollo Client

Location

```
src/graphql/apollo.ts
```

Purpose

Connect React with GraphQL Server.

## Queries

Location

```
src/graphql/queries.ts
```

Purpose

Fetch Purchase Orders.

Example

```
GET_PURCHASE_ORDERS
```

## Mutations

Location

```
src/graphql/mutations.ts
```

Purpose

Update Purchase Order Status.

Example

```
ACKNOWLEDGE_PO
```

# Backend

Location

```
server/index.js
```

Contains

- GraphQL Schema
- Queries
- Mutations
- Resolvers
- Mock Purchase Orders

# Types

Location

```
src/types/po.ts
```

Contains

- PurchaseOrder
- POItem
- POStatus

Purpose

Provides TypeScript type safety.

# Routing

Location

```
src/routes/AppRoutes.tsx
```

Routes

```
/login

/orders

/orders/:poNumber

/invoices/new
```
# Main File Flow

```
main.tsx

↓

App.tsx

↓

AppRoutes.tsx

↓

Login

↓

Orders

↓

Order Details

↓

Invoice
```
# GraphQL Flow

```
React Component

↓

Apollo Client

↓

GraphQL Query

↓

Apollo Server

↓

Resolver

↓

Mock Data

↓

React UI
```
# Mutation Flow

```
Click Acknowledge

↓

GraphQL Mutation

↓

Apollo Server

↓

Resolver

↓

Status Updated

↓

React UI Updated
```
# Project Features Completed

- Login
- Purchase Orders
- Purchase Order Details
- GraphQL Query
- GraphQL Mutation
- Apollo Client
- Apollo Server
- Optimistic UI
- Loading State
- Error State
- Empty State
- Invoice Submission
- Upload PDF
- Responsive Design
- Mobile First
- PWA Support (Optional)

# Learning Outcomes

This project demonstrates practical knowledge of

- React
- TypeScript
- GraphQL
- Apollo Client
- Apollo Server
- React Router
- Component Reusability
- State Management
- File Upload
- Mobile First Design
- Progressive Web App (PWA)

#

Project Name

Supplier Portal

Technology

React + TypeScript + GraphQL + Apollo Client + Apollo Server + Vite

Purpose

Supplier Purchase Order and Invoice Management Portal


#### Updated 



## src/auth/

### tokenStorage.ts
Purpose:
- Stores Access Token and Refresh Token.
- Uses localStorage when "Remember Me" is selected.
- Uses sessionStorage when "Remember Me" is not selected.
- Provides helper functions:
  - saveTokens()
  - getAccessToken()
  - getRefreshToken()
  - clearTokens()

---

## src/graphql/

### apollo.ts
Purpose:
- Configures Apollo Client.
- Connects the React application to the GraphQL server.
- Configures Apollo Cache.
- Supports cursor-based pagination.

### authLink.ts
Purpose:
- Adds the Access Token to every GraphQL request.
- Reads the token from tokenStorage.
- Sends the Authorization header automatically.

### queries.ts
Purpose:
- Stores all GraphQL Queries.
- Includes Purchase Order query with:
  - Pagination
  - Search
  - Filters

### mutations.ts
Purpose:
- Stores all GraphQL Mutations.
- Purchase Order Acknowledge Mutation.
- Invoice Submission Mutation.

---

## src/routes/

### AppRoutes.tsx
Purpose:
- Defines all application routes.
- Protects private pages.
- Redirects users to Login when not authenticated.

### ProtectedRoute.tsx
Purpose:
- Checks whether the user is logged in.
- Prevents unauthorized access to protected pages.

---

## src/pages/

### Login.tsx
Purpose:
- User Login.
- Form Validation.
- Stores tokens.
- Supports Remember Me.

### Orders.tsx
Purpose:
- Displays Purchase Orders.
- GraphQL Query.
- Cursor Pagination.
- Search & Filters.
- Load More functionality.
- Logout.

### OrderDetails.tsx
Purpose:
- Displays complete Purchase Order details.
- Purchase Order acknowledgement.
- Optimistic UI update.

### Invoice.tsx
Purpose:
- Invoice creation.
- Form validation.
- GraphQL mutation.
- Upload progress.
- File upload.

---

## src/components/

### FileUpload.tsx
Purpose:
- Drag & Drop upload.
- PDF validation.
- File size validation.
- File preview.
- Remove uploaded file.

### POCard.tsx
Purpose:
- Displays Purchase Order summary.

### StatusBadge.tsx
Purpose:
- Displays Purchase Order status with different badge colors.

### Loading.tsx
Purpose:
- Shows loading state while data is being fetched.

### EmptyState.tsx
Purpose:
- Displays a message when no Purchase Orders are available.

### ErrorState.tsx
Purpose:
- Displays an error message when a GraphQL request fails.

---

## src/types/

### po.ts
Purpose:
- Defines TypeScript interfaces for Purchase Orders and PO Items.
- Provides type safety throughout the application.

src/
│
├── auth/
│   └── tokenStorage.ts
│
├── components/
│   ├── EmptyState.tsx
│   ├── ErrorState.tsx
│   ├── FileUpload.tsx
│   ├── Loading.tsx
│   ├── POCard.tsx
│   └── StatusBadge.tsx
│
├── graphql/
│   ├── apollo.ts
│   ├── authLink.ts
│   ├── mutations.ts
│   └── queries.ts
│
├── pages/
│   ├── Login.tsx
│   ├── Orders.tsx
│   ├── OrderDetails.tsx
│   └── Invoice.tsx
│
├── routes/
│   ├── AppRoutes.tsx
│   └── ProtectedRoute.tsx
│
├── types/
│   └── po.ts
│
└── App.tsx