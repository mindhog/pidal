Pidal - Another Software Effects Pedal Built from a Raspberry Pi
================================================================

This repository contains software, CAD files and my notes associated with the
Hog-1 effects pedal (or "pidal" as I've been saying).

Though I"m reasonably happy with the hardware at this point, the software
(though very usable) is still very much a work in progress.  Furthermore, I
have yet to write up a detailed post on the construction of the unit.

In any case, I have decided to publish the repository as it now stands.

Brief Install Instructions
--------------------------

For complete (though disorganized) instructions, see [notes.txt](notes.txt).

The stripped down process for installing just the shell program follows (this
will work on any debian-based Linux sysem as well as a Raspberry Pi running
Raspberry Pi OS):

1)  Install the following packages as root:

    ```shell
    $ apt-get install swig libasound2-dev a2jmidid tmux lingot libxpm-dev \
        libfltk1.3-dev libjack-jackd2-dev libsndfile1-dev libsamplerate0-dev \
        libasound2-dev libxft-dev libfftw3-dev lv2-dev cmake
    $ pip3 install cffi NumPy JACK-Client attrs
    ```

2)  Obtain my patched version of rakarrack-plus:

    ```shell
    $ git clone https://github.com/mindhog/rakarrack-plus.git mmuller-patches
    $ cd rakarrack-plus
    $ mkdir build; cd build; cmake
    $ make -j5
    $ sudo make install
    ```

    You'll want to use my patched version (as opposed to rakarrack in the
    distro or even the original rakarrack-plus fork) as it fixes a number of
    issues that are very relevant to remote controlling rak from another
    program.

3)  Run "lingot" (the tuner program) once to generate a config file.  Then
    edit `$HOME/.lingot/lingot.conf` and change the value of `AUDIO_SYSTEM` to
    `jack`.

4)  Build the code in this repository as follows:

    ```shell
    $ python setup.py build
    ```

5)  Edit [run.sh](run.sh) if you want to specify your soundcard.  You can also
    add a new shell script to the init.d directory that will allow you to plug
    in alternate external soundcards and select the preferred one at runtime
    (scripts in this directory are run in alphabetical order, first to define
    `jack_pid` will pre-empt the others).

At this point, if you run `run.sh` things should hopefully work (please open
a bug report if it doesn't).  You should see a window displaying the initial
config and your sound-card should be configured to route through one of the
effects programs.

Contributions
-------------

I'm happy to accept coding contributions, however please note that the github
repository is not canonical: I maintain this code within mercurial.  Feel free
to open pull requests for review, but I will ultimately merge them from the
mercurial repo (preserving your credentials, of course).

Licensing
---------

The code in this repository is released under the Apache Software License,
version 2.0 (see [LICENSE](LICENSE) for details).
