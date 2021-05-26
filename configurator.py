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
    loops = 5

    # repeats: Number of triggers to generate
    iterations = 2

    # resetPhases:  0 = Only reset phase at initialization
    #               1 = Reset Phase each time around repeat loop
    resetPhase = 1

    # pulseGap: Gap between pulses
    pulseGap = 200e-6

    # mode: 0 = output individual waveform from one LO
    #       1 = output superimposed waveforms from all LOs
    mode = 0

    # phaseSource : 0 = PC sets the phase source
    #               1 = HVI sets the phase source
    phaseSource = 1

    # frequencySource : 0 = PC sets the frequency source
    #               1 = HVI sets the frequency source
    frequencySource = 1

    # Lo frequency definitions (card_channel_LO)
    lo1_1_0 = 10e6
    lo1_1_1 = 30e6
    lo1_1_2 = 50e6
    lo1_1_3 = 70e6

    lophase1_1_0 = 0
    lophase4_1_0 = 0

    control = mode + (phaseSource << 1) + (frequencySource << 2)

    # Register:
    #   #1 - name of register
    #   #2 - value to be written
    pcFpgaRegisters1 = [
        Register("PC_CH1_Control", control),
        Register("PC_CH1_Q0", Q(lophase1_1_0)),
        Register("PC_CH1_I0", I(lophase1_1_0)),
        Register("PC_CH1_PhaseInc0A", A(lo1_1_0)),
        Register("PC_CH1_PhaseInc0B", B(lo1_1_0)),
        Register("PC_CH1_Q1", Q(lophase1_1_0)),
        Register("PC_CH1_I1", I(lophase1_1_0)),
        Register("PC_CH1_PhaseInc1A", A(lo1_1_1)),
        Register("PC_CH1_PhaseInc1B", B(lo1_1_1)),
        Register("PC_CH1_Q2", Q(lophase1_1_0)),
        Register("PC_CH1_I2", I(lophase1_1_0)),
        Register("PC_CH1_PhaseInc2A", A(lo1_1_2)),
        Register("PC_CH1_PhaseInc2B", B(lo1_1_2)),
        Register("PC_CH1_Q3", Q(lophase1_1_0)),
        Register("PC_CH1_I3", I(lophase1_1_0)),
        Register("PC_CH1_PhaseInc3A", A(lo1_1_3)),
        Register("PC_CH1_PhaseInc3B", B(lo1_1_3)),
        Register("PC_CH3_Control", control),
        Register("PC_CH3_Q0", Q(lophase1_1_0)),
        Register("PC_CH3_I0", I(lophase1_1_0)),
        Register("PC_CH3_PhaseInc0A", A(lo1_1_0)),
        Register("PC_CH3_PhaseInc0B", B(lo1_1_0)),
        Register("PC_CH3_Q1", Q(lophase1_1_0)),
        Register("PC_CH3_I1", I(lophase1_1_0)),
        Register("PC_CH3_PhaseInc1A", A(lo1_1_1)),
        Register("PC_CH3_PhaseInc1B", B(lo1_1_1)),
        Register("PC_CH3_Q2", Q(lophase1_1_0)),
        Register("PC_CH3_I2", I(lophase1_1_0)),
        Register("PC_CH3_PhaseInc2A", A(lo1_1_2)),
        Register("PC_CH3_PhaseInc2B", B(lo1_1_2)),
        Register("PC_CH3_Q3", Q(lophase1_1_0)),
        Register("PC_CH3_I3", I(lophase1_1_0)),
        Register("PC_CH3_PhaseInc3A", A(lo1_1_3)),
        Register("PC_CH3_PhaseInc3B", B(lo1_1_3)),
        Register("PC_CH4_Control", control),
        Register("PC_CH4_Q0", Q(lophase1_1_0)),
        Register("PC_CH4_I0", I(lophase1_1_0)),
        Register("PC_CH4_PhaseInc0A", A(lo1_1_0)),
        Register("PC_CH4_PhaseInc0B", B(lo1_1_0)),
        Register("PC_CH4_Q1", Q(lophase1_1_0)),
        Register("PC_CH4_I1", I(lophase1_1_0)),
        Register("PC_CH4_PhaseInc1A", A(lo1_1_1)),
        Register("PC_CH4_PhaseInc1B", B(lo1_1_1)),
        Register("PC_CH4_Q2", Q(lophase1_1_0)),
        Register("PC_CH4_I2", I(lophase1_1_0)),
        Register("PC_CH4_PhaseInc2A", A(lo1_1_2)),
        Register("PC_CH4_PhaseInc2B", B(lo1_1_2)),
        Register("PC_CH4_Q3", Q(lophase1_1_0)),
        Register("PC_CH4_I3", I(lophase1_1_0)),
        Register("PC_CH4_PhaseInc3A", A(lo1_1_3)),
        Register("PC_CH4_PhaseInc3B", B(lo1_1_3)),
    ]

    pcFpgaRegisters2 = [
        Register("PC_CH1_Control", control),
        Register("PC_CH1_Q0", Q(lophase4_1_0)),
        Register("PC_CH1_I0", I(lophase4_1_0)),
        Register("PC_CH1_PhaseInc0A", A(lo1_1_0)),
        Register("PC_CH1_PhaseInc0B", B(lo1_1_0)),
        Register("PC_CH1_Q1", Q(lophase4_1_0)),
        Register("PC_CH1_I1", I(lophase4_1_0)),
        Register("PC_CH1_PhaseInc1A", A(lo1_1_1)),
        Register("PC_CH1_PhaseInc1B", B(lo1_1_1)),
        Register("PC_CH1_Q2", Q(lophase4_1_0)),
        Register("PC_CH1_I2", I(lophase4_1_0)),
        Register("PC_CH1_PhaseInc2A", A(lo1_1_2)),
        Register("PC_CH1_PhaseInc2B", B(lo1_1_2)),
        Register("PC_CH1_Q3", Q(lophase4_1_0)),
        Register("PC_CH1_I3", I(lophase4_1_0)),
        Register("PC_CH1_PhaseInc3A", A(lo1_1_3)),
        Register("PC_CH1_PhaseInc3B", B(lo1_1_3)),
    ]

    hviFpgaRegisters = [
        Register("HVI_Mult_A", 0x00),
        Register("HVI_Mult_B", 0x00),
        Register("HVI_Mult_AB", 0x00),
        Register("HVI_GLOBAL_PhaseReset", 0),
        Register("HVI_CH1_PhaseInc0A", A(lo1_1_0)),
        Register("HVI_CH1_PhaseInc0B", B(lo1_1_0)),
        Register("HVI_CH3_PhaseInc0A", A(lo1_1_0)),
        Register("HVI_CH3_PhaseInc0B", B(lo1_1_0)),
        Register("HVI_CH4_PhaseInc0A", A(lo1_1_0)),
        Register("HVI_CH4_PhaseInc0B", B(lo1_1_0)),
        Register("HVI_CH1_Phase0", 0),
        Register("HVI_CH3_Phase0", 0),
        Register("HVI_CH4_Phase0", 0),
        Register("HVI_CH1_Amplitude0", 0xffff),
        Register("HVI_CH3_Amplitude0", 0xffff),
        Register("HVI_CH4_Amplitude0", 0xffff),
    ]

    # Fpga:
    #   #1 - filename of bit image
    #   #2 - filename of 'vanilla' bit image
    #   #3 - list of writable register values
    fpga1 = Fpga(
        "./FPGA/QuadLoCh1_4_01_20.k7z",
        "./FPGA/M3202A_Vanilla.k7z",
        pcFpgaRegisters1,
        hviFpgaRegisters,
    )

    fpga2 = Fpga(
        "./FPGA/QuadLoCh1_4_01_20.k7z",
        "./FPGA/M3202A_Vanilla.k7z",
        pcFpgaRegisters2,
        hviFpgaRegisters,
    )

    # HviRegisters: Controls the registers implemeted inside the HVI
    #   #1 - name
    #   #2 - value
    hviRegisters = [
        Register("LoopCounter", 0),
        Register("IterationCounter", 0),
        Register("FrequencyIterator", A(lo1_1_0)),
        Register("PhaseIterator", 0),
        Register("AmplitudeIterator", 0xfff),
        Register("AB", 0),
    ]

    # SubPulseDescriptor:
    #    #1 - carrier frequency inside envelope (generally 0 if using LO)
    #    #2 - Pulse width
    #    #3 - time offset in from start of pulse window
    #            (needs to be long enough for envelope shaping)
    #    #4 - Amplitude (sum of amplitudes must be < 1.0)
    #    #5 - pulse shaping filter bandwidth
    pulseGroup = [
        SubPulseDescriptor(0, 10e-6, 1e-06, 0.6, 1e06),
        SubPulseDescriptor(0, 10e-6, 1e-06, 0.2, 1e06),
        SubPulseDescriptor(0, 10e-6, 1e-06, 0.12, 1e06),
        SubPulseDescriptor(0, 10e-6, 1e-06, 0.086, 1e06),
    ]

    pulseGroup2 = [SubPulseDescriptor(10e6, 10e-6, 1e-06, 0.5, 1e06)]

    # PulseDescriptor
    #    #1 - Waveform ID to be used. Must be unique for every pulse (PulseGroup)
    #    #2 - The length of the pulse window
    #            (must be long enough to hold all pulse envelopes, with transition times)
    #    #3 - List of SubPulseDescriptor details - to maximum of 5.
    pulseDescriptor1 = PulseDescriptor(1, 60e-06, pulseGroup)
    pulseDescriptor2 = PulseDescriptor(2, 60e-06, pulseGroup2)

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
    #    #3 - Trigger (False = auto, True = trigger from SW/HVI)
    daq1 = DaqDescriptor(1, 100e-06, loops * iterations, True)

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
        fpga1,
        hviRegisters,
        [pulseDescriptor1, pulseDescriptor2],
        [queue1, queue3, queue4],
    )

    awg2 = AwgDescriptor(
        "AWG_FOLLOW_0", "M3202A", 4, 1e09, 4, fpga2, [], [pulseDescriptor1], [queue1]
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
    dig = DigDescriptor("DIG_0", "M3102A", 4, 500e06, 7, Fpga(), [], [daq1])

    modules = [awg1, awg2, dig]

    # HviConstants: Controls things used to set up the HVI
    #   #1 - name
    #   #2 - value
    hviConstants = [
        HviConstant("ResetPhase", resetPhase),
        HviConstant("NumberOfLoops", loops),
        HviConstant("NumberOfIterations", iterations),
        HviConstant("Gap", int(pulseGap / 1e-9)),
#        HviConstant("FrequencyIncrement", A(lo1_1_0)),
        HviConstant("FrequencyIncrement", 0),
        HviConstant("PhaseIncrement", int(180 * 1024/360)),
        HviConstant("AmplitudeIncrement", int(500)),
    ]

    # HVI:
    #    #1 - Python file that defines the HVI algorithm.
    #    #2 - List of Modules to include in HVI
    #    #3 - List of constants
    #    #4 - PXI Trigger Lines to use (defaults to all, 0 indexed)
    hvi = Hvi("hvi_quad_lo", modules, hviConstants)

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


def A(f, fs=1e9):
    S = 5
    T = 8
    K = (f / fs) * (S / T) * 2 ** 25
    A = int(K)
    return A


def B(f, fs=1e9):
    S = 5
    T = 8
    K = (f / fs) * (S / T) * 2 ** 25
    A = int(K)
    B = round((K - A) * 5 ** 10)
    return B


def I(phase):
    return int(round(32767 * math.cos(math.radians(phase))))


def Q(phase):
    return int(round(32767 * math.sin(math.radians(phase))))


if __name__ == "__main__":
    main()
