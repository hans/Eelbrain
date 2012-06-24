"""
the main application for Eelbrain's wx-terminal

"""

import logging
import os
import sys

import wx

import shell



class MainApp(wx.App):
    """
    The main application (:py:class:`wx.App` subclass). Creates the shell 
    instance.
    
    """
    def __init__(self, redirect=False, filename=None, **shell_kwargs):
        """
        redirect : bool
            Redirect sys.stdout and sys.stderr; Redirects the output of 
            internal ``print`` commands
        
        filename : 
            Target for redirected 
        
        """
        self.shell_kwargs = shell_kwargs
        wx.App.__init__(self, redirect=redirect, filename=filename)
    
    def OnInit(self):
        self.shell = shell.ShellFrame(None, title='Eelbrain Shell', 
                                      **self.shell_kwargs)
        self.SetTopWindow(self.shell)
        if wx.__version__ >= '2.9':
            self.shell.ShowWithEffect(wx.SHOW_EFFECT_ROLL_TO_BOTTOM)
        else:
            self.shell.Show()
        
        if len(sys.argv) > 1:
            for arg in sys.argv[1:]:
                self.shell.OnFileOpen(None, path=arg)
        
        return True
    
    def MacOpenFile(self, filename):
        """
        after
        http://wiki.wxpython.org/Optimizing%20for%20Mac%20OS%20X
        
        """
        logging.debug("MAC Open File: %s"%filename)
        if os.path.basename(filename) == 'eelbrain':
            # (when launching through the script, MacOpenFile is called with
            # the script's path)
            return
        elif os.path.isfile(filename):
            self.shell.OnFileOpen(path=filename)
