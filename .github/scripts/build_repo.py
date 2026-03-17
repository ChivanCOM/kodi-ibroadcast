"""
Builds the Kodi repository:
  - Regular addons: zips/<id>/<id>-<version>.zip
  - Binary addons:  zips/<id>/<id>-<version>+<platform>.zip  (one per platform)
  - Copies icon.png into each zips/<id>/ directory
  - Regenerates addons.xml and addons.xml.md5 at repo root
"""

import hashlib
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET

ROOT     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZIPS_DIR = os.path.join(ROOT, "zips")

# Per-platform config for binary addons.
# lib_src  = filename expected in the addon directory after CI build
# library  = filename to reference inside the zip's addon.xml
# kodi     = value for the <platform> tag understood by Kodi
BINARY_PLATFORMS = {
    "plugin.visualization.albumart": [
        {
            "tag":     "osx",
            "kodi":    "osx",
            "lib_src": "plugin.visualization.albumart.dylib",
            "library": "plugin.visualization.albumart.dylib",
        },
        {
            "tag":     "android",
            "kodi":    "android",
            "lib_src": "plugin.visualization.albumart.so",
            "library": "plugin.visualization.albumart.so",
        },
    ]
}

# All binary extensions — used to exclude "wrong platform" binaries from each zip
ALL_BIN_EXTS = {".dylib", ".so", ".dll"}

ADDON_DIRS = [
    d for d in os.listdir(ROOT)
    if os.path.isdir(os.path.join(ROOT, d))
    and os.path.exists(os.path.join(ROOT, d, "addon.xml"))
    and not d.startswith(".")
    and d != "zips"
]

SKIP_DIRS  = {"build", "build_android", "src", "__pycache__", ".git"}
SKIP_EXTS  = {".zip", ".cpp", ".h", ".sh"}
SKIP_FILES = {"CMakeLists.txt"}


def get_version(addon_dir):
    tree = ET.parse(os.path.join(ROOT, addon_dir, "addon.xml"))
    return tree.getroot().attrib["version"]


def _platform_addon_xml(addon_dir, pcfg, plat_version):
    """Return a modified addon.xml string for one platform."""
    tree = ET.parse(os.path.join(ROOT, addon_dir, "addon.xml"))
    root = tree.getroot()
    root.set("version", plat_version)

    for ext in root.findall("extension"):
        point = ext.get("point", "")

        if point == "xbmc.player.musicviz":
            # Replace all library_* with a single library= for this platform
            for attr in list(ext.attrib):
                if attr.startswith("library"):
                    del ext.attrib[attr]
            ext.set("library", pcfg["library"])

        elif point == "xbmc.addon.metadata":
            plat_el = ext.find("platform")
            if plat_el is None:
                plat_el = ET.SubElement(ext, "platform")
            plat_el.text = pcfg["kodi"]

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' \
           + ET.tostring(root, encoding="unicode") + "\n"


def _clean_dest_zips(dest_dir, addon_path):
    for d in [dest_dir, addon_path]:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".zip"):
                    os.remove(os.path.join(d, f))


def build_binary_zips(addon_dir):
    addon_path = os.path.join(ROOT, addon_dir)
    version    = get_version(addon_dir)
    dest_dir   = os.path.join(ZIPS_DIR, addon_dir)
    os.makedirs(dest_dir, exist_ok=True)
    _clean_dest_zips(dest_dir, addon_path)

    for pcfg in BINARY_PLATFORMS[addon_dir]:
        lib_path = os.path.join(addon_path, pcfg["lib_src"])
        if not os.path.exists(lib_path):
            print(f"  Skip {addon_dir}+{pcfg['tag']}: {pcfg['lib_src']} not found")
            continue

        plat_version = f"{version}+{pcfg['tag']}"
        zip_name     = f"{addon_dir}-{plat_version}.zip"
        zip_path     = os.path.join(dest_dir, zip_name)
        xml_content  = _platform_addon_xml(addon_dir, pcfg, plat_version)

        print(f"  Zipping {addon_dir} v{plat_version} -> zips/{addon_dir}/{zip_name}")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for dirpath, dirnames, filenames in os.walk(addon_path):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for filename in filenames:
                    if filename in SKIP_FILES:
                        continue
                    ext = os.path.splitext(filename)[1]
                    if ext in SKIP_EXTS:
                        continue
                    # Exclude binaries that belong to other platforms
                    if ext in ALL_BIN_EXTS and filename != pcfg["lib_src"]:
                        continue
                    full_path = os.path.join(dirpath, filename)
                    arcname   = os.path.relpath(full_path, ROOT)
                    if filename == "addon.xml" and dirpath == addon_path:
                        zf.writestr(arcname, xml_content)
                    else:
                        zf.write(full_path, arcname)

    icon_src = os.path.join(addon_path, "icon.png")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(dest_dir, "icon.png"))


