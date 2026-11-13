<h1 align="center">ScySeqTools</h1>

<p align="center">
  <a href="https://www.sphinx-doc.org/"><img src="https://img.shields.io/badge/docs-Sphinx-blue" alt="docs: Sphinx"></a>
  <a href="https://docs.pytest.org/"><img src="https://img.shields.io/badge/tests-pytest-blue" alt="tests: pytest"></a>
  <a href="https://hatch.pypa.io/latest/"><img src="https://img.shields.io/badge/project-Hatch-blue" alt="project: Hatch"></a>
  <a href="https://docs.python.org/3/library/doctest.html"><img src="https://img.shields.io/badge/tests-doctest-blue" alt="tests: doctest"></a>
</p>

ScySeqTools provides desktop applications for researchers and observers who
study behaviour using recordings. It helps turn recorded observations into
structured data that can be saved, compared, and analysed to investigate
behavioural patterns.

In this context, **coding** means systematically assigning labels to observed
behaviours. Observers use a **coding scheme**: a defined set of categories and
rules describing what each label means and when to apply it. Clear definitions
help different observers apply the labels consistently. Recording these labels
over time creates a sequence of observations for analysis. This approach is
described in the research guidelines for
[systematic coding of observed human behaviour](https://link.springer.com/article/10.1007/s11135-024-01969-9).

ScySeqTools supports this workflow through two graphical applications. The
**Encoder** lets you define your labels and record observations while reviewing
media. The **Analyser** works with the resulting coded sequences to summarise
label frequencies, examine transitions and relationships between sequences, and
assess agreement between observers. No programming is required to use the apps.

**[Download the apps](https://github.com/scyseq-tools/scyseqtools/releases/latest)**
| [For users](#for-users) | [For developers](#for-developers)

## For users

### Choose your app

| App | What you can do |
| --- | --- |
| **Encoder** | Watch recordings and record behaviour labels. |
| **Analyser** | Examine coded data, compare observers, and export results. |

Use both apps to go from a recording to analysis results. If you already have
coded ScySeqTools data, you can start with the Analyser.

The Analyser uses **Scyseq**, the analysis package that provides the calculations
for working with coded behaviour sequences. Visit the
[Scyseq website](https://scyseq-tools.github.io/scyseq/) to learn more about its
analysis methods.

### Download the apps

1. Open the **[latest release](https://github.com/scyseq-tools/scyseqtools/releases/latest)**
   from the official ScySeqTools project.
2. Scroll to **Assets** and expand it if the files are hidden.
3. Choose **Encoder**, **Analyser**, or download both, using the table below to
   match your computer. Each app is a separate download.
4. Save the archive, then extract it: on Windows, right-click the `.zip` file
   and choose **Extract All**; on Ubuntu,
   right-click the `.tar.gz` file and choose **Extract Here**.
5. Open the extracted app as described in [Open an app](#open-an-app).

Download filenames start with `ScySeqTools-Encoder-` or `ScySeqTools-Analyser-`,
followed by the platform and version:

| Your computer | Filename ending to choose |
| --- | --- |
| Windows, 64-bit Intel/AMD | `windows-x64-<version>.zip` |
| Ubuntu Linux, 64-bit Intel/AMD (built on Ubuntu 22.04) | `ubuntu-22.04-x64-<version>.tar.gz` |

For example, `ScySeqTools-Encoder-windows-x64-v0.0.2.zip` is the Windows Encoder.
The version changes with each release.

The **Source code (zip)** and **Source code (tar.gz)** links contain project
files for developers. Choose the named app archives above to run the apps.
The `SHA256SUMS` text files are optional download checksums, not applications.

### Before opening the Encoder

The downloaded apps include Python, so you do not need to install Python or
Hatch. The **Encoder also requires [VLC media player](https://www.videolan.org/vlc/)**,
which is installed separately. The Analyser does not require VLC.

- **Windows:** install [64-bit VLC](https://www.videolan.org/vlc/download-windows.html)
  in its default location, `C:\Program Files\VideoLAN\VLC`.
- **Ubuntu:** install VLC through your software manager. The Encoder also uses
  the MediaInfo system library; you can install both from a terminal with
  `sudo apt install vlc libmediainfo0v5`.

### Open an app

Open the files in the **extracted folder**, rather than inside the archive.
In the names below, `<version>` means the release version, such as `v0.0.2`.

- **Windows:** double-click `ScySeq Encoder <version>.exe` or
  `ScySeq Analyser <version>.exe`. Windows may hide the `.exe` ending.
- **Ubuntu/Linux:** the files are `scyseq-encoder-<version>` and
  `scyseq-analyser-<version>`. If needed, enable **Allow executing file as program**
  in the file's **Properties > Permissions** (wording varies by file manager).
  Open a terminal in the extracted folder and run `./scyseq-encoder-v0.0.2` or
  `./scyseq-analyser-v0.0.2`, replacing `v0.0.2` with the downloaded version.

### Your first project

1. **Choose a project folder.** Open the Encoder and select a folder for your
   work, such as `My observation project`. It uses or creates `media` and `data`
   folders inside it. Put your recordings in `media`.
2. **Define your behaviour labels.** Choose **Actions > Define a new code**.
   Enter your project details, add code names and their possible labels (for
   example, `movement` with `still` and `moving`), and click **Record** for each.
   Add recording sites for the people or places you observe, select their codes,
   and click **Record**. Click **Save code** to save the `.jod` definition in `data`.
3. **Record observations.** Choose **Actions > Start a new session**. Load a
   recording and your `.jod` file, click **Start processing**, and enter your
   observer name. Play the recording, select the appropriate labels, and click
   **Record** as you work. The first record asks you to save a `.cdx` session file;
   save it in `data`. Later records update that file.
4. **Analyse your data.** Open the Analyser, click **Choose data directory**, and
   select your project's `data` folder. Select your `.cdx` files under
   **Available files**, then click **Select file(s)**. Choose an analysis tab,
   select the relevant sites and codes, and click **Launch** or **Compute kappa**.
   Choose an output folder when prompted. Table results are saved as `.csv`
   files, which you can open in a spreadsheet app.

To continue an unfinished coding session, use **Actions > Retrieve a session**
in the Encoder and select its `.cdx` file.

For detailed instructions and explanations of the analysis tabs, read the
**[full user guide](https://scyseq-tools.github.io/scyseqtools/userguide.html)**.
For help or to report a problem, use the
[upstream issue tracker](https://github.com/scyseq-tools/scyseqtools/issues).
Include your operating system, app version, and what happened.

<details>
<summary>Advanced: Encoder configuration and window layout</summary>

On first run, the Encoder creates an editable configuration file in your
operating system's user config folder:

```text
Windows: %APPDATA%\ScySeqTools\Encoder\config.ini
Ubuntu/Linux: ~/.config/ScySeqTools/Encoder/config.ini
```

The app loads configuration in this order; later settings override earlier ones:

1. Bundled defaults inside the package or app.
2. The user-editable OS config file shown above.
3. A `config.ini` in the selected project folder, if present.

Use the user config file to change your defaults, or a project's `config.ini`
to change settings for that project. The last selected project folder is
remembered in:

```text
Windows: %APPDATA%\ScySeqTools\Encoder\cwdfile.ini
Ubuntu/Linux: ~/.local/state/ScySeqTools/Encoder/cwdfile.ini
```

By default, the Encoder uses a single window. To open separate Information,
Control, and Coding framework windows, add this to your user or project
`config.ini`, under the existing `[application]` section if it is present:

```ini
[application]
encoder_layout = detached
```

Use `encoder_layout = embedded` to return to the single-window layout.

</details>

## For developers

ScySeqTools uses [Scyseq](https://github.com/scyseq-tools/scyseq) as its symbolic
sequence analysis library. This checkout supports development and local app
builds on Windows and Linux.

Project resources: [upstream repository](https://github.com/scyseq-tools/scyseqtools),
[issue tracker](https://github.com/scyseq-tools/scyseqtools/issues), and
[documentation](https://scyseq-tools.github.io/scyseqtools/).

### Requirements

- Python 3.9 or newer
- Hatch, used to create and manage the development virtual environment
- VLC 64-bit, required by the encoder through `python-vlc`
- `tkinter`
  - Windows: included with the standard Python installer
  - Ubuntu/Debian: `sudo apt install python3-tk`
- Ubuntu/Debian Encoder system library: `sudo apt install libmediainfo0v5`

On Windows, install 64-bit VLC from:

[VLC for Windows](https://www.videolan.org/vlc/download-windows.html).

After installing VLC, this file should exist:

```powershell
Test-Path "C:\Program Files\VideoLAN\VLC\libvlc.dll"
```

### Starter setup

Clone or download the project, then open a terminal in the project folder.
On Windows, use PowerShell; on Linux, use your usual terminal.

```sh
cd path/to/scyseqtools
```

Replace `path/to/scyseqtools` with the folder where you cloned or downloaded
the project.

#### 1. Check Python

```sh
python --version
```

You should see Python 3.9 or newer.

#### 2. Check whether Hatch is installed

```sh
hatch --version
```

If your terminal says `hatch` is not found or not recognized, install it:

```sh
python -m pip install hatch
```

Then check again:

```sh
hatch --version
```

#### 3. Create and enter the Hatch environment

From the project root, run:

```sh
hatch shell
```

Your prompt should now start with something like:

```text
(scyseqtools) ...
```

That means you are inside the ScySeqTools virtual environment.

#### 4. Install ScySeqTools in editable mode

Inside the Hatch shell, install the current project:

```sh
python -m pip install -e .
```

The `-e` option means "editable": Python imports ScySeqTools directly from this source
folder, so local code changes are picked up without reinstalling every time.

#### 5. Verify the install

```sh
python -m pip show scyseqtools
python -c "import scyseqtools; print(scyseqtools.__file__)"
python -c "import scyseqtools.encoder.main; print('ok')"
python -c "import scyseqtools.analyser.main; print('ok')"
```

If both app import checks print `ok`, the package imports work.

### Run ScySeqTools from source

Inside the Hatch shell:

```sh
scyseq-encoder
```

or:

```sh
scyseq-analyser
```

The encoder opens a graphical interface and asks you to choose a working
directory. ScySeqTools expects or creates `media` and `data` folders inside that
working directory.

Configuration paths, override order, and window layouts are documented in the
**Advanced: Encoder configuration and window layout** subsection under
[For users](#for-users).

### Build applications locally

From the project root, install build dependencies:

```powershell
python -m pip install -e ".[dev,build]"
```

Then run the spec for your OS:

```powershell
# Windows
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-encoder-windows.spec
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-analyser-windows.spec
```

```sh
# Ubuntu/Linux
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-encoder-linux.spec
pyinstaller --clean --noconfirm packaging/pyinstaller/scyseq-analyser-linux.spec
```

Local builds are written to `dist/`, using the unversioned names
`ScySeq Encoder.exe` and `ScySeq Analyser.exe` on Windows, or `scyseq-encoder`
and `scyseq-analyser` on Linux.

The Encoder and Analyser GitHub Actions workflows run on version tags, build
both platforms, add the tag to the app filenames, and create or update a GitHub
Release with the app archives and separate Encoder/Analyser `SHA256SUMS` files.
Actions artifacts are also kept for 14 days. Direct users to
[GitHub Releases](https://github.com/scyseq-tools/scyseqtools/releases), where
the published apps are available without relying on temporary Actions artifacts.

### Run tests

Inside the Hatch shell:

```sh
python -m pytest tests
```

### Build the documentation

The documentation is built with Sphinx.

First enter the Hatch environment from the project root:

```sh
hatch shell
```

Then navigate to the docs folder and build the HTML files:

**On Windows:**

```powershell
cd docs
.\make.bat html
```

**On Linux:**

```bash
cd docs
make html
```

The generated HTML documentation will be available in `docs/build/html/`. Open `docs/build/html/index.html` in your browser to view the documentation.

### Contributing

Contributions to ScySeqTools are welcome!

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) when participating in
the ScySeqTools community.

To contribute:

1. Fork the official repository: [github.com/scyseq-tools/scyseqtools](https://github.com/scyseq-tools/scyseqtools).
2. Create a branch for your feature or bug fix.
3. Submit a pull request with a clear description of changes.
4. Ensure tests pass.
