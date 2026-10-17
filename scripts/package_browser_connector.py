"""Package only the reviewed local extension assets, never runtime data."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    root=Path(__file__).resolve().parents[1]
    source=root/'deploy/browser-connector'
    manifest=json.loads((source/'manifest.json').read_text())
    assert set(manifest['permissions']) == {'activeTab','scripting','storage'}
    assert not manifest.get('host_permissions') and not manifest.get('externally_connectable')
    files=['manifest.json','background.js','reader.js','collector.js','popup.html','popup.js']
    destination=root/'dist/outreach-browser-connector.zip'
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(source/name,name)
        archive.write(root/'docs/BROWSER_CONNECTOR.md','SETUP.md')
    with ZipFile(destination) as archive:
        assert archive.testzip() is None and set(archive.namelist())==set(files+['SETUP.md'])
    print(f'Browser connector packaged: {destination} (7 files; not installed)')


if __name__=='__main__':
    main()
