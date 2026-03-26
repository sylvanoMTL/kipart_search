# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-03-26
## [0.1.0] - 2026-03-26

### Added
- Parametric component search across JLCPCB/LCSC offline database
- DigiKey API v4 integration with OAuth2 authentication
- Mouser API integration for keyword and MPN lookup
- PySide6 standalone desktop GUI with search bar, results table, and spec panel
- KiCad 9+ IPC API integration for PCB footprint highlight and cross-probe
- BOM verification engine with MPN, datasheet, symbol, and footprint checks
- SQLite cache with per-source TTL for pricing, parametric data, and datasheets
- OS-native credential storage via keyring
- Freemium license activation with dev bypass for source builds
- User verification status with project-local persistence
- Nuitka standalone Windows build with Inno Setup installer
- Automated release pipeline with version gate, GPL firewall, and SHA256 checksums
- CI/CD workflow for Windows release builds on tag push
