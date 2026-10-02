"""引用地图（可选，pip install citation-map）。

CitationMap 内部用多进程和 Selenium，遇到验证码会弹出 Chrome 并在终端等待回车，
所以放在子进程里运行（继承启动服务的终端），不影响 Web 服务本身。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = "citation_map.html"


class CitationMapError(Exception):
    code = "map_failed"


def available():
    return importlib.util.find_spec("citation_map") is not None


def generate(scholar_id, out_dir, progress=None):
    if progress:
        progress("map")
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([sys.executable, "-m", "backend.citemap", scholar_id, str(out_dir)], cwd=ROOT)
    if proc.returncode != 0 or not (out_dir / HTML).exists():
        raise CitationMapError(f"citation-map exited with code {proc.returncode}")


if __name__ == "__main__":
    from citation_map import generate_citation_map

    sid, out = sys.argv[1], Path(sys.argv[2])
    generate_citation_map(sid, output_path=str(out / HTML), csv_output_path=str(out / "citation_info.csv"),
                          cache_folder=str(out / "cache"), print_citing_affiliations=False)
