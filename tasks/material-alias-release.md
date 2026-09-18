# Company/project material mappings — release track

Base: deployed `1cd73516c809`, plus its documentation commit `0f4b4d5f`.
User chose to continue material mapping after the supplier/journal releases.
Work on supplier payments remains in the parallel worktree.

- [x] Inspect existing local implementation and deployed consumers.
- [x] Read-only production inventory: 14 legacy rows, all inactive; no owned table.
- [x] Integrate the existing owned API/storage and every deployed material reader.
- [x] Integrate the existing editor and complete scoped browser snapshots.
- [x] Verify active membership, project access, conflicts, revocation and retries.
- [x] Rehearse an additive migration following 0023, preserving all legacy rows.
- [ ] Run focused PostgreSQL, full regression, build and authenticated browser checks.
- [ ] Publish coordinated server/browser flags and verify the live release.

Mappings may be company-wide or restricted to one exact project. Do not assign
historical owners by project name. The live inventory contains no active mapping
to import; preserve all 14 inactive rows, their content and disabled state.
Recheck that inventory under deployment locks before enabling the new directory.
Any newly active legacy mapping requires explicit review before cutover.

Use an independent additive migration; the unreleased 0013 branch depends on
warehouse distribution, which is outside this release. Do not run future payment
or distribution migrations or overwrite their separate worktree.
