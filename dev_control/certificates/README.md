# Scoped EIS trust

Public Russian Trusted Root CA downloaded via verified HTTPS from
https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt on 2026-10-19.
Official installation guidance: https://www.gosuslugi.ru/crt and
https://developers.sber.ru/help/certificates/how-to .
DER SHA-256: D26D2D0231B7C39F92CC738512BA54103519E4405D68B5BD703E9788CA8ECF31.

Used only in a disposable EIS browser's NSS database. The host's system trust,
Mac Keychain and existing Jev container are not modified. Each run verifies the
fingerprint. No global TLS error bypass. Expiry/hostname remain browser-verified.
The probe inherits the existing host's Chrome no-sandbox requirement but runs in
a separate unprivileged, read-only Docker container without provider credentials.
