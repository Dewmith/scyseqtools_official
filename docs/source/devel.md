# Developer Guide

ScySeqTools provides two desktop apps for Windows and Linux. The Analyser uses
[Scyseq](https://github.com/scyseq-tools/scyseq) for symbolic sequence analysis.
See the [Python API reference](codedoc.rst) for the modules behind each app.

## Prerequisites

- Install Git and Python 3.9 or newer with Tk support. Check the interpreter with
  `python --version` (use `python3` on Linux if that is your interpreter name).
- On Windows, include Tcl/Tk when installing Python. For Encoder playback, use
  64-bit Python and install 64-bit VLC in its default location. In PowerShell,
  `Test-Path "C:\Program Files\VideoLAN\VLC\libvlc.dll"` should return `True`.
  [VLC for Windows](https://www.videolan.org/vlc/download-windows.html)
- On Ubuntu or Debian, install Tk and the Encoder's playback and media inspection
  libraries with `sudo apt install python3-tk vlc libmediainfo0v5`.

## Set up a checkout

Clone the repository and enter its root directory. If you use SSH, the clone
URL is `git@github.com:scyseq-tools/scyseqtools.git`.

```sh
git clone https://github.com/scyseq-tools/scyseqtools.git
cd scyseqtools
```

Check for Hatch with `hatch --version`. If needed, install it with
`python -m pip install hatch`. To keep Hatch environments in a shared directory,
you can set `storage.path` under `[envs]` in your Hatch configuration.
Start the default Hatch environment and install
the checkout in editable mode so source changes take effect on the next run.

```sh
hatch shell
python -m pip install -e .
```

To verify the installation, check the imported package path points into your
checkout and that both launchers import successfully.

```sh
python -c "import scyseqtools; print(scyseqtools.__file__)"
python -c "import scyseqtools.encoder.main; print('Encoder OK')"
python -c "import scyseqtools.analyser.main; print('Analyser OK')"
```

Run the following app, test, and packaging commands inside the Hatch shell.
Use `exit` to leave the environment.

## Run and test the apps

Run `scyseq-encoder` or `scyseq-analyser` to open the corresponding app. The
Encoder opens at its home screen. When recording a new session, the first
**Record** prompts for a project folder if one has yet to be selected during
this launch. See the {ref}`Encoder settings <encoder-settings>`
for configuration files and window layouts.

Run the test suite from the repository root:

```sh
python -m pytest tests
```

## Build and release desktop apps

The default Hatch environment includes PyInstaller. From the repository root,
run the specs for the operating system you are building on.

**Windows**

```powershell
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-encoder-windows.spec
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-analyser-windows.spec
```

**Ubuntu/Linux**

```sh
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-encoder-linux.spec
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-analyser-linux.spec
```

Local builds appear in `dist/` as `ScySeq Encoder.exe` and `ScySeq Analyser.exe`
on Windows, or `scyseq-encoder` and `scyseq-analyser` on Linux.

Pushing a version tag (for example, `v1.2.3`) triggers the Encoder and Analyser
workflows. Each builds both platforms, adds the tag to the executable name, and
publishes the archives and a per-app `SHA256SUMS` file to the same GitHub Release.
Actions retains the build artifacts for 14 days. Direct app users to the
[published releases](https://github.com/scyseq-tools/scyseqtools/releases).

## Build the documentation

From the repository root, run the same Sphinx HTML build as GitHub Pages:

```sh
hatch run docs:build
```

Open `docs/build/html/index.html` to inspect the site. Alternatively, from the
`docs` directory in the default Hatch shell, run `.\make.bat html` on Windows
or `make html` on Linux.

The HTML site uses `sphinxcontrib-mermaid` to render workflow diagrams in the
browser. To include an existing diagram in a reStructuredText page, reference
its source file in the directive:

```rst
.. mermaid:: _static/encoder_workflow.mmd
```

## Contribute

Fork the [official repository](https://github.com/scyseq-tools/scyseqtools),
create a branch for your change, and run the tests. For documentation changes,
also build the site and inspect the affected pages. Open a pull request
describing the change and how you checked it. Follow the project's
[Code of Conduct](https://github.com/scyseq-tools/scyseqtools/blob/main/CODE_OF_CONDUCT.md).
