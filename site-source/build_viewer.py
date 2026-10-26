from pathlib import Path
import base64
p=Path(__file__).resolve().parent;h=(p/'viewer-template.html').read_text()
(p/'stroyka-materials.html').write_text(h+'<script id="model" type="application/octet-stream">'+base64.b64encode((p/'stroyka-polished.glb').read_bytes()).decode()+'</script><script>'+(p/'viewer.bundle.js').read_text()+'</script></html>')
(p/'index.html').write_text(h+'<script src="./viewer.bundle.js" defer></script></html>')
