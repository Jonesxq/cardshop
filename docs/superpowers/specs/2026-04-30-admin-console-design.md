# Admin Console Design

## Goal

Build an independent `/admin-console` Vue operations backend for the virtual goods card-delivery shop. The console should cover daily operations end to end: dashboard, orders, products, inventory, payments, users, announcements, site settings, and audit logs.

The existing Django Admin remains available as a fallback for low-frequency maintenance, but routine operations should happen in `/admin-console`.

## Current Project Context

The project is a Django 5.2 + Django REST Framework backend with a Vue 3 + Vite + Element Plus frontend. The current customer-facing frontend already uses JWT authentication through the existing accounts API. Business data lives in these existing apps:

- `shop`: categories, products, card secrets, announcements, site config, Codex import helpers.
- `orders`: orders, payment state, delivery items, order services.
- `payments`: payment gateway, callbacks, provider transaction records.
- `accounts`: custom user model based on Django `AbstractUser`.

Admin operations today mostly use Django Admin, with custom pages for the admin guide, product card import, and Codex card import.

## Chosen Approach

Use the complete operations console approach:

- Add a dedicated Django app named `admin_console` for admin-facing APIs, permissions, audit logs, statistics, and high-risk operation services.
- Add a Vue route group at `/admin-console` inside the existing frontend app, using a separate admin layout and admin API client methods.
- Reuse the existing JWT flow, but require staff access for all `/api/admin-console/*` endpoints.
- Keep Django Admin available for fallback and emergency maintenance.

This avoids polluting customer-facing code with operations complexity while still using the current deployment, authentication, database models, and UI stack.

## Users And Roles

The console supports three fixed roles:

- `operator`: can manage products, categories, inventory, orders, announcements, and operational dashboard tasks. Cannot assign roles. Cannot view full sensitive payment callback payloads.
- `finance`: can view payment flows, order amounts, finance-related dashboard metrics, and resolve payment exceptions. Cannot import card secrets, replace cards, or change product content.
- `superadmin`: has all permissions, including user role assignment, site settings, sensitive payment payload visibility, and all high-risk operations.

Role storage should be simple and explicit. Add an `AdminProfile` model in the new `admin_console` app with a one-to-one relation to the existing user model and a `role` field. Console access still requires `is_staff=True`. Superusers are treated as `superadmin` even if no `AdminProfile` exists.

## Information Architecture

The `/admin-console` menu contains these sections:

- Dashboard: mixed operations and analysis dashboard.
- Orders: order list, filters, detail drawer, state interventions, delivery actions.
- Products: product and category management, status, price, image URL, description, sorting, stock overview.
- Inventory: card-secret list, product filtering, import preview, import commit, duplicate detection, low-stock warnings, abnormal stock operations.
- Payments: payment transaction list, provider filters, linked orders, raw payload view with role-based masking, exception resolution.
- Users: user list, order count, total spend, login status, staff role assignment.
- Content: announcement management and site display configuration.
- Logs: admin operation logs with actor, target, action, reason, before state, after state, and timestamp.

The UI style should be professional and restrained: light theme, compact spacing, high information density, predictable navigation, clear tables, and small but legible dashboard cards. It should feel like a practical SaaS or ERP operations surface, not a marketing page.

## Dashboard

The dashboard is a mixed operations dashboard:

- Top summary metrics: today order count, today paid amount, pending orders, low-stock products, abnormal payments.
- Operational tasks: low-stock list, abnormal payment list, latest pending orders.
- Analysis area: recent 7-day order and sales trend, top-selling products, recent paid orders.

Every dashboard task item links to the relevant filtered list so operators can act immediately.

## Order Operations

The order list defaults to recent orders and supports filters by status, product, contact, order number, and time range. Selecting an order opens a right-side detail drawer so the operator keeps list context.

High-risk order actions are allowed:

- Change order status.
- Manually mark payment as successful.
- Cancel a pending or abnormal order.
- Redeliver existing delivery content.
- Replace delivered cards.
- Release reserved inventory.
- Handle abnormal payment state.

Every high-risk operation must:

- Check role permissions on the backend.
- Run in a database transaction when it mutates orders or inventory.
- Require a non-empty reason.
- Record an `AdminOperationLog`.
- Return the operation log ID to the frontend.
- Show a confirmation dialog in the frontend before submitting.

Redelivery should not silently consume new inventory. Card replacement must explicitly decide what happens to the old card: release it when safe, or mark it unusable when it may have been exposed.

## Inventory Import

Inventory import is a two-step flow:

1. Preview import: accept pasted text or uploaded TXT/CSV, parse rows, detect empty rows, duplicates within input, and duplicates already in the database for the selected product.
2. Commit import: create only valid new cards after the operator confirms the preview summary.

The preview should return total rows, valid rows, empty rows, duplicate rows, existing rows, and sample rejected rows. The commit should return created count, skipped duplicate count, and an audit log ID.

Card secrets remain encrypted in storage. Lists do not show full cleartext card secrets by default.

## Payments

Payment management focuses on traceability and exception handling:

- List transactions with provider, merchant order number, channel trade number, amount, status, linked order, and creation time.
- Payment detail view shows raw callback payload.
- `operator` role sees masked sensitive payload fields.
- `finance` and `superadmin` can inspect full payloads.
- Exception resolution requires a reason and writes an audit log.

