"""pytest kökü — `src/` düz yapıda (paket adı yok, bkz. ARCHITECTURE.md §12),
runtime'da `cd src && python main.py` ile çalıştığı için import kökü `src/`.
Testler repo kökünden koştuğunda aynı kökü sys.path'e ekliyoruz.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
