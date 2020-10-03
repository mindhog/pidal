"""
fontchooser module for Tkinter

This module defines a class Fontchooser and a convenience function askfont.

Fontchooser is an interface to the Tcl/Tk fontchooser command
which displays a dialog from which an available font can be selected.

askfont is a convenience function that displays the font selection
dialog and returns the selected font.

Author: Lance Ware
Date  : November 2016
"""


import re
import tkinter as tk


#==============================================================================
# Internal font/string conversion functions
#==============================================================================


def _font_to_str(val):
    if not val:
        s = "Arial 10" # default
    elif isinstance(val, (tuple, list)):
        s = " ".join(tk._stringify(item) for item in val)
    else:
        s = str(val)
    return(s)

def _str_to_font(val):
    val = str(val)
    # Font string in form "{family} size ?styles" or "family size ?styles".
    m = re.match(r"({.+}|\w+) +(-?[0-9]+) *(.*)", val)
    if m:
        fam = m.group(1).strip("{}")
        size = int(m.group(2))
        styles = m.group(3)
        if styles:
            font = (fam, size, styles)
        else:
            font = (fam, size)
    else:
        font = val
    return(font)


###############################################################################


class Fontchooser:
    """
    Interface to the Tcl/Tk fontchooser command.
    
    The fontchooser command displays a font selection dialog, from which an
    available font can be selected.
    This class supports the subcommands configure, show, hide, and all the
    configuration options parent, title, font, command, visible.
    Note that the font selection dialog is modal, at least on Windows, so the 
    show() method will not return until "OK" or "Cancel" is clicked.
    """
    
    def __init__(self, master=None, **options):
        """
        Class instance initialization.
        master  - specifies parent widget for font selection dialog and takes
                  precedence over the parent option if also specified.
        options - any of the options parent, title, font, command.
        """
        options = options.copy()
        self.master = master or options.get("parent")
        if not self.master:
          self.master = tk._default_root if tk._support_default_root else tk.Tk()
        options["parent"] = self.master
        self.master.tk.call("tk", "fontchooser", "configure", "-command", 
                            self.master._register(self._callback))
        self._command = None
        self["font"] = None # Tk isn't setting a default font, so force it.
        self.configure(**options)
        self.ok = False

    #--------------------------------------------------------------------------
    # Internal callback
    #
    # This callback is used to intercept the callback mechanism.
    # If the font selection dialog OK button is pressed, this callback is 
    # invoked with the 'visible' option set to false.
    # If the font selection dialog Apply button is pressed, this callback is
    # invoked with the 'visible' option set to true.
    # If the font selection dialog Cancel button is pressed, this callback is 
    # not invoked.
    # If the 'command' option is specified, it will be invoked from this 
    # callback.
    #--------------------------------------------------------------------------

    def _callback(self, font):
        # Set font to the one chosen. Tk doesn't do this automatically.
        self["font"] = font
        self.ok = not self.visible()
        if self._command:
            self._command()

    #--------------------------------------------------------------------------
    # Dialog show/hide methods
    #--------------------------------------------------------------------------

    def show(self):
        """Show the font selection dialog."""
        self.ok = False
        self.master.tk.call("tk", "fontchooser", "show")
      
    def hide(self):
        """Hide the font selection dialog if visible."""
        self.master.tk.call("tk", "fontchooser", "hide")

    #--------------------------------------------------------------------------
    # Option get/set methods
    #--------------------------------------------------------------------------

    def parent(self):
        """Get font selection dialog parent widget."""
        return(self["parent"])

    def title(self):
        """Get font selection dialog title."""
        return(self["title"])

    def font(self):
        """Get currently selected or inital font. The font is in the
        tuple format (family, size, styles).
        """
        return(self["font"])

    def command(self):
        """Get command that will be called when OK or Apply is selected."""
        return(self["command"])

    def visible(self):
        """Get boolean indicating whether font selection dialog is visible."""
        return(self["visible"])
        
    def configure(self, **options):
        """Set the values of one or more options."""
        for k in options:
          self[k] = options[k]
          
    config = configure

    def __getitem__(self, opt):
        """Options get mechanism.""" 
        if opt in ("parent", "title", "font", "visible"):
            val = self.master.tk.call("tk", "fontchooser", 
                                      "configure", "-" + opt)
            if opt == "font":
                val = _str_to_font(val)
            return(val)
        elif opt == "command":
            return(self._command)
        else:
            raise KeyError("invalid Fontchooser option '{}'".format(opt))

    def __setitem__(self, opt, val):
        """Options set mechanism."""
        if opt in ("parent", "title", "font"):
            if opt == "font":
                val = _font_to_str(val)
            self.master.tk.call("tk", "fontchooser", 
                                "configure", "-" + opt, val)
        elif opt == "command":
            self._command = val
        else:
            raise KeyError("invalid Fontchooser option '{}'".format(opt))

    #--------------------------------------------------------------------------

    def selected(self):
        """ 
        Returns True if OK was pressed in the fontchooser dialog, thus
        indicating that the current font option was selected by the user.
        """
        return(self.ok)


#==============================================================================
# Convenience function


def askfont(font=None, **options):
    """
    Displays the font selection dialog and returns the selected font,
    if any, in tuple format (family, size, styles).
    font    - initially selected font, if any.
    options - options for Fontchooser (parent, title, font, command).
    """
    fc = Fontchooser(font=font, **options)
    fc.show()
    return(fc.font() if fc.selected() else None)


#==============================================================================
# Test

if __name__ == "__main__":

    class Font_Sel():
        def __init__(self, master=None, **options):
            self.fc = Fontchooser(master, command=self.cmd, **options)
            print(self.state())
        def sel(self):
            self.fc.show()
            print(self.state())
            return(self.fc.font() if self.fc.selected() else None)
        def cmd(self):
            print("--> cmd()")
            print(self.state())
        def state(self):
            return("\n".join("{} = {}".format(opt, self.fc[opt]) for opt in ("parent", "title", "font", "command", "visible")))

    def cb():
        print("--> cb()")

    def choose_font():
        fs = Font_Sel(root, title = "Fontchooser", font=("arial", 12))
        print(fs.sel())
        font = askfont(title="Select Font (no default)")
        print(font)
        font = askfont(("times new roman", 12, "bold italic"), parent=root, title="Select Font (with default)", command=cb)
        print(font)

    root = tk.Tk()
    tk.Button(root, text="Choose Font", command=choose_font).pack()
    root.mainloop()
