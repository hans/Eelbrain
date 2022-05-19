"""Import wx through this module to modify up logging"""
import logging
from warnings import filterwarnings

L = logging.getLogger(__name__)

filterwarnings('ignore', message='Not importing directory .*', module='wx.*')
try:
    import wx
except ImportError as e:
    logging.warn("wx import failed; GUI members will not be accessible",
                 exc_info=e)

    wx = None
    Icon = show_text_dialog = None
    needs_jumpstart = get_app = run = None
    history = select_epochs = select_components = load_stcs = None
else:
    # filter unnecessary warnings
    from .. import _config
    if _config.SUPPRESS_WARNINGS:
        filterwarnings('ignore', category=wx.wxPyDeprecationWarning)
        filterwarnings('ignore', 'NewId()', category=DeprecationWarning)
        filterwarnings('ignore', module='(traitsui|pyface|apptools)', category=DeprecationWarning)
        filterwarnings('ignore', 'invalid escape sequence', DeprecationWarning)  # tvtk
        wx.Log.EnableLogging(False)

    from .utils import Icon, show_text_dialog
    from .app import needs_jumpstart, get_app, run
    from . import history, select_epochs, select_components, load_stcs
