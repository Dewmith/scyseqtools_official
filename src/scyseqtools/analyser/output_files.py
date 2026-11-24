"""Stage analyser outputs and publish them with explicit replacement permission."""

from dataclasses import dataclass
import errno
import os
from pathlib import Path
from shutil import copyfileobj
from tempfile import NamedTemporaryFile


@dataclass(frozen=True)
class SaveDestination:
    path: Path
    replace: bool = False


def output_path(folder, filename):
    name = Path(filename)
    if (not filename or filename == ".." or name.name != filename
            or any(char in filename for char in "/\\\x00")):
        raise ValueError("Enter a filename in the selected folder.")
    if os.name == "nt":
        is_reserved = getattr(os.path, "isreserved", None)
        if is_reserved is None:
            invalid = (name.is_reserved() or filename.endswith((".", " "))
                       or any(char in '<>:"|?*' or ord(char) < 32 for char in filename))
        else:
            invalid = is_reserved(filename)
        if invalid:
            raise ValueError("Enter a filename that Windows can use.")
    return Path(folder) / name


def write_lines(path, *, lines, newline=None):
    with path.open("w", encoding="utf-8", newline=newline) as stream:
        stream.writelines(lines)


def write_outputs(outputs):
    """Run all serializers before publishing the first output in this batch."""
    staged = []
    try:
        for destination, write in outputs:
            with NamedTemporaryFile(dir=destination.path.parent, prefix=".scyseq-",
                                    suffix=destination.path.suffix, delete=False) as stream:
                source = Path(stream.name)
            staged.append((source, destination))
            write(source)
        for source, destination in staged:
            if destination.replace:
                source.replace(destination.path)
            else:
                _publish_new(source, destination.path)
    finally:
        for source, _ in staged:
            source.unlink(missing_ok=True)


def _publish_new(source, destination):
    if os.name == "nt":
        source.rename(destination)  # Windows rename fails if the destination already exists.
        return
    try:
        os.link(source, destination)
    except OSError as exc:
        if exc.errno not in (errno.EOPNOTSUPP, errno.EPERM, errno.ENOSYS, errno.EMLINK):
            raise
        # Some filesystems do not support hard links. Exclusive creation still guards the name.
        with source.open("rb") as original:
            output = destination.open("xb")
            try:
                with output:
                    copyfileobj(original, output)
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
