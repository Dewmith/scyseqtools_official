
this is a test for `leo_dev` branch in git

# Introduction {#sec-intro}

Behavioral sciences need tools to convert video recordings to data that
can be quantified. In this process they need tools that are simple and
efficient since the burden of behavioral sequences encoding is usually
heavy.

Although `Codix` has not been advertised earlier it has already been used in a
series of studies **cite all the studies that used Codix**. As an example we
will use the mother-infant interaction study as an illustration 


Codix has been inspired by the very first version of Cowlog
[@HanninenEtPastell09]. The other free software that we are aware of are:

- `cowlog` [@HanninenEtPastell09; @Pastell16]

- `BORIS` [@FriardEtGamba16]

- Video activity coder [@Braswell21]

- Simple video coder [@BartoEtAl17]

and there are also commercial software.

The Codix interface is deliberately very simple, even spartan. The sequence of
processing stages ares constraint to simple scenarios to avoid errors.

Codix Encoder is an adapted video player based on VLC

Codix Analyzer is a client-server architecture that serve analysis tools
based on the scikits/symbolic library.

[**Do we need to join scikits/symbolic to the paper!?**]{.sans-serif}

Coding is time consuming and people need simple tools that perform the
most basic operations.

The development philosophy is to provide a tool that do only one thing.

CODIX is based on the Python VLC bindings and the Tk-inter library.


# Codix suite description {#sec:1}

Codix suite is composed of:

- a video encoder `codix-encoder` which allows one to play a video and encode
  behaviors for regular time intervals[^Cont] into symbolic sequences.

- a symbolic sequence analyzer `codix-analyzer` which exposes the set of metrics
  implemented in the `scikits-symbolic` library to the used through a web
server. `codix-analyzer` can be run locally or remotely due to its client-server
architecture. 

[^Cont]: Shall we implement continuous encoding?

## `codix-encoder`

The initial interface of `codix-encoder` is very simple and allow only three
operations through the "Actions" menu (see **FigXX**):

1. Define a new encoding framework
2. Start a new coding session
3. Resume a previous coding session

The first option suppose that you have already defined an encoding framework.
If this is not the case, you can use the `New_code` application through the
`files` menu. The second option retrieve the encoding framework in the data
file.

We first describe the `New_code` application that allows one to define the
encoding framework of the study and then the encoder interface.

### New code

Before starting to encode a video, one needs to define a new coding framework for
the study. This can be done using  the `new code` application which can
be accessed through the main menu of the `encoder` window[^nc] (see Fig.XXX).

[^nc]: For the user able to launch individual python script, this application
    can also be used as a standalone tool.

**Figure for the New Code interface**

The first informations entered in the interface are the name of the project,
which will be used as the file name for saving the encoding definition and a
short description of the project. Both are mandatory.  Then the interface allows
one to define whether the encoding will be performed on the basis of regular
time intervals or on the basis of continuous events coding **Implement the
continuous event coding**. When regular coding is chosen the value of the time
interval (in seconds) can be entered.

The next frame of the interface allows one to define the set of coding
categories used in the study (named `codes`). User should give a name to the
category and define the items encoded in this code category. Items can be
separated by a space or `,-;:/`. Those items will constitute the alphabet of the
symbolic sequence associated with this encoding category. In our example, we
will encode...

The last frame allows one to define the recording "sites" (e.g. persons in a
family therapy session) and the codes categories associated to each of them. In
our example, the "sites" corresponds to the mother and the infant and we
associate bla bla codes with the mother and bla bla codes with the infant.

Technically, all the specifications: date and time of the definition,  name of
the project and its description, the  codes (and associated items)  and sites
(and associated codes) are recorded in a file with a json format derived from a
Python dictionary.  A human-readable report of the encoding frame in html format is also saved in
the same directory as the json file.

The format of the json file for the coding framework is as follows:
```{.json}
{'date': 'Mon Feb 13 08:02:19 2023', 
'project': 'The project of the year', 
'description': 'One of the best project of the year!', 
'interval': 10.0, 
'codes': {
    'code1': ['symb1', 'symb2', 'symb3'], 
    'code2': ['symb1', 'symb2', 'symb3']
}, 
'sites': {
    'site1': ['code1'], 
    'site2': ['code1', 'code2'], 
    'site3': ['code2']
}  
}  
```

It provides a versatile user interface which is dynamically built using
a code definition file. 

The code definition file can be either edited by
hand using a **yaml** syntax or constructed using a user interface
accessible from the CODIX main window.

Code definition file specifies:

-   temporal informations: regular (True, False not implemented) period
    and unit for the period

-   participants

-   encodings with their alphabets

