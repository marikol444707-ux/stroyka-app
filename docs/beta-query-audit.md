# Beta query audit — 2026-09-26

This audit intentionally does not change runtime query semantics.

## Confirmed hotspot

- `GET /supply-history` accepts `limit=None` and therefore can return an unbounded list.
- The frontend currently calls `/supply-history` without a limit from the full loader and dashboard/mobile loader.
- Applying a global default in `backend.db.limit_offset_sql()` would also change every other caller and could silently truncate existing screens. That is not a safe Beta fix without UI pagination.

## Already bounded path

- `GET /materials` uses the shared paging helper.
- Current frontend loaders pass `MATERIALS_PAGE_LIMIT` explicitly for materials, so this path is already bounded in the primary UI flow.

## Safe next slice

Add pagination to the supply-history UI/API contract together:
1. explicit `limit/offset` in frontend calls;
2. visible `hasMore`/load-more behavior;
3. regression test proving older history is still reachable;
4. only then consider a server default for callers that omit `limit`.

No production profiling, deploy, migration, or runtime data changes were performed.
