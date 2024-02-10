"""
DAPHNEStream data loading and storing class.
"""

# Internal Libraries
import os

# DUNE-DAQ Libraries
import daqdataformats
from hdf5libs import HDF5RawDataFile
from rawdatautils.unpack.daphne import (
        np_array_adc_stream,
        np_array_channels_stream
)

# External Libraries
import numpy as np

# pdstools
from . import exceptions


class DAPHNEStreamData:
    """
    Class that loads a given raw HDF5 data file that contains
    DAPHNEStreams.

    Loading fragments populates obj.ds_data. By default this only loads
    a few fragments as the data rate for PDS is very high.

    Gives warnings and information when trying to load empty fragments.
    These outputs can be quieted with quiet=True on init.
    """
    # Useful print colors
    _FAIL_TEXT_COLOR = '\033[91m'
    _WARNING_TEXT_COLOR = '\033[93m'
    _BOLD_TEXT = '\033[1m'
    _RESET_TEXT_COLOR = '\033[0m'

    # Data
    ds_data = np.array([], dtype=np.uint16).reshape(0, 1)  # Will concatenate
    channels = np.array([], dtype=np.uint8)  # Will populate
    _data_is_empty = True

    def __init__(self, filename: str, quiet: bool = False) -> None:
        """
        Loads the given HDF5 file and initializes member data.

        Parameters:
            filename (str): File name to load from.
            quiet (bool): Quiet debugging output.

        Returns:
            Nothing.
        """
        # File structure loading
        self._h5_file = HDF5RawDataFile(os.path.expanduser(filename))
        self._quiet = quiet
        self._set_fragment_paths(self._h5_file.get_all_fragment_dataset_paths())

        # File identification attributes
        self.run_id = self._h5_file.get_int_attribute("run_number")
        self.file_index = self._h5_file.get_int_attribute("file_index")
        return None

    def __call__(self, frag_path: str) -> np.ndarray:
        """
        Loads a fragment path, same as self.load_fragment.

        Parameters:
            frag_path (str): Fragment path to load.

        Returns:
            np.ndarray: Array of ADC values found in the fragment.
                        Also concatenates self.ds_data with these values.
        """
        return self.load_fragment(frag_path)

    # Setters
    def _set_fragment_paths(self, frag_paths: list[str]) -> None:
        """
        Filters all the fragment paths to only find DAPHNEStreams.

        Parameters:
            frag_paths (list[str]): List of fragment paths to filter on.

        Returns:
            Nothing. Creates a new data member self._frag_paths.
        """
        self._frag_paths = []

        # Filter paths
        for frag_path in frag_paths:
            if "DAPHNEStream" in frag_path:
                self._frag_paths.append(frag_path)

        if self._quiet:
            return None

        # Debugging outputs
        if len(self._frag_paths) == 0:
            print(
                    self._WARNING_TEXT_COLOR
                    + self._BOLD_TEXT
                    + "WARNING: No DAPHNEStream fragments found!"
                    + self._RESET_TEXT_COLOR
            )
        return None

    def set_channels(self, channels: list[int]) -> None:
        """
        Set the ARAPUCA channels to search over.

        Parameters:
            channels (list[int]): List of channel numbers to collect on.

        Returns:
            Nothing. Mutates self.channels.
        """
        # Debugging output
        if len(self.channels) != 0 and not self._quiet:
            print(
                    self._WARNING_TEXT_COLOR
                    + self._BOLD_TEXT
                    + "WARNING: Overwriting old channel mask."
                    + self._RESET_TEXT_COLOR
            )

        self.channels = np.array(channels, dtype=np.uint8)

        return None

    # Getters
    def get_fragment_paths(self) -> list[str]:
        """ Returns the set fragment paths list. """
        return self._frag_paths

    def get_loaded_data(self) -> np.ndarray:
        """ Returns the loaded data as a copy. """
        return self.ds_data.copy()

    # Loaders
    def load_fragment(self, frag_path: str) -> np.ndarray:
        """
        Load a fragment and store and return the output.

        Requires self.channels to be non-empty.

        Parameters:
            frag_path (str): Fragment path to load on.

        Returns:
            np.ndarray: Array of ADC values found in the fragment.
                        Also concatenates self.ds_data with these values.
        """
        if len(self.channels) == 0:
            if not self._quiet:
                print(
                        self._FAIL_TEXT_COLOR
                        + self._BOLD_TEXT
                        + "ERROR: Trying to load fragment without setting channels."
                        + self._WARNING_TEXT_COLOR
                        + "\nSet the channels with self.set_channels()."
                        + self._RESET_TEXT_COLOR
                )
            raise exceptions.EmptyChannelsError("Tried loading with empty self.channels.")

        frag = self._h5_file.get_frag(frag_path)
        channels = np_array_channels_stream(frag)

        # Channels stored in this fragment. Shape: (Num frames, 4 channels)
        # Physically, channel numbers shouldn't change between frames.
        # Only get the first since they're all the same.
        channels = channels[0]

        # Filter channels and waveforms.
        wf_filter = np.zeros((4,), dtype=bool)
        for idx, channel in enumerate(channels):  # Filter channels
            if channel in self.channels:
                wf_filter[idx] = True

        if np.sum(wf_filter) == 0:  # No channels passed the filter
            if not self._quiet:
                print(
                        self._WARNING_TEXT_COLOR
                        + self._BOLD_TEXT
                        + f"WARNING: No channels of interest found in fragment {frag_path}."
                        + self._RESET_TEXT_COLOR
                )
            return np.array([], dtype=np.uint64)

        # Channels in filter case. Continue loading.
        adcs = np_array_adc_stream(frag)  # (Num ticks, 4 channels)
        adcs = adcs[:, wf_filter]  # Only get the filtered channels

        # Start a new self.ds_data.
        if self._data_is_empty:
            self.ds_data = adcs.T
            self._data_is_empty = False
            return adcs.T

        # Continue with old self.ds_data. Add new WFs as new rows.
        # Truncates to the smaller data size if necessary.
        min_ticks = np.min((self.ds_data.shape[1], adcs.shape[0]))
        self.ds_data = np.vstack((self.ds_data[:, :min_ticks], adcs.T[:, :min_ticks]))
        # TODO: AO: Should there be a warning/error if truncating?

        return adcs.T

    def load_fragment_list(self, frag_list: list[str]) -> None:
        """
        Load a list of fragment paths.

        Parameters:
            frag_list (list[str]): List of fragment paths to load.

        Returns:
            Nothing. Concatenates to self.ds_data.
        """
        for frag_path in frag_list:
            _ = self.load_fragment(frag_path)  # Not saving the output.
        return None
