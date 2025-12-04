User's guide
============

This is the user's guide

Installation
------------

The common requirements are `Python <https://www.python.org>`_ and 
`vlc <https://www.videolan.org/vlc/>`_

Then, *when avalaible on pypi*, the installation should reduce to:

.. code-block:: bash

   pip install codix

Initialisation (TODO)
---------------------

Test de subsubsection
^^^^^^^^^^^^^^^^^^^^^

Before using the encoder or the analyser, codix configuration has to be
initialised using:

.. code-block:: bash

   codix init

asks the following questions:

- Choose codix working directory (default: USER/codix_projects or
  USER/codix_wd):

- Choose theme (default: XXX)

  The themes are provided by the ttk-themes url?

- Other configurations?

Encoder guide
-------------

Editing test from Maissane

Launch codix encoder using the icon? or the command

.. code-block:: bash

   codix-encoder

1. Is it a new project?

   - if "Yes":

      * Define the structure of the project (**TODO**)
      * Define the coding frame of the project (newcode)

   - if "No":

      * Get project definitions: structure (**TODO**), coding frame
      * Start a new session?

        - if "No": resume session

            * Get session name and location in the project structure?
            * Get media from the defined place
            * Get metadata
            * Get data

        - if "Yes": start new session

            * Define session location in the project structure?
            * Define media (and save media in correct place **TODO**)

1. Launching Codix

Open the Terminal.
In the terminal, type:./codix
A small window opens (Choose working directory):
Check that the displayed directory corresponds to the desired one.
Click OK.

2. Creating a Code File

In the menu bar: Actions → Create a new code.
In Name, enter the name of the code file.
In Description, enter a description of the code file.
In Code name, enter the name of the code (example: movement).
In List of items, enter the items associated with the code (example: small, big, change). Click Record.
In Recording site, enter the name of the site (example: mother). Select the codes to assign to the site and click Record.
Once the code file is complete, click Save all specifications and quit.
Save the code file in the desired folder.

3. Starting a New Coding Session

In the menu bar: Actions → Start a new session.
Load the video:
Click Load in the Media file section.
In the corresponding folder, select the video to code.
Load the code file:
Click Load in the Code file section.
In the corresponding folder, select the desired code file.
In File type, select Code file (*.cod) or New code (*.jod) depending on the code.

4. Starting the Coding

In the Codix window, click Play/Pause to launch the video.
Click Play/Pause again to stop the video as soon as coding can begin (e.g., once the experimenter has closed the door).
Settings:
In the field By period of (..) sec., enter the time interval for coding.Example: 2 sec. → the video will stop every 2 seconds.
Tick the box to activate this time interval.
Click Start processing.
Enter the coder’s first name.
Restart the video with Play/Pause.
Coding:
Code the first video segment.
Click Record.
A window opens in the folder containing the chosen code: name the file.
Repeat the sequence: Play/Pause → code → Record.

5. Correcting or Going Back

If you need to modify a previous code:
Click Back as many times as needed to reach the desired segment.
Click Play/Pause to restart the video.
Correct the codes if necessary and click Record.

6. Quitting a Finished Session

To close the session: Actions → Quit.

7. Resuming an Unfinished Coding Session

Launch Codix:
Open the Terminal.
In the terminal, type:./codix
Check that the directory matches the desired one.
Click OK.
In the menu:
Actions → Retrieve a session.
Click Load in Data file.
In the corresponding folder, select the desired coding file: the video and coding window will open.
Click Start processing and enter the first name of the coder who started coding the video: coding will resume from where it was left off.

8. Common Issues and Solutions

Codix window not appearingWhen resuming a session, the Codix window may remain invisible.→ Solution: move the different open windows around until it appears.
Video playback bugThe video may stop completely or Play/Pause may become inactive.→ Solution: click Back several times.Note: previous codes may not have been saved. In that case, they must be re-entered before continuing.

9. Best Practices

Always check that the displayed directory matches the desired one before starting.
Do not multiply folders in the main directory: keep one folder for videos and one folder for codes.
Write down the last coded segment in a document to keep track in case of interruption or bug.
Check the names of saved files to avoid duplicates or session errors.
In case of repeated bugs, restart the software and, if necessary, the computer.
Keep a backup copy of coding files.

Analyser guide
--------------

Launch codix analyser using the icon? or the command

.. code-block:: bash

   codix-analyser
