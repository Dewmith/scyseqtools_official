---
title: Encoder description
---

## Structure of the encoder

The encoder is a GUI that commands VLC player and favors the encoding of a video.

`encoder`
  : this is the main script which is the enter point of the codix-encoder software
     
`applicationmenu.py`
  : the menu of the application (a very simple menu since the software is simple on purpose).

`codingframe.py`
  : the part of the interface which is dynamically built using an encoding definition read in a `.cod` file

`ib.py`
  : this is an old file and **I think this file should disappear** 

`infoframe.py`
  : the frame which displays the informations about the code file (`.cod`), media file and data file (`ext?`).

`playercontrol.py`
  : the file where the functions that command the VLC player should be grouped (not done in the codix3.0.1...)

`utils.py`
  : I think this file does not have any further used function **Check this**.

`newcode.py`
  : an independent application which can be launched from the main `encoder` script
 
 `htmlreport.py`
  : the templates for the html report  after a new code has been defined.

# Scenarios

One suppose that only three scenarios are possible:

1. "Define a new code"
2. "Start a new session" (if this scenario is not continued until actual coding
   begins then is in fact a "free media viewing" scenario)
3. "Resume session" (this is a very important scenario to allow the encoding
   persons to stop coding and resume since this is a very long process.) 

# Variables

We try to keep the number of important variables to the minimum. Right now, we
have:

- `media_loaded`
- `code_loaded`
- `data_loaded` (is this the same as `recording` or `processing`?)
- `player_mode`
- `period`
- `max_time`
- `current_time`
- `min_time`
- `max_step`
- `current_step`
(Note that `min_step`$=0$...)

What about `start_processing` and `data_loaded`?

**To Do:**

1. A table with the evolution of the values of the variables during the
course of each scenario (2 tables)

2. Write above the type of the variables and their possible values and an
   explanation of their use

3. Define (with a graph) the indices of the data related to the player time and
   processing step. 


