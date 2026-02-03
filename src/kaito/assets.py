from pathlib import Path

import yaml

project_dir: Path = Path(__file__).parent.parent.parent.absolute()


with open(project_dir / "assets" / "openai_models.yaml", "r") as file:
    MODEL_INFO_DATA = yaml.safe_load(file)


with open(project_dir / "assets" / "openai_tools.yaml", "r") as file:
    BUILT_IN_TOOLS_INFO = yaml.safe_load(file)
