"""
Custom exceptions to be more descriptive about problems
when using this project.
"""


class EmptyChannelsError(Exception):
    """
    PDS channels were not specified.

    This is raised when trying to load data fragments
    before specifying the channel(s) of interest.
    """
    pass
