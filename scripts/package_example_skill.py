"""Build the portable example Skill ZIP without including local caches."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
source = root / "skill_packages" / "low_valuation_screener"
destination = root / "skill_packages" / "low-valuation-screener-1.0.0.zip"
with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
    for path in sorted(source.iterdir()):
        if path.is_file():
            archive.write(path, path.name)
print(destination)
