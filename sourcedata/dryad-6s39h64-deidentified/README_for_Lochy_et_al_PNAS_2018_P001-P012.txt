READ ME:

This data set is associated with the following manuscript published in PNAS (2018):

Title:
Selective visual representation of letters and words in the left ventral occipito-temporal cortex with intracerebral recordings.

Authors: 
Aliette Lochy, Corentin Jacques,Louis Maillard, Sophie Colnat-Coulbois, Bruno Rossion, Jacques Jonas.



--- 1. Electrophysiological data ---

Each folder contains the data from one participant. The data consist in recordings of intracerebral EEG in epileptic patient viewing visual stimuli. Each channel corresponds to the recording (i.e. voltage over time) of one intracerebral contact and additional physiological markers (e.g. ECG). 

In each folder there is data from three conditions (see file name): 
1. VC-W: periodic presentation of words (at 2 Hz) among pseudo-fonts presented at 10 Hz.
2. NW-W: periodic presentation of words (at 2 Hz) among non-fonts presented at 10 Hz.
3. PW-W: periodic presentation of words (at 2 Hz) among pseudo-words presented at 10 Hz.

Each condition consist of two files (.mat and .lw5) that can be open in Letswave 5, a free software for EEG data analysis (http://www.nocions.org/letswave/) running on Matlab. 

Prior to this step, sEEG data (TRC files, Micromed) have been pre-processed in the following way:

1. Imported in Letswave 5, which has been used for the subsequent steps
2. Low-pass filtered with a cut-off at 40Hz using a butterworth low-pass filter (Order 4)
3. Each recording sequence was segmented from 2 seconds after the onset of the sequence until ~68 seconds, so that the number of bins in the segmented sequence allows an exact integer number of cycles of the 2Hz word frequency (˜66 s). 
4. Sequences corresponding to the same condition (e.g. PW-W) were merged in the same file. 


Further data transform and analyses (FFT, etc.) have not been performed.


Letswave files can be open in Matlab without 'Letswave'. They consist of one header file (the .lw5 file) and one data file (the .mat file). 
The dimensions of the 'data' variable are organized as follow:

-dim 1: sequences/epochs
-dim 2: channels
-dim 3: unused
-dim 4: unused
-dim 5: unused
-dim 6: time


--- 2. Recording contacts coordinates ---

In addition, the locations of each intracerebral channel both in the Talairach and the MNI space are reported in a txt file in each participant's folder. 



--- 3. Set of stimuli used ---


The full set of stimuli used in the study are included in a separate folder (/Stimuli/), along with an information about bigram frequency for the words, nonwords and pseudowords ('stimuli_bigram_frequency.txt').