-   comments: lines starting with `#` are considered as comments

Example of .jod file. In this file, the coding is regular
with a three-seconds period. The two participants are associated with
different sets of codes and their alphabets.</figcaption>

This file will be used to build a coding window adapted to the specific coding
of the study.

Symbolic sequences are series of letters taken from an alphabet

In the case of the mother-infant interaction study, for each 3 second section of
video recording, the maternal and infant behaviors within a dyad were coded by
the same rater but initial and reunion conditions were coded by independent
raters (Feldman, 2007; Pezard et al., 2017; Tronick, Als, & Brazelton, 1980).

Maternal behaviors were encoded according to three categories:

-   Verbal behaviors. Mothers' verbal behavior was divided into three
    categories (Fonagy, 2011; Gros-Louis, West, Goldstein, & King, 2006;
    Stacks et al., 2014): silence, reflective verbalization, and
    vocalizations/verbalizations. 

-   Motor behaviors. Mothers' motor behavior was divided into three
    categories (Granat et al., 2017; Mantis, Stack, Ng, Serbin, &
    Schwartzman, 2014): no movement, touch, and movement without
    physical contact.

-   Gaze behaviors. Mothers' gaze behavior referred to direction of gaze
    and was divided in two categories (Kim, Fonagy, Koss, Dorsett, &
    Strathearn, 2014; Lotzin, Schiborr, et al., 2015): gaze toward
    infant and gaze away (i.e. when the mother gazed away from the
    infant's face and did not gaze toward him/her).

For the infants, vocal behaviors were divided into three categories
(Feldman, 2003): silence, vocalizations and negative vocal behaviors.
Vocalizations category corresponded to positive and neutral
vocalizations. Negative vocal behaviors category corresponded to crying,
screaming and fussing. Vegetative sounds (i.e. burp, hiccup, cough,
yawn, heavy breathing) were excluded. Motor behaviors (i.e. movement and
no movement) and direction of gaze (i.e. gaze toward mother and gaze
away) were also coded. Vocal behaviors, motor behaviors and direction of
gaze were taken into account to describe a global state of behavioral
involvement (see Table 1) divided into three levels of global behavioral
involvement (i.e. low, moderate and high) on a continuum from
disengagement to engagement in the interaction (Feldman, Greenbaum, &
Yirmiya, 1999; Tronick et al., 1980).

As a result, infants' and mothers' behaviors were associated with a
symbolic sequence encoded according to the respective categories of
behavior. For each maternal behavior i.e. verbal behavior, motor
behavior and gaze, we thus considered two symbolic sequences $x_{t}$ and
$y_{t}$ for mother $X$ and infant $Y$ encoded according to alphabets
$A = \{\alpha_{0},\cdots,\alpha_{k - 1}\}$ and
$B = \{\beta_{0},\beta_{1},\beta_{2}\}$ respectively, where each symbol
represents a category of behavior for the mother i.e. {silence,
reflective verbalization, verbalization} for mothers' verbal behavior,
{no movement, touch, movement without physical contact} for mothers'
motor behavior and {toward infant, away} for mothers' gaze behavior and
a level of behavioral involvement for the infant i.e. {low, moderate,
high} for infants' global behavioral involvement.

### Encoder interface and process

In case 1, you are supposed to start a new encoding session so the next
step is to load either a video or a code file but loading a data file is
disabled.

In case 2, since all the information are present in the data file (names of the
code file and of the video file), all the files are loaded at once (if they
exist).

When at least 2 of the 3 elements are presents (at least code and video and
perhaps data) the interface appear with 4 frames: one for the file names, one
controller for the video, one for the codes and one for playing the video.

Before coding starts, one can explore the video using the buttons of the
controller either continuously or using a time step which can be defined in the
controller window (frame?). 

The code frames is built according to the code file and thus provide an adapted
interface for each project with different coding framework.

When one starts coding, several options are frozen. During the encoding process,
one can go back to check the encoding. The software also checks that all the
codes are entered before processing.

Data are stored in a json file according to the illustrated file in FigXX.

```{.json}

{"history": [["Sat Jan 14 12:03:01 2023", "CC", ""]], 
"media": "/home/Student/Desktop/Study/videos/S2650002.MP4", 
"code": "/home/Student/Desktop/Study/Codes/6persoSis.cod", 
"times": [0, 10000, 20000, 30000, 40000, 50000],
"comments": ["", "", "", "", ""],
 "regular": true, "period": 10.0, "t_unit": "second", 
"data": {"Mere": 
{"Emotion": {"dico": {"0": "Neutre", "1": "Pos", "2": "Neg"}, 
             "seq": [0, 2, 0, 2],
```



