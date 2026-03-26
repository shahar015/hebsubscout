#!/usr/bin/env python3
"""
Repository Generator
====================
Reads addon.xml from each addon directory, combines them into
addons.xml + addons.xml.md5, and copies zips into the repo structure.

Run this script after updating any addon:
    python generate_repo.py

This creates the /repo/ directory that GitHub Pages serves.
"""

import os
import sys
import hashlib
import zipfile
import xml.etree.ElementTree as ET

# Addons to include in the repository
ADDON_DIRS = [
    'repository.hebsubscout',
    'script.module.hebsubscout',
    'service.subtitles.hebsubscout',
    'plugin.video.hebscout',
    'context.hebsubscout',
]

REPO_DIR = 'repo'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def read_addon_xml(addon_dir):
    """Read and return the addon.xml content."""
    path = os.path.join(SCRIPT_DIR, addon_dir, 'addon.xml')
    if not os.path.exists(path):
        print('WARNING: {} not found'.format(path))
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def get_addon_id_version(addon_dir):
    """Parse addon ID and version from addon.xml."""
    path = os.path.join(SCRIPT_DIR, addon_dir, 'addon.xml')
    tree = ET.parse(path)
    root = tree.getroot()
    return root.attrib['id'], root.attrib['version']


def make_zip(addon_dir, addon_id, version, output_dir):
    """Create a Kodi-compatible zip for an addon."""
    zip_name = '{}-{}.zip'.format(addon_id, version)
    zip_path = os.path.join(output_dir, zip_name)
    
    source_dir = os.path.join(SCRIPT_DIR, addon_dir)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            # Skip hidden files/dirs and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for f in files:
                if f.startswith('.') or f.endswith('.pyc'):
                    continue
                full_path = os.path.join(root, f)
                # Archive path: addon_id/relative_path
                rel_path = os.path.relpath(full_path, source_dir)
                arc_path = os.path.join(addon_id, rel_path)
                zf.write(full_path, arc_path)
    
    print('  Created: {}'.format(zip_path))
    return zip_path


def generate():
    """Generate the full repository."""
    # Ensure repo dir exists
    repo_path = os.path.join(SCRIPT_DIR, REPO_DIR)
    os.makedirs(repo_path, exist_ok=True)
    
    # Collect addon XMLs
    addon_xmls = []
    
    for addon_dir in ADDON_DIRS:
        xml_content = read_addon_xml(addon_dir)
        if not xml_content:
            continue
        
        addon_id, version = get_addon_id_version(addon_dir)
        print('Processing: {} v{}'.format(addon_id, version))
        
        # Add to combined XML
        addon_xmls.append(xml_content)
        
        # Create addon subdirectory in repo
        addon_repo_dir = os.path.join(repo_path, addon_id)
        os.makedirs(addon_repo_dir, exist_ok=True)
        
        # Create zip
        make_zip(addon_dir, addon_id, version, addon_repo_dir)
        
        # Copy addon.xml to repo dir (Kodi reads this too)
        import shutil
        shutil.copy2(
            os.path.join(SCRIPT_DIR, addon_dir, 'addon.xml'),
            os.path.join(addon_repo_dir, 'addon.xml')
        )
    
    # Generate combined addons.xml
    combined = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    for xml in addon_xmls:
        # Remove XML declaration if present
        if xml.startswith('<?xml'):
            xml = xml[xml.index('?>') + 2:].strip()
        combined += xml + '\n'
    combined += '</addons>\n'
    
    addons_xml_path = os.path.join(repo_path, 'addons.xml')
    with open(addons_xml_path, 'w', encoding='utf-8') as f:
        f.write(combined)
    print('\nGenerated: {}'.format(addons_xml_path))
    
    # Generate MD5 checksum
    md5 = hashlib.md5(combined.encode('utf-8')).hexdigest()
    md5_path = os.path.join(repo_path, 'addons.xml.md5')
    with open(md5_path, 'w') as f:
        f.write(md5)
    print('Generated: {} ({})'.format(md5_path, md5))
    
    # Also create the repo zip at the root level (for first-time install)
    repo_id, repo_version = get_addon_id_version('repository.hebsubscout')
    root_zip = os.path.join(repo_path, '{}-{}.zip'.format(repo_id, repo_version))
    make_zip('repository.hebsubscout', repo_id, repo_version, repo_path)
    
    print('\n=== Repository generated successfully ===')
    print('Upload the /repo/ directory to GitHub Pages.')
    print('Users add source: https://hebsubscout.github.io/repository/')
    print('Then install: {}-{}.zip'.format(repo_id, repo_version))


if __name__ == '__main__':
    generate()
