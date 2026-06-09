"""Rename a pure-PyPI wheel with a platform-specific tag."""
import re
import sys
import zipfile
from pathlib import Path


def tag_wheel(wheel_path: Path, platform_tag: str) -> Path:
    stem = wheel_path.stem
    if not stem.endswith(".whl"):
        stem = wheel_path.name

    match = re.match(
        r"^(?P<package>[^-]+)-(?P<version>[^-]+)-(?P<python>[^-]+)-(?P<abi>[^-]+)-(?P<platform>.+)$",
        stem,
    )
    if not match:
        print(f"error: cannot parse wheel name: {wheel_path.name}", file=sys.stderr)
        sys.exit(1)

    new_name = (
        f"{match.group('package')}-{match.group('version')}"
        f"-{match.group('python')}-{match.group('abi')}"
        f"-{platform_tag}.whl"
    )
    new_path = wheel_path.with_name(new_name)

    with zipfile.ZipFile(wheel_path, "r") as zin:
        with zipfile.ZipFile(new_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.endswith("/WHEEL"):
                    text = data.decode("utf-8")
                    text = re.sub(
                        r"^Tag: .+$",
                        f"Tag: {match.group('python')}-{match.group('abi')}-{platform_tag}",
                        text,
                        flags=re.MULTILINE,
                    )
                    data = text.encode("utf-8")
                zout.writestr(info, data)

    wheel_path.unlink()
    print(f"tagged: {new_path.name}")
    return new_path


def main():
    if len(sys.argv) < 3:
        print("usage: python tag_wheel.py <dist_dir> <platform_tag>", file=sys.stderr)
        sys.exit(1)

    dist_dir = Path(sys.argv[1])
    platform_tag = sys.argv[2]

    for whl in dist_dir.glob("*.whl"):
        tag_wheel(whl, platform_tag)


if __name__ == "__main__":
    main()
