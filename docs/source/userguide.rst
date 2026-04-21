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


Launch Codix
^^^^^^^^^^^^^^
..
• Open the Terminal.
• Type the following command:

.. code-block:: bash

   ./codix

• A small window opens: Check that the displayed directory matches the desired folder.
• Click **OK**.  

Create a code file
~~~~~~~~~~~~~~~~~~~~
..
..
• In the menu bar: **Actions → Create a new code**
..
• Fill in the following fields:
   * *Name*: name of the code file.
   * *Description*: description of the code file.
   * *Code name*: name of the code (e.g., *movement*).
   * *List of items*: items associated with the code (e.g., *small*, *large*) 
      - Click **Record**.
   * *Recording site*: name of the site (e.g., *mother*).
      - Select the codes to assign to the site.
      - Click **Record**.
..
• Repeat the operation for as many codes, items, and recording sites as needed.
..
• Once the code file is complete: 
   * Click **Save all specifications and quit**.
   * Save the code file in the desired folder.

Start a new coding session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
..
• In the menu bar: **Actions → Start a new session**  
..
• Load the video:  

   - Click **Load** in the *Media file* section.

   - In the corresponding folder, select the video to code.
..
• Load the code file:  

   - Click **Load** in the *Code file* section.
 

   - In *File type*, select **Code file (*.cod)** or **New code (*.jod)** depending on the code.
 

   - In the corresponding folder, select the desired code file.

• The Codix window opens. Click **Play/Pause** to start the video.
..  
• Click **Play/Pause** again to stop the video as soon as coding can begin  
  (e.g., once the participants start speaking).
..
   
   ⚙️ Settings: 

      - In the field *By period of (..) sec.*, enter the coding interval (e.g., **2 sec** → the video will stop every 2 seconds).  
  
      - Tick the box to activate the interval.  
  
      - Click **Start processing**.  
  
      - Enter the coder’s first name.  
  
      - Restart the video using **Play/Pause**.
..
   
   🧩 Coding procedure: 

      - Code the first video segment.  
      - Click **Record**.  
      - A window opens: name the file.  
      - Repeat the following cycle: **Play/Pause → coding → Record**.
..

   ✏️ Edit previous codes:

      - Click **Back** as many times as needed to reach the desired segment.  
      - Click **Play/Pause** to restart the video.  
      - Correct the items if necessary.
      - Click **Record**.
..
   
   🔚 Exit session:  

      - In the menu bar: **Actions → Quit**.
..
   ..
Resume an unfinished coding session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
..
After launching Codix:  

   - In the menu bar: **Actions → Retrieve a session**.  

   - Click **Load** in *Data file*.  

   - In the corresponding folder, select the desired coding file: the video and coding window will open.  

   - Click **Start processing**.

   - Enter the first name of the coder who started coding the video: coding will resume from where it was left off.

Analyser guide
--------------

Launch codix analyser using the icon? or the command

.. code-block:: bash

   codix-analyser