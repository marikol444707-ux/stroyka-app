# S3 migration for uploads

This is a safe checklist for moving uploaded files from local `/uploads` to S3-compatible storage.

## Current rule

- Do not move or delete local `/uploads` until S3 is configured and verified.
- `backend/uploads` must stay as a symlink or compatibility path for old links.
- Run readiness checks before changing production storage mode.

## Required backend variables

Set these in `backend/.env` or systemd environment:

```env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://storage.yandexcloud.net
S3_BUCKET=your-bucket
S3_REGION=ru-central1
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_PREFIX=uploads
S3_PUBLIC_URL=
S3_ACL=public-read
```

`S3_PUBLIC_URL` is optional. Use it only when the bucket is served through a CDN or public domain.

## Readiness check

Before migration:

```bash
npm run smoke:s3-readiness
REQUIRE_S3=1 npm run smoke:s3-readiness
```

The first command is non-blocking and shows the current local uploads state. The second command must pass before real migration.

## Rollout sequence

1. Configure the bucket and credentials.
2. Run `REQUIRE_S3=1 npm run smoke:s3-readiness`.
3. Generate a new test upload through `/upload-photo`.
4. Check that the returned `fileUrl` points to S3 or the configured public URL.
5. Copy old local `/uploads` files to S3 preserving a clear prefix.
6. Keep local `/uploads` for rollback until the links are verified in the UI.
7. Only after verification, decide whether to keep local files as backup or archive them.

## Rollback

Set `STORAGE_BACKEND=local`, restart `stroyka`, and keep nginx serving `/uploads`.
