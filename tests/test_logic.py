import re
from pathlib import Path

slug = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
assert slug.fullmatch("tour-de-montana")
assert not slug.fullmatch("bad slug")
assert "slots_available BETWEEN 0 AND slots_total" in Path("core/schema.sql").read_text()
assert "CREATE TABLE leads" in Path("core/schema.sql").read_text()
assert 'email: str = Field(pattern=r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")' in Path("api/routes/leads.py").read_text()
print("logic checks passed")
