# regshot-to-reg
###Description

**This Python 2 script takes a Regshot comparison text file as input and produces two .reg files (undo and redo) as output.**

The undo file will undo the registry changes just made and the redo file will add the same changes again once the undo file has reverted the recent changes.

**Warning**: Adding and removing registry entries can be very dangerous, and I would strongly advise against running any .reg file produced by the script, at least until you have manually checked it and confirmed that it seems unlikely to make your computer initiate a self-destruct countdown sequence. There may be an odd registry key or value that I have not forseen which may cause the script to choke or produce invalid output. More testing is needed.

###Basic Usage

The assumption here is that everything is going to take place in one directory that contains 1) the regshot-to-reg.py script and 2) the Regshot comparison text file from which you want to generate .reg files. As long as the previous conditions are satisfied, it should work like this once cd'ed to the same directory:


```
> regshot-to-reg.py textfile.txt
```

If the script protests that it can't open the file for some reason, that is probably because it has run into a hidden error. To unhide error messages, simply add '-d' onto the end to display errors or '-df' to print the errors to a file in the same directory.
