"""Private stdin/stdout worker. No credentials, file paths or URLs in input."""
import io
import sys


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        # Production Linux supports an address-space cap. Darwin does not provide
        # an equivalent enforceable limit here; local fixtures use CPU/wall caps.
        if sys.platform == 'linux':
            resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
    except (ImportError, OSError, ValueError):
        return 3  # Fail closed when resource limits are unavailable.
    try:
        from pypdf import PdfReader
    except ImportError:
        return 3
    try:
        content = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            return 4
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            return 6
        if len(reader.pages) > 30:
            return 4
        if not reader.pages:
            return 2
        pages, total = [], 0
        for page in reader.pages:
            text = page.extract_text() or ''
            if not text.strip():
                return 5  # Do not silently omit scanned/empty pages.
            total += len(text) + (2 if pages else 0)
            if total > 64000:
                return 4
            pages.append(text)
        sys.stdout.buffer.write('\n\n'.join(pages).encode('utf-8'))
        return 0
    except MemoryError:
        return 4
    except Exception:
        return 2


if __name__ == '__main__':
    sys.exit(main())