Payment actions should not bypass order service rules. When a payment action changes order state, it should reuse the same service layer used by normal payment completion where possible.

## Users And Staff Roles

User management supports:

- Searching users by email or username.
- Viewing order count and total paid amount.
- Enabling or disabling login.
- Assigning one of the fixed console roles to staff users.

Only `superadmin` can change staff roles or grant console access. Non-staff users cannot access `/admin-console` even if they have a role value.

## API Surface

The management API lives under `/api/admin-console/`:

- `GET /api/admin-console/me`
- `GET /api/admin-console/dashboard`
- `GET /api/admin-console/products`
- `POST /api/admin-console/products`
- `PATCH /api/admin-console/products/{id}`
- `GET /api/admin-console/categories`
- `POST /api/admin-console/categories`
- `PATCH /api/admin-console/categories/{id}`
- `GET /api/admin-console/cards`
- `POST /api/admin-console/cards/import/preview`
- `POST /api/admin-console/cards/import/commit`
- `GET /api/admin-console/orders`
- `GET /api/admin-console/orders/{id}`
- `POST /api/admin-console/orders/{id}/mark-paid`
- `POST /api/admin-console/orders/{id}/cancel`
- `POST /api/admin-console/orders/{id}/redeliver`
- `POST /api/admin-console/orders/{id}/replace-card`
- `POST /api/admin-console/orders/{id}/release-stock`
- `GET /api/admin-console/payments`
- `GET /api/admin-console/payments/{id}`
- `POST /api/admin-console/payments/{id}/resolve`
- `GET /api/admin-console/users`
- `GET /api/admin-console/users/{id}`
- `PATCH /api/admin-console/users/{id}`
- `GET /api/admin-console/announcements`
- `POST /api/admin-console/announcements`
- `PATCH /api/admin-console/announcements/{id}`
- `GET /api/admin-console/site-config`
- `PATCH /api/admin-console/site-config/{key}`
- `GET /api/admin-console/logs`

List endpoints should support pagination and practical filters. Mutation errors should return readable Chinese `detail` messages. High-risk mutation responses include `log_id`.

## Frontend Structure

Add admin console files inside the existing Vue frontend:

- `src/views/admin/AdminConsoleLayout.vue`
- `src/views/admin/DashboardView.vue`
- `src/views/admin/OrdersView.vue`
- `src/views/admin/ProductsView.vue`
- `src/views/admin/InventoryView.vue`
- `src/views/admin/PaymentsView.vue`
- `src/views/admin/UsersView.vue`
- `src/views/admin/ContentView.vue`
- `src/views/admin/LogsView.vue`
- `src/api/adminConsole.js`
- `src/stores/adminSession.js`

The admin layout should use Element Plus components with icons from `@element-plus/icons-vue`. The first screen after login is the actual dashboard, not a landing page.

Admin route guards should:

- Require JWT authentication.
- Call `/api/admin-console/me` to verify staff access and role.
- Redirect non-authenticated users to the existing `/login` page with a redirect query pointing back to `/admin-console`.
- Show a clear forbidden state for authenticated users without staff access.
- Hide menu items and buttons that the current role cannot use.

Backend permission checks remain authoritative even when the frontend hides actions.

## Error Handling And Empty States

All admin pages should include:

- Loading states for initial data and table refreshes.
- Empty states for no results after filtering.
- Inline form validation for required fields.
- Toast messages for successful actions.
- Confirmation dialogs for high-risk operations.
- Clear error messages from backend `detail` responses.

Dangerous actions should use explicit action labels and reason fields, not vague confirmations.

## Security And Audit

Security requirements:

- All `/api/admin-console/*` endpoints require authenticated staff users.
- Role checks happen in backend permissions or service methods.
- Card secrets stay encrypted and are not exposed in normal inventory tables.
- Payment payloads are masked for roles without sensitive access.
- Mutating high-risk operations write immutable audit logs.
- Audit logs include actor, role, action, target type, target ID, reason, before snapshot, after snapshot, request IP, user agent, and timestamp.

Audit logs should be readable in the console and registered in Django Admin for emergency access.

## Implementation Boundaries

This project does not include:

- Configurable menu-level RBAC.
- Complex BI or funnel analytics.
- WebSocket real-time updates.
- Multi-tenant or multi-shop support.
- Multi-language admin UI.
- A separate frontend repository or independent admin deployment.

These boundaries keep the console complete enough for daily operations without turning the MVP into a platform rewrite.

## Testing Strategy

Backend tests should cover:

- Staff-only access to admin-console APIs.
- Role-specific access for operator, finance, and superadmin.
- Dashboard statistics.
- Product and category mutations.
- Inventory import preview and commit.
- Duplicate card import handling.
- Order state changes and inventory side effects.
- Payment exception resolution.
- Operation log creation for every high-risk action.

Frontend verification should cover:

- Admin route guard and forbidden state.
- Role-based menu and button visibility.
- Dashboard loading and filtered navigation.
- Order detail drawer and high-risk confirmation dialogs.
- Inventory import preview and commit flow.
- Payment detail payload masking.
- Build success with `npm run build`.

Manual end-to-end verification should use a staff account to:

1. Enter `/admin-console`.
2. View the dashboard.
3. Create or update a product.
4. Preview and commit a card import.
5. Create a customer order from the storefront.
6. Manually handle the order from the console.
7. Inspect the resulting operation log.
