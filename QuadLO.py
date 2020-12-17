# -*- coding: utf-8 -*-
"""
Created on Fri Nov  6 16:45:52 2020

@author: gumcbrid
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import logging

sys.path.append(r'C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1 as key

import pulses as pulseLab

import Configuration
import QuadLoHvi

log = logging.getLogger(__name__)

if len(sys.argv) > 1:
    configName = sys.argv[1]
else:
    configName = 'latest'   
log.info("Opening Config file: {})".format(configName))

config = Configuration.loadConfig(configName)

def main():
    configureModules()
    QuadLoHvi.configure(config)
    log.info("Waiting for stuff to happen...")
    time.sleep(1)
    digData = []
    for module in config.modules:
        if module.model == 'M3102A':
            digData.append(getDigData(module))
            sampleRate = module.sample_rate
    log.info("Closing down hardware...")
    QuadLoHvi.close()
    closeModules()
    log.info("Plotting Results...")
    plotWaves(digData, sampleRate, "Captured Waveforms")
    plt.show()


def plotWaves(waves, sampleRate, title):
    plt.figure()
    plotnum = 0
    for group in waves:
        for subgroup in group:
            plotnum = plotnum + 1
            plt.subplot(len(group) * len(waves), 1, plotnum)
            for wave in subgroup:
                timebase = np.arange(0, len(wave))
                timebase = timebase / sampleRate
                plt.plot(timebase, wave)
    plt.suptitle(title)

def configureModules():    
    chassis = key.SD_Module.getChassisByIndex(1)
    if chassis < 0:
        log.error("Finding Chassis: {} {}".format(chassis, 
                                                  key.SD_Error.getErrorMessage(chassis)))
    log.info("Chassis found: {}".format(chassis))
    for module in config.modules:
        if module.model == 'M3202A':
            configureAwg(chassis, module)
        elif module.model == 'M3102A':
            configureDig(chassis, module)

def _configureFpga(module):
    if module.fpga.image_file != '':
        log.info("Loading FPGA image: {}".format(module.fpga.image_file))
        error = module.handle.FPGAload(os.getcwd() + '\\' + module.fpga.image_file)
        if error < 0:
           log.error('Loading FPGA bitfile: {} {}'.format(error, 
                                                          key.SD_Error.getErrorMessage(error)))

    log.info("Writing {} FPGA registers".format(len(module.fpga.pcRegisters)))
    for register in module.fpga.pcRegisters:
        sbReg = module.handle.FPGAgetSandBoxRegister(register.name)
        error = sbReg.writeRegisterInt32(register.value)
        if error < 0:
            log.error("Error writing register: {}".format(register.name))
    

def configureAwg(chassis, module):
    log.info("Configuring AWG in slot {}...".format(module.slot))
    module.handle = key.SD_AOU()
    awg = module.handle
    error = awg.openWithSlotCompatibility('', 
                                          chassis, 
                                          module.slot,
                                          key.SD_Compatibility.KEYSIGHT)
    if error < 0:
        log.info("Error Opening - {}".format(error))
    _configureFpga(module)
    #Clear all queues and waveforms
    awg.waveformFlush()
    for channel in range(module.channels):
        awg.AWGflush(channel + 1)
    loadWaves(module)
    enqueueWaves(module)
    trigmask = 0
    for channel in range(module.channels):
        awg.channelWaveShape(channel + 1, key.SD_Waveshapes.AOU_AWG)
#Remove this if using HVI
#        trigmask = trigmask | 2**channel
#        log.info("triggering with {}".format(trigmask))
#        awg.AWGtriggerMultiple(trigmask)

def closeModules():
    for module in config.modules:
        if module.model == "M3202A":
            stopAwg(module)
        elif module.model == "M3102A":
            stopDig(module)
        if module.fpga.image_file != '':
            log.info("Loading FPGA image: {}".format(module.fpga.vanilla_file))
            error = module.handle.FPGAload(os.getcwd() + '\\' + module.fpga.vanilla_file)
            if error < 0:
               log.error('Loading FPGA bitfile: {} {}'.format(error, 
                                                              key.SD_Error.getErrorMessage(error)))
        module.handle.close()
    log.info("Finished stopping and closing Modules")

def stopAwg(module):
    log.info("Stopping AWG in slot {}...".format(module.slot))
    for channel in range(1, module.channels + 1):
        error = module.handle.AWGstop(channel)
        if error < 0:
            log.info("Stopping AWG failed! - {}".format(error))
    
def stopDig(module):
    log.info("Stopping Digitizer in slot {}...".format(module.slot))
    for channel in range(1, module.channels + 1):
        error = module.handle.DAQstop(channel)
        if error < 0:
            log.info("Stopping Digitizer failed! - {}".format(error))
    

def loadWaves(module):
    for pulseDescriptor in module.pulseDescriptors:
        if len(pulseDescriptor.pulses) > 1:
            waves = []
            for pulse in pulseDescriptor.pulses:
                samples = pulseLab.createPulse(module.sample_rate / 5,
                                            pulse.width,
                                            pulse.bandwidth,
                                            pulse.amplitude / 1.5,
                                            pulseDescriptor.pri,
                                            pulse.toa)
                if pulse.carrier != 0:
                    carrier = pulseLab.createTone(module.sample_rate, 
                                                  pulse.carrier,
                                                  0,
                                                  samples.timebase)
                    wave = samples.wave * carrier
                waves.append(samples.wave)

            wavesGroup = []
            #Plot the waves, before they are interweaved
            for wave in waves:
                subgroup = []
                subgroup.append([wave])
                wavesGroup.append(subgroup)
            wavesGroup.append([waves])
            title = "Waveform {} in module {}_{}".format(pulseDescriptor.id,
                                                      module.model,
                                                      module.slot)
            plotWaves(wavesGroup, module.sample_rate, title)
            wave = interweavePulses(waves)
        else:
            #not interleaved, so normal channel
            pulse = pulseDescriptor.pulses[0]
            samples = pulseLab.createPulse(module.sample_rate,
                                        pulse.width,
                                        pulse.bandwidth,
                                        pulse.amplitude / 1.5,
                                        pulseDescriptor.pri,
                                        pulse.toa)
            wave = samples.wave
            if pulse.carrier != 0:
                carrier = pulseLab.createTone(module.sample_rate, 
                                              pulse.carrier,
                                              0,
                                              samples.timebase)
                wave = wave * carrier
        waveform = key.SD_Wave()
        error = waveform.newFromArrayDouble(key.SD_WaveformTypes.WAVE_ANALOG, 
                                            wave)
        if error < 0:
            log.info("Error Creating Wave: {} {}".format(error,
                                                          key.SD_Error.getErrorMessage(error)))
        log.info("Loading waveform length: {} as ID: {} ".format(len(wave), 
                                                                 pulseDescriptor.id))
        error = module.handle.waveformLoad(waveform, pulseDescriptor.id)
        if error < 0:
            log.info("Error Loading Wave - {} {}".format(error,
                                                         key.SD_Error.getErrorMessage(error)))
                    
def enqueueWaves(module):
    for queue in module.queues:
        for item in queue.items:
            if item.trigger:
                trigger = key.SD_TriggerModes.SWHVITRIG
            else:
                trigger = key.SD_TriggerModes.AUTOTRIG
            start_delay = item.start_time / 10E-09 # expressed in 10ns
            start_delay = int(np.round(start_delay))
            log.info("Enqueueing: {} in channel {}".format(item.pulse_id, 
                                                           queue.channel))
            error = module.handle.AWGqueueWaveform(queue.channel, 
                                                    item.pulse_id, 
                                                    trigger, 
                                                    start_delay, 
                                                    1, 
                                                    0)
            if error < 0:
                log.info("Queueing waveform failed! - {}".format(error))
        log.info("Setting queue 'Cyclic' to {}".format(queue.cyclic))
        if queue.cyclic:
            queueMode = key.SD_QueueMode.CYCLIC
        else:
            queueMode = key.SD_QueueMode.ONE_SHOT
        error =module.handle.AWGqueueConfig(queue.channel, 
                                            queueMode)
        if error < 0:
            log.error("Configure cyclic mode failed! - {}".format(error))

        # This is only required for channels that implement the 'vanilla'
        # ModGain block. (It does no harm to other applications that do not).
        # It assumes that the source is to be directly from the AWG, rather 
        # than function generator.
        log.info("Setting Output Characteristics for channel {}".format(queue.channel))
        error = module.handle.channelWaveShape(queue.channel, key.SD_Waveshapes.AOU_AWG)
        if error < 0:
            log.warn("Error Setting Waveshape - {}".format(error))
        error = module.handle.channelAmplitude(queue.channel, 1.5)
        if error < 0:
            log.warn("Error Setting Amplitude - {}".format(error))
        module.handle.AWGstart(queue.channel)


def configureDig(chassis, module):
    log.info("Configuring DIG in slot {}...".format(module.slot))
    module.handle = key.SD_AIN()
    dig = module.handle
    error = dig.openWithSlotCompatibility('', 
                                          chassis, 
                                          module.slot,
                                          key.SD_Compatibility.KEYSIGHT)
    if error < 0:
        log.info("Error Opening - {}".format(error))
    _configureFpga(module)
   #Configure all channels to be DC coupled and 50 Ohm
    for channel in range(1, module.channels + 1):
        error = dig.DAQflush(channel)
        if error < 0:
            log.info("Error Flushing")
        log.info ("Configuring Digitizer in slot {}, Channel {}".format (module.slot,
                                                                      channel))
        error = dig.channelInputConfig( channel, 
                                        2.0,
                                        key.AIN_Impedance.AIN_IMPEDANCE_50,
                                        key.AIN_Coupling.AIN_COUPLING_DC)
        if error < 0:
            log.info("Error Configuring channel")

    for daq in module.daqs:
        log.info("Configuring Acquisition parameters for channel {}".format(daq.channel))
        if daq.trigger:
            trigger_mode = key.SD_TriggerModes.SWHVITRIG
        else:
            trigger_mode = key.SD_TriggerModes.AUTOTRIG
        trigger_delay = daq.triggerDelay * module.sample_rate  # expressed in samples
        trigger_delay = int(np.round(trigger_delay))
        pointsPerCycle = int(np.round(daq.captureTime * module.sample_rate))
        error = dig.DAQconfig(
            daq.channel,
            pointsPerCycle,
            daq.captureCount,
            trigger_delay,
            trigger_mode)
        if error < 0:
            log.info("Error Configuring Acquisition")
        log.info("Starting DAQ, channel {}".format(daq.channel))
        error = dig.DAQstart(daq.channel)
        if error < 0:
            log.info("Error Starting Digitizer")

def getDigDataRaw(module):
    TIMEOUT = 1000
    daqData = []
    for daq in module.daqs:
        channelData = []
        for capture in range(daq.captureCount):
            pointsPerCycle = int(np.round(daq.captureTime * module.sample_rate))
            dataRead = module.handle.DAQread(daq.channel,
                                             pointsPerCycle,
                                             TIMEOUT)
            if len(dataRead) != pointsPerCycle:
                log.warning("Slot:{} Attempted to Read {} samples, "
                            "actually read {} samples".format(module.slot, 
                                                              pointsPerCycle, 
                                                              len(dataRead)))
            channelData.append(dataRead)
        daqData.append(channelData)
    return(daqData)

def getDigData(module):
    LSB = 1 / 2**14
    samples = getDigDataRaw(module)
    for daqData in samples:
        for channelData in daqData:
            channelData = channelData * LSB
    return(samples)
      

def interweavePulses(pulses):
    interweaved = np.zeros(len(pulses[0]) * 5)
    for ii in range(len(pulses)):
        interweaved[ii::5] = pulses[ii]
    return interweaved

    
if (__name__ == '__main__'):
    main()