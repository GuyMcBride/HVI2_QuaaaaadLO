# -*- coding: utf-8 -*-
"""
Created on Mon Nov  9 08:57:55 2020

@author: Administrator
"""

import os
import yaml
import logging
import math

from Configuration import (
    Config,
    loadConfig,
    AwgDescriptor,
    DigDescriptor,
    Hvi,
    HviConstant,
    Fpga,
    Register,
    PulseDescriptor,
    SubPulseDescriptor,
    Queue,
    QueueItem,
    DaqDescriptor,
)

log = logging.getLogger(__name__)


def main():
    # repeats: Number of triggers to generate
    loops = 1

    # repeats: Number of triggers to generate
    iterations = 16

    # pulseGap: Gap between pulses
    pulseGap = 200e-6

    # Register:
    #   #1 - name of register
    #   #2 - value to be written
    pcFpgaRegisters1 = [
        Register("PC_CH1_Control", 0x02),
        Register("PC_CH1_Log2Averages", 0x00),
        Register("PC_CH1_Prescaler", 0x00),
        Register("PC_CH1_Flags", 0x0),
    ]

    hviFpgaRegisters = [
        Register("HVI_GLOBAL_Trigger", 0),
    ]

    # Fpga:
    #   #1 - filename of bit image
    #   #2 - filename of 'vanilla' bit image
    #   #3 - list of writable register values
    fpga1 = Fpga(
        "./FPGA/Averager.k7z",
        "./FPGA/Vanilla_M3102A.k7z",
        pcFpgaRegisters1,
        hviFpgaRegisters,
    )

    # awgHviRegisters: Controls the HVI registers implemented inside the AWG_LEAD
    #   #1 - name
    #   #2 - value
    awgHviRegisters = [
        Register("LoopCounter", 0),
        Register("IterationCounter", 0),
    ]

    # SubPulseDescriptor:
    #    #1 - carrier frequency inside envelope (generally 0 if using LO)
    #    #2 - Pulse width
    #    #3 - time offset in from start of pulse window
    #            (needs to be long enough for envelope shaping)
    #    #4 - Amplitude (sum of amplitudes must be < 1.0)
    #    #5 - pulse shaping filter bandwidth
    pulseGroup = [
        SubPulseDescriptor(10e6, 10e-6, 1e-06, 0.6, 1e06),
    ]

    # PulseDescriptor
    #    #1 - Waveform ID to be used. Must be unique for every pulse (PulseGroup)
    #    #2 - The length of the pulse window
    #            (must be long enough to hold all pulse enelopes, with transition times)
    #    #3 - List of SubPulseDescriptor details - to maximum of 5.
    pulseDescriptor1 = PulseDescriptor(1, 150e-06, pulseGroup)

    # QueueItem:
    #    #1 - PulseGroup ID that defines the waveform
    #    #2 - Trigger (False = auto, True = trigger from SW/HVI)
    #    #3 - Start Delay (how long, in time from trigger, to delay before play)
    #    #4 - How many repeats of the waveform
    # Queue:
    #    #1 - Channel
    #    #2 - IsCyclical
    #    #3 - List of QueueItem details (waveforms)
    queue1 = Queue(1, True, [QueueItem(1, True, 0, 1)])
    queue3 = Queue(3, True, [QueueItem(1, True, 0, 1)])
    queue4 = Queue(4, True, [QueueItem(1, True, 0, 1)])

    # DaqDescriptor:
    #    #1 - Channel
    #    #2 - Capture Period
    #    #3 - Number of captures
    #    #3 - Trigger (False = auto, True = trigger from SW/HVI)
    daq1 = DaqDescriptor(1, 150e-06, loops, True)

    # AwgDescriptor:
    #    #1 - Name
    #    #2 - Model Number
    #    #3 - Number of channels
    #    #4 - Sample Rate of module
    #    #5 - Slot Number, in which the module is installed
    #    #6 - FPGA details
    #    #7 - List of HVI registers to use
    #    #8 - List of PulseDescriptor details
    #    #9 - List of queues (up to number of channels)
    awg1 = AwgDescriptor(
        "AWG_LEAD",
        "M3202A",
        4,
        1e09,
        2,
        Fpga(),
        awgHviRegisters,
        [pulseDescriptor1],
        [queue1, queue3, queue4],
    )

    # DigDescriptor:
    #    #1 - Name
    #    #2 - Model Number
    #    #3 - Number of channels
    #    #4 - Sample Rate of module
    #    #5 - Slot Number, in which the module is installed
    #    #6 - FPGA details
    #    #7 - List of HVI registers used
    #    #8 - List of DaqDescriptor details
    dig = DigDescriptor("DIG_0", "M3102A", 4, 500e06, 7, fpga1, [], [daq1])

    modules = [awg1, dig]

    # HviConstants: Controls things used to set up the HVI
    #   #1 - name
    #   #2 - value
    hviConstants = [
        HviConstant("NumberOfLoops", loops),
        HviConstant("NumberOfIterations", iterations),
        HviConstant("Gap", int(pulseGap / 1e-9)),
    ]

    # HVI:
    #    #1 - Python file that defines the HVI algorithm.
    #    #2 - List of Modules to include in HVI
    #    #3 - List of constants
    #    #4 - PXI Trigger Lines to use (defaults to all, 0 indexed)
    hvi = Hvi("FrameAverager", modules, hviConstants)

    # Config:
    #   #1 - List of Module details
    #   #2 - HVI details
    config = Config(modules, hvi)

    #    __name__ = "Configuration"
    saveConfig(config)
    config = loadConfig()
    log.info("Config File contents:\n{}".format(vars(config)))


def saveConfig(config: Config):
    if not os.path.exists("./config_hist"):
        os.mkdir("./config_hist")
    latest_hist = 0
    for file in os.listdir("./config_hist"):
        name = os.path.splitext(file)[0]
        hist = int(name.split("_")[-1])
        if hist > latest_hist:
            latest_hist = hist

    filename = "./config_hist/config_" + str(latest_hist + 1) + ".yaml"

    log.info("Generating Config file: {}".format(filename))
    with open(filename, "w") as f:
        yaml.dump(config, f)
    with open("config_default.yaml", "w") as f:
        yaml.dump(config, f)


def I(phase):
    return int(round(32767 * math.cos(math.radians(phase))))


def Q(phase):
    return int(round(32767 * math.sin(math.radians(phase))))


if __name__ == "__main__":
    main()
