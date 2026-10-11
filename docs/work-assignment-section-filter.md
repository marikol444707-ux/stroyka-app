# Estimate section filter for work assignment

The existing assignment dialog filters unassigned work by the exact source
section index and optionally by text. Section numbering distinguishes equal
section names; names are never used as identity. Only sections containing
unassigned work appear in the filter.

Changing filters does not change the selected work, manual prices or totals.
Select/clear acts on the displayed rows. The hidden-selection warning and
existing retain-only-found action cover both filters. Mobile final review lists
all selected rows, independent of the filter. Source changes reset the filter
with the existing draft lifecycle. Server assignment identity and permissions
are unchanged.

Verification: 15 focused tests, ESLint, production build; local real-browser
checks at 390/1280 px with three sections and combined text filtering, retaining
one row, final review, navigation back and no mobile horizontal overflow. No
production assignment was created.
