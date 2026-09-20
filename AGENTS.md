# Deployment retention

The user explicitly requires deleting deployment backups and staging after an
update is successfully installed and verified. Do not accumulate release copies.
Follow docs/deployment-retention.md. Keep rollback files only while deployment is
unfinished or failed. Back up only the current frontend manifest and public files,
not historical static chunks; do not create a full Git bundle backup per release.
Never depend on an old staging directory surviving cleanup. Completed releases
must emit deployed.json only after all release checks pass. The installed
stroyka-release-cleanup timer finalizes eligible stages automatically.
