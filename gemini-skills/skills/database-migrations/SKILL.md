---
name: database-migrations
description: Manages schema changes for direct SQLite access in C# projects, ensuring safe testing and generation of migrations.
---

# Database Migrations Protocol (SQLite / C#)

## Core Mandate
Since dashboard and UI projects mandate **direct SQLite access** without webserver middleware, all schema changes must be carefully managed, tested, and versioned within the C# application's lifecycle.

## Guidelines for Schema Changes
1. **No Direct Production Edits:** Never manually edit production SQLite files or schema files without a migration script.
2. **Migration Strategy:**
   - If using `Microsoft.Data.Sqlite` with raw SQL, ensure migration scripts (e.g., `001_initial.sql`, `002_add_users.sql`) are created and embedded as resources or deployed alongside the app.
   - If using `sqlite-net-pcl` or Entity Framework Core with SQLite, use the framework's built-in migration tooling.
3. **Schema Verification:** Read existing schema definitions (e.g., `schemas.json` in Truthpack or `native/src/schema.c` in protected repos) to understand current state before proposing changes.
4. **Testing:** Any new migration must be tested against a temporary or in-memory SQLite database before being finalized. Include verification steps to ensure data integrity is maintained during schema upgrades.
