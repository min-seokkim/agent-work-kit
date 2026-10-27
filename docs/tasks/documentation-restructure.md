# Documentation restructuring

## Current status

The owner selected an agent-first development system: short current task records, separate historical records and task-based access to validation evidence. This revision replaces the navigation-only refresh in `90e2557`.

Next action: read `.awkit/handoffs/documentation-restructure/structure.json` for the exact snapshot, checks and delivery stages. Finish any pending stage against that revision. Once delivery is complete, select further product work with the owner from the roadmap.

## Scope and acceptance

ID: `documentation-restructure`. Owner: the implementing session until delivery. Base: `90e2557`. Scope: development documents, their incoming references, a repository-only evidence catalogue script and its tests. Product commands and raw evidence retain their existing formats and locations.

Acceptance: an agent can find the selected task, its next action, source requirements and evidence without reading execution history. Preserve prior records, identifiers, heading anchors, failures and qualifications in `docs/history/`. Keep one current record per task. Catalogue local evidence by document references, identify shared and unreferenced collections, and report absent or unreadable sources without inferring a pass. Retain dirty workspaces and run artifacts.

## Verification and delivery

The receipt above records preservation and link checks, catalogue tests, reading and rendered inspection, frozen `checks.toml` results, commit, Windows/Linux CI and exact-installation comparison. Keep it outside the frozen files. Main-agent reading is self-review; mechanical checks and historical reviews do not establish human acceptance of this rewrite.

Earlier navigation, cleanup and split receipts remain in `.awkit/handoffs/documentation-restructure/`; this revision uses new filenames. Run `python scripts/evidence_catalog.py` to refresh `.awkit/evidence/index.md` and `catalog.json` from the local checkout. Generated lists describe availability and references; verification claims require the cited run and its snapshot.

## History and evidence

<a id="current-navigation-refresh"></a><a id="earlier-scope-and-evidence"></a><a id="outcome-and-scope"></a><a id="awkit-observations"></a><a id="verification-and-next-action"></a><a id="readme-current-state-refresh"></a>

[Full record and verification history](../history/tasks/documentation-restructure.md) preserves the original scope, decisions, failures and evidence paths. The [evidence guide](../evidence.md) explains how to find retained local artifacts.
