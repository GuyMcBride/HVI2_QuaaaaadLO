# -*- coding: utf-8 -*-
"""
Created on Mon Nov  9 08:57:55 2020

@author: Administrator
"""

import os
import yaml
import logging

from Configuration import (Config, loadConfig, 
                           AwgDescriptor, DigDescriptor,
                           Hvi, HviConstant, Fpga, Register,
                           PulseDescriptor, SubPulseDescriptor, 
                           Queue, QueueItem, 
                           DaqDescriptor)

log = logging.getLogger(__name__)

def main():
    # repeats: Number of triggers to generate
    repeats = 10
    
    # pulseGap: Gap between pulses
    pulseGap = 200.010E-6

    # mode: 0 = output individual waveform from one LO
    #       1 = output superimposed waveforms from all LOs
    mode = 0
    
    #Lo frequency definitions (card_channel_LO)
    lo1_1_0 = 10.0E6
    lo1_1_1 = 30E6
    lo1_1_2 = 50E6
    lo1_1_3 = 70E6
    
    # Register:
    #   #1 - name of register
    #   #2 - value to be written
    pcFpgaRegisters = [Register('PC_CH1_PhaseSel', mode),
                      Register('PC_CH1_PhaseInc0A', A(lo1_1_0)),
                      Register('PC_CH1_PhaseInc0B', B(lo1_1_0)),
                      Register('PC_CH1_PhaseInc1A', A(lo1_1_1)),
                      Register('PC_CH1_PhaseInc1B', B(lo1_1_1)),
                      Register('PC_CH1_PhaseInc2A', A(lo1_1_2)),
                      Register('PC_CH1_PhaseInc2B', B(lo1_1_2)),
                      Register('PC_CH1_PhaseInc3A', A(lo1_1_3)),
                      Register('PC_CH1_PhaseInc3B', B(lo1_1_3)),
                      Register('PC_CH4_PhaseSel', mode),
                      Register('PC_CH4_PhaseInc0A', A(lo1_1_0)),
                      Register('PC_CH4_PhaseInc0B', B(lo1_1_0)),
                      Register('PC_CH4_PhaseInc1A', A(lo1_1_1)),
                      Register('PC_CH4_PhaseInc1B', B(lo1_1_1)),
                      Register('PC_CH4_PhaseInc2A', A(lo1_1_2)),
                      Register('PC_CH4_PhaseInc2B', B(lo1_1_2)),
                      Register('PC_CH4_PhaseInc3A', A(lo1_1_3)),
                      Register('PC_CH4_PhaseInc3B', B(lo1_1_3))]
    
    hviFpgaRegisters = [Register('RegisterBank_PhaseReset', 0)]
    
    # Fpga:
    #   #1 - filename of bit image
    #   #2 - filename of 'vanilla' bit image
    #   #3 - list of writable register values
    fpga1 = Fpga("./FPGA/QuadLoCh1and4_4_00_95.k7z",
                 "./FPGA/M3202A_Vanilla_HVI2.k7z", 
                 pcFpgaRegisters,
                 hviFpgaRegisters)
    
    # SubPulseDescriptor:
    #    #1 - carrier frequency inside envelope (generally 0 if using LO)
    #    #2 - Pulse width
    #    #3 - time offset in from start of pulse window 
    #            (needs to be long enough for envelope shaping)
    #    #4 - Amplitude (sum of amplitudes must be < 1.0)
    #    #5 - pulse shaping filter bandwidth
    pulseGroup = [SubPulseDescriptor(0, 10e-6, 1E-06,  0.3,    1E06),
                  SubPulseDescriptor(0, 10e-6, 1E-06, -0.1,   1E06),
                  SubPulseDescriptor(0, 10e-6, 1E-06,  0.06,  1E06),
                  SubPulseDescriptor(0, 10e-6, 1E-06, -0.043, 1E06)]

    pulseGroup2 = [SubPulseDescriptor(10E6, 10e-6, 1E-06, 0.5, 1E06)]
    
    # PulseDescriptor
    #    #1 - Waveform ID to be used. Must be unique for every pulse (PulseGroup)
    #    #2 - The length of the pulse window 
    #            (must be long enough to hold all pulse enelopes, with transition times)
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
    queue2 = Queue(4, True, [QueueItem(1, True, 0, 1)])

    # DaqDescriptor:
    #    #1 - Channel
    #    #2 - Capture Period
    #    #3 - Trigger (False = auto, True = trigger from SW/HVI)
    daq1 = DaqDescriptor(1, 100e-06, repeats, True)
    
    # AwgDescriptor:
    #    #1 - Model Number
    #    #2 - Number of channels
    #    #3 - Sample Rate of module
    #    #4 - Slot Number, in which the module is installed
    #    #5 - FPGA details
    #    #6 - List of HVI registers to use
    #    #7 - List of LoDescriptor details
    #    #8 - List of PulseDescriptor details
    #    #9 - List of queues (up to number of channels)
    awg1 = AwgDescriptor("M3202A", 4, 1E09, 2, fpga1,
                         [pulseDescriptor1, pulseDescriptor2], 
                         [queue1, queue2])

    awg2 = AwgDescriptor("M3202A", 4, 1E09, 4, fpga1,
                         [pulseDescriptor1], 
                         [queue1])

    # DigDescriptor:
    #    #1 - Model Number
    #    #2 - Number of channels
    #    #3 - Sample Rate of module
    #    #4 - Slot Number, in which the module is installed
    #    #5 - FPGA details
    #    #6 - List of HVI registers to use
    #    #7 - List of DaqDescriptor details
    dig  = DigDescriptor("M3102A", 4, 500E06, 7, Fpga(), [daq1])

    modules = [awg1, awg2, dig]
    
    # HviConstant:
    #   #1 - name
    #   #2 - value
    hviConstants = [HviConstant('NumberOfLoops', repeats),
                    HviConstant('Gap', int(pulseGap / 1E-9))]
    
    # HVI:
    #    #1 - PXI Trigger Lines to use
    #    #2 - List of Modules to include in HVI
    #    #3 - List of constants
    hvi = Hvi([5, 6, 7], modules, hviConstants)
    
    # Config:
    #   #1 - List of Module details
    #   #2 - HVI details
    config = Config(modules, hvi)
    
#    __name__ = "Configuration"
    saveConfig(config)
    config = loadConfig()
    log.info("Config File contents:\n{}".format(vars(config)))
    
def saveConfig(config : Config):   
    if not os.path.exists('./config_hist'):
        os.mkdir('./config_hist')
    latest_hist = 0
    for file in os.listdir('./config_hist'):
        name = os.path.splitext(file)[0]
        hist = int(name.split('_')[-1])
        if hist > latest_hist:
            latest_hist = hist
    
    filename = './config_hist/config_' + str(latest_hist + 1) + '.yaml' 

    log.info("Generating Config file: {}".format(filename))
    with open(filename, 'w') as f:
        yaml.dump(config, f)
    with open('config_default.yaml', 'w') as f:
        yaml.dump(config, f)


def A(f, fs=1E9):
    S = 5
    T = 8
    K = (f / fs) * (S / T) * 2**25
    A = int(K)
    return A

def B(f, fs=1E9):
    S = 5
    T = 8
    K = (f / fs) * (S / T) * 2**25
    A = int(K)
    B = round((K-A) * 5**10) 
    return B

if (__name__ == '__main__'):
    main()
        