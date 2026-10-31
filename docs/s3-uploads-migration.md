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

## Private-access audit

Before changing the bucket to private or changing any object ACL, run the
read-only audit below. It reports counts for the object ACL, unauthenticated
HTTP access through the S3 endpoint and configured public URL bases, and
authenticated application access. It does not print URLs or object keys and
does not write to S3 or the database.

```bash
python3 scripts/audit_s3_anonymous_access.py --limit 5
```

After the sample is understood, run without `--limit` for the complete
registered-file inventory. A private object ACL is not sufficient evidence by
itself: anonymous HTTP access must also be denied. The report covers objects
registered in `file_ownership`; reconcile the S3 reference cutover report and
Timeweb bucket policy before switching the bucket to private.

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
