# mp4snoop
A python program to read an MP4 file, and display the file structure.

The parsing is done by what is essentially a recursive-decent parser,
which examines the next box type and dispatches handling for that
particular type. Boxes not specifically handled are reported (size,type).

# Current State

Alternate sizes (box size==1 or 0) have been implemented but not tested.

Alternate box types (orig type of 'uuid') have not been implemented.

While most box versions are 0 (32bit size path), the version==1
boxes with 64bit sizes are implemented but have not been
tested.
