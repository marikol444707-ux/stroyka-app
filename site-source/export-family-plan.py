"""Export view-only 2D footprints from the existing model's navigation data."""
from pathlib import Path
import hashlib,json
p=Path(__file__).parent
nav=json.loads((p/'navigation.json').read_text())
assert nav['modelSha256']==hashlib.sha256((p/'stroyka-polished.glb').read_bytes()).hexdigest(),'Navigation does not match current model'
geometry={'modelSha256':nav['modelSha256'],'rooms':nav['rooms'],'walls':[c for c in nav['colliders'] if c['group']=='03_walls'],'furniture':[c for c in nav['colliders'] if c['group']=='07_interior']}
(p/'family-plan-geometry.js').write_text('// Derived from navigation.json. Presentation only; no approved dimensions.\nexport const planGeometry='+json.dumps(geometry,ensure_ascii=False,separators=(',',':'))+';\n')
