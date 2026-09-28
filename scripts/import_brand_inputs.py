"""Copy task-private uploads for the unprivileged bootstrap user."""
import os
import shutil
from pathlib import Path
root = Path(__file__).resolve().parent.parent
for name in ['LOGO_FILE','HERO_IMAGE']:
    if os.environ.get(name):
        source = Path(os.environ[name])
        if source.stat().st_size > 10 * 1024 * 1024: raise ValueError('Brand images must be under 10 MB')
        shutil.copyfile(source, root/'.private'/name.lower())
