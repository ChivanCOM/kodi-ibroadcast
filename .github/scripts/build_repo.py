"""
Builds the Kodi repository:
  - Creates zips/<addon-id>/<addon-id>-<version>.zip for every addon
  - Copies icon.png into each zips/<addon-id>/ directory
  - Regenerates addons.xml and addons.xml.md5 at repo root
"""

import hashlib
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZIPS_DIR = os.path.join(ROOT, "zips")

ADDON_DIRS = [
    d for d in os.listdir(ROOT)
    if os.path.isdir(os.path.join(ROOT, d))
    and os.path.exists(os.path.join(ROOT, d, "addon.xml"))
    and not d.startswith(".")
    and d != "zips"
]


def get_version(addon_dir):
    tree = ET.parse(os.path.join(ROOT, addon_dir, "addon.xml"))
    return tree.getroot().attrib["version"]


def build_zip(addon_dir):
    version = get_version(addon_dir)
    zip_name = f"{addon_dir}-{version}.zip"

    # Destination: zips/<addon-id>/
    dest_dir = os.path.join(ZIPS_DIR, addon_dir)
    os.makedirs(dest_dir, exist_ok=True)

    # Remove existing zips in dest (always rebuild fresh)
    for f in os.listdir(dest_dir):
        if f.endswith(".zip"):
            os.remove(os.path.join(dest_dir, f))

    # Remove stale zips left in the addon dir itself (old structure cleanup)
    addon_path = os.path.join(ROOT, addon_dir)
    for f in os.listdir(addon_path):
        if f.endswith(".zip"):
            os.remove(os.path.join(addon_path, f))

    zip_path = os.path.join(dest_dir, zip_name)

    SKIP_DIRS  = {"build", "build_android", "src", "__pycache__", ".git"}
    SKIP_EXTS  = {".zip", ".cpp", ".h", ".sh"}
    SKIP_FILES = {"CMakeLists.txt"}

    print(f"  Zipping {addon_dir} v{version} -> zips/{addon_dir}/{zip_name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(addon_path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for filename in filenames:
                if filename in SKIP_FILES:
                    continue
                if os.path.splitext(filename)[1] in SKIP_EXTS:
                    continue
                full_path = os.path.join(dirpath, filename)
                arcname = os.path.relpath(full_path, ROOT)
                zf.write(full_path, arcname)

    # Copy icon.png so Kodi's browser can show it
    icon_src = os.path.join(addon_path, "icon.png")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(dest_dir, "icon.png"))


def build_addons_xml():
    addons_node = ET.Element("addons")
    for addon_dir in sorted(ADDON_DIRS):
        tree = ET.parse(os.path.join(ROOT, addon_dir, "addon.xml"))
        addons_node.append(tree.getroot())

    ET.indent(addons_node, space="  ")
    content = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        addons_node, encoding="unicode"
    ) + "\n"

    with open(os.path.join(ROOT, "addons.xml"), "w", encoding="utf-8") as f:
        f.write(content)

    md5 = hashlib.md5(content.encode("utf-8")).hexdigest()
    with open(os.path.join(ROOT, "addons.xml.md5"), "w") as f:
        f.write(md5)

    print(f"  addons.xml written ({len(ADDON_DIRS)} addons), md5={md5}")


def build_index_html():
    """Generate index.html files so Kodi's HTTP browser can navigate the repo."""
    addon_links = "\n".join(
        f'    <a href="zips/{d}/">{d}/</a><br>' for d in sorted(ADDON_DIRS)
    )
    root_html = f"""<!DOCTYPE html>
<html><body>
<h1>iBroadcast Kodi Repository</h1>
{addon_links}
</body></html>
"""
    with open(os.path.join(ROOT, "index.html"), "w") as f:
        f.write(root_html)

    for addon_dir in ADDON_DIRS:
        version = get_version(addon_dir)
        zip_name = f"{addon_dir}-{version}.zip"
        addon_html = f"""<!DOCTYPE html>
<html><body>
<h1>{addon_dir}</h1>
    <a href="{zip_name}">{zip_name}</a><br>
</body></html>
"""
        dest_dir = os.path.join(ZIPS_DIR, addon_dir)
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, "index.html"), "w") as f:
            f.write(addon_html)

    print("  index.html files written")


if __name__ == "__main__":
    print("Building Kodi repository...")
    os.makedirs(ZIPS_DIR, exist_ok=True)
    for addon_dir in sorted(ADDON_DIRS):
        build_zip(addon_dir)
    build_addons_xml()
    build_index_html()
    print("Done.")
