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

If you already have coded sessions (`.cdx` files), you can
start with the Analyser.

**[Download the apps for Windows or Ubuntu](https://github.com/scyseq-tools/scyseqtools/releases/latest)**

## Download and open an app

Under **Assets** on the release page, download the archive for each app you
want. Both apps include Python. In the filenames below, `<version>` stands for
the version shown on the release page.

| Your computer | Encoder download | Analyser download |
| --- | --- | --- |
| Windows, 64-bit Intel/AMD | `ScySeqTools-Encoder-windows-x64-<version>.zip` | `ScySeqTools-Analyser-windows-x64-<version>.zip` |
| Ubuntu, 64-bit Intel/AMD (built on 22.04) | `ScySeqTools-Encoder-ubuntu-22.04-x64-<version>.tar.gz` | `ScySeqTools-Analyser-ubuntu-22.04-x64-<version>.tar.gz` |

**Windows**

1. If you are using the Encoder, install 64-bit VLC in its default folder, `C:\Program Files\VideoLAN\VLC`. [Download VLC for Windows](https://www.videolan.org/vlc/download-windows.html)
2. Right-click the downloaded ZIP and choose **Extract All**.
3. In the extracted folder, double-click `ScySeq Encoder <version>.exe` or `ScySeq Analyser <version>.exe`. Windows may hide the `.exe` ending.

**Ubuntu**

1. If you are using the Encoder, install VLC and MediaInfo by running `sudo apt install vlc libmediainfo0v5` in a terminal.
2. Right-click the downloaded archive and choose **Extract Here**.
3. Open a terminal in the extracted folder. Type `./scyseq-encoder-` or `./scyseq-analyser-`, press **Tab** to complete the versioned filename, then press **Enter**. If you see “Permission denied”, open the file’s **Properties → Permissions**, enable **Allow executing file as program**, and try again.

## Your first project

1. **Define your labels.** In the Encoder, choose **Define a new code** and enter a project name and description. For example, enter `movement` as the code name and `still, moving` as its list of items, then click **Record**. Add a recording site for the person or place you are observing, select `movement`, and click **Record** again. Choose **Save code** to save the `.jod` definition.
2. **Record a session.** From the home screen, choose **Start a new session**, load your recording and the `.jod` file, then click **Start processing** and enter your observer name. Play the recording, select a label, and click **Record**. The first time, choose a project folder when prompted and save the `.cdx` session file. Each subsequent **Record** updates that file.
3. **Resume later.** Choose **Retrieve a session** on the Encoder home screen, load the saved `.cdx` file, and click **Start processing**. Enter the same observer name to continue where you left off.
4. **See your results.** In the Analyser, click **Choose data directory** and open the folder containing your `.cdx` file. Highlight it under **Available files** and click **Select file(s)**. Open **Statistics**, highlight your site, and click **Select** to see its codes. Choose your code, click **Launch**, and choose an output folder. Open the resulting `.csv` in a spreadsheet to see the sequence length and label frequencies.

For other analyses and Encoder settings, read the [full user guide](https://scyseq-tools.github.io/scyseqtools/userguide.html).
If you need help, include your operating system, app version, and what happened in the [issue tracker](https://github.com/scyseq-tools/scyseqtools/issues).
