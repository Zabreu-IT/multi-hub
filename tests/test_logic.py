import re
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.pop("OPENROUTER_API_KEY", None)
from worker.email_ai import generate_welcome_email

slug = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
assert slug.fullmatch("tour-de-montana")
assert not slug.fullmatch("bad slug")
assert "slots_available BETWEEN 0 AND slots_total" in Path("core/schema.sql").read_text()
assert "CREATE TABLE leads" in Path("core/schema.sql").read_text()
assert 'email: str = Field(pattern=r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")' in Path("api/routes/leads.py").read_text()
assert "ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata" in Path("api/main.py").read_text()
subject, body = generate_welcome_email({"business_name": "Hotel Sol"})
assert subject == "Bienvenido a Multi-Hub" and "Hola Hotel Sol" in body and 120 <= len(body.split()) <= 180
print("logic checks passed")
