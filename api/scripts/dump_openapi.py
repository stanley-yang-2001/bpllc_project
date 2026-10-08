"""Write the OpenAPI schema to a file (no database needed). Used by `npm run gen:api` / `make gen-api`."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tutor_core"))

from app.config import Settings          # noqa: E402
from app.main import create_app          # noqa: E402

app = create_app(Settings(database_url="unused", jwt_secret="x" * 40, bcrypt_rounds=4, run_migrations=False))
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
print(f"wrote {out}")
