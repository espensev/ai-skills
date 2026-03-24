---
name: csharp-ui-builder
description: Enforces that new user-facing dashboard and UI projects are built in C# with direct SQLite access (no webserver middleware).
---

# C# UI Builder Protocol

## Core Mandate
Based on the global user preferences and workspace rules:
- **All new user-facing applications** must be built in **C#**, not Python.
- **Dashboard/UI projects** must use **direct SQLite access** (no webserver middleware).
- **Web Servers:** Do not build Python web servers for new projects.
- **Tooling:** PowerShell is the preferred scripting language on Windows. Avoid Python for local workspace tooling.

## Implementation Guidelines
1. **Architecture:** Use a modern C# UI framework (e.g., WinUI 3, WPF, or Avalonia) for frontend desktop applications.
2. **Database:** Integrate SQLite directly using `Microsoft.Data.Sqlite` or `sqlite-net-pcl` embedded within the desktop application.
3. **No Middleware:** Do not create REST APIs, GraphQL endpoints, or intermediate web servers to serve the UI or to mediate database access.
4. **Scripting:** When creating automation, build, or deployment scripts, strictly use `.ps1` (PowerShell) scripts.
