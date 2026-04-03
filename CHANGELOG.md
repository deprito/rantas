# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-01

### Added
- **Docker Healthchecks**: Added healthchecks for Celery services in `docker-compose.ghcr.yml` and `stack_file.yml`
  - `celery-worker`: Uses `celery inspect ping` to verify worker responsiveness
  - `celery-beat`: Simple pass-through check (ps/pgrep not available in container)
  - `flower`: HTTP check on port 5555 using httpx
- **Hunting Config Inline Editing**: Added click-to-edit functionality for hunting config patterns
  - Click brand names to edit them inline
  - Click individual patterns to edit them inline
  - Quick-add input field for each brand to add new patterns directly
  - Works for both default brand patterns and regex patterns
  - Saves to local state, persisted with main "Save Configuration" button
- **Loading Experience Optimization**: Improved perceived performance with skeleton screens and progressive loading
  - New `frontend/src/components/skeleton/` directory with reusable skeleton components
  - `SkeletonCard`, `SkeletonShimmer`, `SkeletonStatCard`, `SkeletonTable`, `SkeletonChart` base components
  - `DashboardStatsSkeleton`, `DashboardChartSkeleton`, `DashboardMetricsCardSkeleton` for dashboard
  - `HuntingStatusSkeleton`, `HuntingStatsSkeleton`, `HuntingFiltersSkeleton`, `CertPatrolStreamSkeleton` for hunting page
  - Progressive loading with per-component loading states (no more blocking full-page spinners)
  - Smooth fade-in animations (`.fade-in` class) for content transitions
  - Staggered animations (`.fade-in-stagger-1` through `.fade-in-stagger-6`) for lists
  - Shimmer effect for skeleton loading states
  - Minimal auth loading indicator (top-right corner) instead of full-screen loading

### Changed
- **Dashboard Page**: Each data section (stats, charts, tables) now loads independently with its own loading state
- **Dashboard Components**: Added `fade-in` animation to StatCard, StatusChart, TopDomainsTable, etc.
- **Hunting Page**: Status, stats, and domain list load progressively with skeleton placeholders
- **Auth Loading**: Minimal floating indicator instead of full-screen blocking overlay

### Fixed
- **Fade-in Animation**: Added `.fade-in` class to dashboard components for smooth content transitions
- **Hunting Toggle Performance**: Made toggle optimistic - removed slow `loadStatus()` call after toggle, now uses immediate response from toggle endpoint
- **Hunting Heartbeat Stale**: Fixed toggle endpoint to reset `monitor_last_heartbeat` to current time when starting monitor (was showing stale "2d ago")
- **Phishing Detection**: Added pattern to catch typosquat domains with suspicious TLDs (e.g., `example.app`), while keeping legitimate domains whitelisted

---

## [1.2.0] - 2025-02-28

### Added
- **Editable Hunting Config Feature**: UI for editing all hunting mode patterns directly from the hunting page
  - Added `default_brand_patterns` field to HuntingConfig model and schema
  - Added `whitelist_patterns` field to HuntingConfig model and schema
  - Redesigned hunting config dialog with tabs for Default Patterns, Regex Patterns, Whitelist, and Settings
  - CT log monitor now uses database patterns instead of hardcoded values
  - Database migration `010_add_editable_patterns.py` to add new columns
  - All pattern types (default brand patterns, regex patterns, and whitelist) are now editable from the UI
- **Migration API Stamp Endpoint**: Admin-only endpoint to fix migration state mismatches
  - `POST /api/admin/migrations/stamp` - Set alembic version without running SQL
- **Auto-migration on Startup**: Backend now runs `alembic upgrade head` automatically on container startup

### Changed
- **Hunting Toggle Button**: Removed permission check - Start/Stop monitoring button now always visible for authenticated users

### Fixed
- **Migration Chain**: Fixed migration 007 (`007_add_custom_brand_patterns`) down_revision to point to `006_add_system_config` instead of deleted revision `473be238355e`
- **Idempotent Migrations**: Migration 008 now checks if columns exist before adding them, preventing "column already exists" errors
- **Pattern Appending**: Fixed "Add Custom Regex Patterns" to append new patterns instead of overwriting existing ones (deduplicates automatically)

---

## Format
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Features that will be removed in future releases
- **Removed**: Features removed in this release
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes
