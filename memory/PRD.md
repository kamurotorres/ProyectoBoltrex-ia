# Boltrex - Product Requirements Document

## Original Problem Statement
Build a responsive web application named "Boltrex" for inventory and sales management with an API-first architecture. The system includes Authentication & RBAC, Product Management, Pricing, Categories, Client Management, POS Invoicing, Returns, Suppliers & Purchases, Inventory, Reports, VAT Management, Data Import, Payment Methods, Credit (Fios) management, and PDF ticket generation.

## Architecture
- **Backend:** FastAPI + MongoDB (pymongo) + Pydantic + JWT + ReportLab
- **Frontend:** React + React Router + Tailwind CSS + Shadcn/UI + cmdk
- **Database:** MongoDB (test_database)

## Core Modules (All Implemented)
1. Authentication & RBAC (backend + frontend)
2. Product Management (CRUD)
3. Pricing & Price Lists
4. Categories (CRUD)
5. Client Management (CRUD)
6. POS Invoicing (with payment status)
7. Returns (with credit balance updates)
8. Suppliers & Purchases (with autocomplete)
9. Inventory (real-time stock)
10. Reports
11. VAT Management
12. Data Import (CSV/Excel)
13. Invoice Listing & PDF Tickets
14. Payment Methods (CRUD)
15. Fios/Credits Management
16. Ticket Configuration
17. Roles & Permissions Management
18. User Management

## What's Been Implemented

### Session 1 (Jan 2026)
- Full core modules: Auth, RBAC, Products, Categories, Clients, Suppliers, Purchases, Returns, POS, Inventory, Reports, Import
- Invoice Listing & PDF Ticket generation with ticket config
- Payment Methods & Fios (Credits) modules
- POS payment status (Pagado/Por Cobrar) and payment method selection
- Returns logic updating credit balances
- UX improvements: Autocomplete for Purchases and POS, full-width POS layout
- Seeding scripts for all modules (init_rbac.py, seed_data.py)

### Session 2 (Feb 7, 2026)
- **Frontend RBAC rollout (P0):** Implemented `usePermissions` hook across ALL frontend pages
  - Pages updated: Categories, Clients, Suppliers, Purchases, Returns, UsersManagement, TicketConfig, RolesPermissions, Import, POS
  - Pages already done: Products, PaymentMethods, Fios (partial)
  - Pattern: canCreate gates Create buttons, canUpdate gates Edit/Save buttons, canDelete gates Delete buttons
  - Shared dialogs (Categories, Clients, Users): Separated Dialog from trigger button so both Create and Edit work independently
  - Sidebar navigation already filtered by read permissions (Layout.js)
  - Testing: 100% pass rate on all pages with testing agent

## Credentials
- Admin: admin@boltrex.com / admin (Administrador role, all permissions)

## Prioritized Backlog
- **P1:** Dashboard with sales graphs and reports
- **P2:** Accounts receivable report with overdue balance alerts
