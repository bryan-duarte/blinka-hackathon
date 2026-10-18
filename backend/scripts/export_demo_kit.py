"""Write the demo self-send kit (PDF, ZIP and XML files plus a README) to a folder.

Run (from backend/): uv run python -m scripts.export_demo_kit [--out ../samples/demo-kit]
"""

import argparse
import shutil
from datetime import UTC, datetime
from pathlib import Path

from contracts.demo import KitDestinations
from core.config import DemoSettings, GuardrailsSettings, KapsoSettings
from modules.demo.catalog import DEMO_SCENARIOS
from modules.demo.kit import README_NAME, render_kit_readme, scenario_kit_files

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "samples" / "demo-kit"


def export_kit(output_dir: Path) -> int:
    destinations = KitDestinations(
        email_address=DemoSettings().inbox_address,
        whatsapp_number=KapsoSettings().sandbox_display_number or None,
    )
    scenarios = list(DEMO_SCENARIOS)
    today = datetime.now(UTC).date()
    is_previous_kit = (output_dir / README_NAME).is_file()
    if output_dir.exists() and any(output_dir.iterdir()) and not is_previous_kit:
        raise SystemExit(f"Refusing to overwrite {output_dir}: it is not an exported demo kit.")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    readme = render_kit_readme(scenarios, destinations, GuardrailsSettings().enforce)
    (output_dir / README_NAME).write_text(readme, encoding="utf-8")
    file_count = 0
    for scenario in scenarios:
        for kit_file in scenario_kit_files(scenario, today):
            target = output_dir / kit_file.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(kit_file.content)
            file_count += 1
    print(f"Wrote {file_count} kit files and {README_NAME} to {output_dir}")
    return file_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    export_kit(parser.parse_args().out.resolve())


if __name__ == "__main__":
    main()