def build_zip(addon_dir):
    addon_path = os.path.join(ROOT, addon_dir)
    version    = get_version(addon_dir)
    dest_dir   = os.path.join(ZIPS_DIR, addon_dir)
    os.makedirs(dest_dir, exist_ok=True)
    _clean_dest_zips(dest_dir, addon_path)

    zip_name = f"{addon_dir}-{version}.zip"
    zip_path = os.path.join(dest_dir, zip_name)

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
                arcname   = os.path.relpath(full_path, ROOT)
                zf.write(full_path, arcname)

    icon_src = os.path.join(addon_path, "icon.png")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(dest_dir, "icon.png"))


def build_addons_xml():
    addons_node = ET.Element("addons")

    for addon_dir in sorted(ADDON_DIRS):
        if addon_dir in BINARY_PLATFORMS:
            base_version = get_version(addon_dir)
            dest_dir     = os.path.join(ZIPS_DIR, addon_dir)
            for pcfg in BINARY_PLATFORMS[addon_dir]:
                plat_version = f"{base_version}+{pcfg['tag']}"
                zip_name     = f"{addon_dir}-{plat_version}.zip"
                if not (os.path.isdir(dest_dir) and
                        os.path.exists(os.path.join(dest_dir, zip_name))):
                    continue  # binary was not built

                tree = ET.parse(os.path.join(ROOT, addon_dir, "addon.xml"))
                root = tree.getroot()
                root.set("version", plat_version)
                for ext in root.findall("extension"):
                    if ext.get("point") == "xbmc.player.musicviz":
                        for attr in list(ext.attrib):
                            if attr.startswith("library"):
                                del ext.attrib[attr]
                        ext.set("library", pcfg["library"])
                    elif ext.get("point") == "xbmc.addon.metadata":
                        plat_el = ext.find("platform")
                        if plat_el is None:
                            plat_el = ET.SubElement(ext, "platform")
                        plat_el.text = pcfg["kodi"]
                addons_node.append(root)
        else:
            tree = ET.parse(os.path.join(ROOT, addon_dir, "addon.xml"))
            addons_node.append(tree.getroot())

    ET.indent(addons_node, space="  ")
    content = '<?xml version="1.0" encoding="UTF-8"?>\n' \
              + ET.tostring(addons_node, encoding="unicode") + "\n"

    with open(os.path.join(ROOT, "addons.xml"), "w", encoding="utf-8") as f:
        f.write(content)

    md5 = hashlib.md5(content.encode("utf-8")).hexdigest()
    with open(os.path.join(ROOT, "addons.xml.md5"), "w") as f:
        f.write(md5)

    print(f"  addons.xml written ({len(ADDON_DIRS)} addons), md5={md5}")


def build_index_html():
    addon_links = "\n".join(
        f'    <a href="zips/{d}/">{d}/</a><br>' for d in sorted(ADDON_DIRS)
    )
    root_html = f"""<!DOCTYPE html>
<html><body>
<h1>ChivanCOM Kodi Repository</h1>
{addon_links}
</body></html>
"""
    with open(os.path.join(ROOT, "index.html"), "w") as f:
        f.write(root_html)

    for addon_dir in ADDON_DIRS:
        dest_dir = os.path.join(ZIPS_DIR, addon_dir)
        os.makedirs(dest_dir, exist_ok=True)
        zips = sorted(f for f in os.listdir(dest_dir) if f.endswith(".zip")) \
               if os.path.isdir(dest_dir) else []
        zip_links = "\n".join(f'    <a href="{z}">{z}</a><br>' for z in zips)
        addon_html = f"""<!DOCTYPE html>
<html><body>
<h1>{addon_dir}</h1>
{zip_links}
</body></html>
"""
        with open(os.path.join(dest_dir, "index.html"), "w") as f:
            f.write(addon_html)

    print("  index.html files written")


if __name__ == "__main__":
    print("Building Kodi repository...")
    os.makedirs(ZIPS_DIR, exist_ok=True)
    for addon_dir in sorted(ADDON_DIRS):
        if addon_dir in BINARY_PLATFORMS:
            build_binary_zips(addon_dir)
        else:
            build_zip(addon_dir)
    build_addons_xml()
    build_index_html()
    print("Done.")
