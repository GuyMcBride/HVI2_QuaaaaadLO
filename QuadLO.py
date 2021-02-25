# -*- coding: utf-8 -*-
"""
Created on Fri Nov  6 16:45:52 2020

@author: gumcbrid
"""

import logging
import os
import sys
import time

import matplotlib.pyplot as plt
import numpy as np

sys.path.append(r"C:\Program Files (x86)\Keysight\SD1\Libraries\Python")
import keysightSD1 as key

import Configuration
import pulses as pulseLab
import hvi_wrap as hvi

log = logging.getLogger(__name__)

if len(sys.argv) > 1:
    configName = sys.argv[1]
else:
    configName = "latest"
log.info("Opening Config file: {})".format(configName))

config = Configuration.loadConfig(configName)


def main():
    configureModules()
    configure_hvi()
    hvi.start()

    log.info("Waiting for stuff to happen...")
    time.sleep(1)
    digData = []
    for module in config.modules:
        if module.model == "M3102A":
            digData.append(getDigData(module))
            sampleRate = module.sample_rate
    log.info("Closing down hardware...")
    hvi.close()
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
        log.error(
            "Finding Chassis: {} {}".format(
                chassis, key.SD_Error.getErrorMessage(chassis)
            )
        )
    log.info("Chassis found: {}".format(chassis))
    for module in config.modules:
        if module.model == "M3202A":
            configureAwg(chassis, module)
        elif module.model == "M3102A":
            configureDig(chassis, module)


def _configureFpga(module):
    if module.fpga.image_file != "":
        log.info(f"Loading FPGA image: {module.fpga.image_file}")
        error = module.handle.FPGAload(os.getcwd() + "\\" + module.fpga.image_file)
        if error < 0:
            log.error(
                f"Loading FPGA bitfile: {error} "
                f"{key.SD_Error.getErrorMessage(error)}"
            )

    log.info(f"Writing {len(module.fpga.pc_registers)} FPGA registers")
    for register in module.fpga.pc_registers:
        sbReg = module.handle.FPGAgetSandBoxRegister(register.name)
        error = sbReg.writeRegisterInt32(register.value)
        if error < 0:
            log.error(f"Error writing register: {register.name}")


def configureAwg(chassis, module):
    log.info(f"Configuring AWG in slot {module.slot}...")
    module.handle = key.SD_AOU()
    awg = module.handle
    error = awg.openWithSlotCompatibility(
        "", chassis, module.slot, key.SD_Compatibility.KEYSIGHT
    )
    if error < 0:
        log.info(f"Error Opening - {error}")
    _configureFpga(module)
    # Clear all queues and waveforms
    awg.waveformFlush()
    for channel in range(module.channels):
        awg.AWGflush(channel + 1)
    loadWaves(module)
    enqueueWaves(module)
    trigmask = 0
    for channel in range(module.channels):
        awg.channelWaveShape(channel + 1, key.SD_Waveshapes.AOU_AWG)


# Remove this if using HVI
#        trigmask = trigmask | 2**channel
#        log.info("triggering with {}".format(trigmask))
#        awg.AWGtriggerMultiple(trigmask)


def closeModules():
    for module in config.modules:
        if module.model == "M3202A":
            stopAwg(module)
        elif module.model == "M3102A":
            stopDig(module)
        if module.fpga.image_file != "":
            log.info(f"Loading FPGA image: {module.fpga.vanilla_file}")
            error = module.handle.FPGAload(
                os.getcwd() + "\\" + module.fpga.vanilla_file
            )
            if error < 0:
                log.error(
                    f"Loading FPGA bitfile: {error} "
                    f"{key.SD_Error.getErrorMessage(error)}"
                )
        module.handle.close()
    log.info("Finished stopping and closing Modules")


def stopAwg(module):
    log.info("Stopping AWG in slot {}...".format(module.slot))
    for channel in range(1, module.channels + 1):
        error = module.handle.AWGstop(channel)
        if error < 0:
            log.info(f"Stopping AWG failed! - {error}")


def stopDig(module):
    log.info(f"Stopping Digitizer in slot {module.slot}...")
    for channel in range(1, module.channels + 1):
        error = module.handle.DAQstop(channel)
        if error < 0:
            log.info(f"Stopping Digitizer failed! - {error}")


def loadWaves(module):
    for pulseDescriptor in module.pulseDescriptors:
        if len(pulseDescriptor.pulses) > 1:
            waves = []
            for pulse in pulseDescriptor.pulses:
                samples = pulseLab.createPulse(
                    module.sample_rate / 5,
                    pulse.width,
                    pulse.bandwidth,
                    pulse.amplitude / 1.5,
                    pulseDescriptor.pri,
                    pulse.toa,
                )
                if pulse.carrier != 0:
                    carrier = pulseLab.createTone(
                        module.sample_rate, pulse.carrier, 0, samples.timebase
                    )
                    wave = samples.wave * carrier
                waves.append(samples.wave)

            wavesGroup = []
            # Plot the waves, before they are interweaved
            for wave in waves:
                subgroup = []
                subgroup.append([wave])
                wavesGroup.append(subgroup)
            wavesGroup.append([waves])
            title = (
                f"Waveform {pulseDescriptor.id} in module {module.model}_{module.slot}"
            )
            #            plotWaves(wavesGroup, module.sample_rate, title)
            wave = interweavePulses(waves)
        else:
            # not interleaved, so normal channel
            pulse = pulseDescriptor.pulses[0]
            samples = pulseLab.createPulse(
                module.sample_rate,
                pulse.width,
                pulse.bandwidth,
                pulse.amplitude / 1.5,
                pulseDescriptor.pri,
                pulse.toa,
            )
            wave = samples.wave
            if pulse.carrier != 0:
                carrier = pulseLab.createTone(
                    module.sample_rate, pulse.carrier, 0, samples.timebase
                )
                wave = wave * carrier
        waveform = key.SD_Wave()
        error = waveform.newFromArrayDouble(key.SD_WaveformTypes.WAVE_ANALOG, wave)
        if error < 0:
            log.info(
                f"Error Creating Wave: {error} {key.SD_Error.getErrorMessage(error)}"
            )
        log.info(f"Loading waveform length: {len(wave)} as ID: {pulseDescriptor.id}")
        error = module.handle.waveformLoad(waveform, pulseDescriptor.id)
        if error < 0:
            log.info(
                f"Error Loading Wave - {error} {key.SD_Error.getErrorMessage(error)}"
            )


def enqueueWaves(module):
    for queue in module.queues:
        for item in queue.items:
            if item.trigger:
                trigger = key.SD_TriggerModes.SWHVITRIG
            else:
                trigger = key.SD_TriggerModes.AUTOTRIG
            start_delay = item.start_time / 10e-09  # expressed in 10ns
            start_delay = int(np.round(start_delay))
            log.info(f"Enqueueing: {item.pulse_id} in channel {queue.channel}")
            error = module.handle.AWGqueueWaveform(
                queue.channel, item.pulse_id, trigger, start_delay, 1, 0
            )
            if error < 0:
                log.info(f"Queueing waveform failed! - {error}")
        log.info(f"Setting queue 'Cyclic' to {queue.cyclic}")
        if queue.cyclic:
            queueMode = key.SD_QueueMode.CYCLIC
        else:
            queueMode = key.SD_QueueMode.ONE_SHOT
        error = module.handle.AWGqueueConfig(queue.channel, queueMode)
        if error < 0:
            log.error(f"Configure cyclic mode failed! - {error}")

        # This is only required for channels that implement the 'vanilla'
        # ModGain block. (It does no harm to other applications that do not).
        # It assumes that the source is to be directly from the AWG, rather
        # than function generator.
        log.info(f"Setting Output Characteristics for channel {queue.channel}")
        error = module.handle.channelWaveShape(queue.channel, key.SD_Waveshapes.AOU_AWG)
        if error < 0:
            log.warn(f"Error Setting Waveshape - {error}")
        error = module.handle.channelAmplitude(queue.channel, 1.5)
        if error < 0:
            log.warn(f"Error Setting Amplitude - {error}")
        module.handle.AWGstart(queue.channel)


def configureDig(chassis, module):
    log.info("Configuring DIG in slot {}...".format(module.slot))
    module.handle = key.SD_AIN()
    dig = module.handle
    error = dig.openWithSlotCompatibility(
        "", chassis, module.slot, key.SD_Compatibility.KEYSIGHT
    )
    if error < 0:
        log.info(f"Error Opening - {error}")
    _configureFpga(module)
    # Configure all channels to be DC coupled and 50 Ohm
    for channel in range(1, module.channels + 1):
        error = dig.DAQflush(channel)
        if error < 0:
            log.info("Error Flushing")
        log.info(f"Configuring Digitizer in slot {module.slot}, Channel {channel}")
        error = dig.channelInputConfig(
            channel,
            2.0,
            key.AIN_Impedance.AIN_IMPEDANCE_50,
            key.AIN_Coupling.AIN_COUPLING_DC,
        )
        if error < 0:
            log.info("Error Configuring channel")

    for daq in module.daqs:
        log.info(f"Configuring Acquisition parameters for channel {daq.channel}")
        if daq.trigger:
            trigger_mode = key.SD_TriggerModes.SWHVITRIG
        else:
            trigger_mode = key.SD_TriggerModes.AUTOTRIG
        trigger_delay = daq.triggerDelay * module.sample_rate  # expressed in samples
        trigger_delay = int(np.round(trigger_delay))
        pointsPerCycle = int(np.round(daq.captureTime * module.sample_rate))
        error = dig.DAQconfig(
            daq.channel, pointsPerCycle, daq.captureCount, trigger_delay, trigger_mode
        )
        if error < 0:
            log.info("Error Configuring Acquisition")
        log.info(f"Starting DAQ, channel {daq.channel}")
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
            dataRead = module.handle.DAQread(daq.channel, pointsPerCycle, TIMEOUT)
            if len(dataRead) != pointsPerCycle:
                log.warning(
                    f"Slot:{module.slot} Attempted to Read {pointsPerCycle} samples, "
                    f"actually read {len(dataRead)} samples"
                )
            if capture != 0:
                channelData.append(dataRead)
        daqData.append(channelData)
    return daqData


def getDigData(module):
    LSB = 1 / 2 ** 14
    samples = getDigDataRaw(module)
    for daqData in samples:
        for channelData in daqData:
            channelData = channelData * LSB
    return samples


def interweavePulses(pulses):
    interweaved = np.zeros(len(pulses[0]) * 5)
    for ii in range(len(pulses)):
        interweaved[ii::5] = pulses[ii]
    return interweaved


def configure_hvi():
    hvi_module_info = []
    for module in config.modules:
        hvi_module_info.append(
            hvi.ModuleDescriptor(
                name=module.name,
                hvi_registers=[reg.name for reg in module.hvi_registers],
                handle=module.handle,
                fpga=module.fpga.image_file,
            )
        )
    loop_count = config.hvi.get_constant("NumberOfLoops")
    gap = config.hvi.get_constant("Gap")

    """ Defines the complete HVI environment and HVI sequence"""
    # Create the main Sequencer and assign all the resources to be used
    hvi.define_system("QuadLo HVI", modules=hvi_module_info)

    hvi.start_sync_multi_sequence_block("Initialize", delay=30)
    # AWG_LEAD Instructions
    hvi.writeFpgaRegister(
        "deassert LO Phase Reset", "AWG_LEAD", "HVI_GLOBAL_PhaseReset", 0b0000
    )
    hvi.writeFpgaRegister(
        "Assert LO Phase Reset", "AWG_LEAD", "HVI_GLOBAL_PhaseReset", 0b1111
    )
    hvi.writeFpgaRegister(
        "deassert LO Phase Reset", "AWG_LEAD", "HVI_GLOBAL_PhaseReset", 0b0000
    )
    hvi.set_register("Clear Loop Counter", "AWG_LEAD", "LoopCounter", 0)
    # AWG_FOLLOW_0 Instructions
    hvi.writeFpgaRegister(
        "deassert LO Phase Reset", "AWG_FOLLOW_0", "HVI_GLOBAL_PhaseReset", 0b0000
    )
    hvi.writeFpgaRegister(
        "Assert LO Phase Reset", "AWG_FOLLOW_0", "HVI_GLOBAL_PhaseReset", 0b1111
    )
    hvi.writeFpgaRegister(
        "deassert LO Phase Reset", "AWG_FOLLOW_0", "HVI_GLOBAL_PhaseReset", 0b0000
    )

    hvi.start_syncWhile_register(
        "Main Loop", "AWG_LEAD", "LoopCounter", "LESS_THAN", loop_count, delay=70
    )
    if config.hvi.get_constant("ResetPhase"):
        hvi.start_sync_multi_sequence_block("Reset Phase", delay=260)
        # AWG_LEAD Instructions
        hvi.writeFpgaRegister(
            "Assert LO Phase Reset", "AWG_LEAD", "HVI_GLOBAL_PhaseReset", 0b1111
        )
        hvi.writeFpgaRegister(
            "deassert LO Phase Reset", "AWG_LEAD", "HVI_GLOBAL_PhaseReset", 0b0000
        )
        # AWG_FOLLOW_0 Instructions
        hvi.writeFpgaRegister(
            "Assert LO Phase Reset", "AWG_FOLLOW_0", "HVI_GLOBAL_PhaseReset", 0b1111
        )
        hvi.writeFpgaRegister(
            "deassert LO Phase Reset", "AWG_FOLLOW_0", "HVI_GLOBAL_PhaseReset", 0b0000
        )
        hvi.start_sync_multi_sequence_block("Trigger All")
    else:
        hvi.start_sync_multi_sequence_block("Trigger All", delay=260)
    # AWG_LEAD Instructions
    hvi.execute_actions(
        "Trigger All",
        "AWG_LEAD",
        ["awg1_trigger", "awg2_trigger", "awg3_trigger", "awg4_trigger"],
    )
    hvi.incrementRegister("Increment loop counter", "AWG_LEAD", "LoopCounter")
    hvi.delay("Wait Gap time", "AWG_LEAD", gap)
    # AWG_FOLLOW_0 Instructions
    hvi.execute_actions(
        "Trigger All",
        "AWG_FOLLOW_0",
        ["awg1_trigger", "awg2_trigger", "awg3_trigger", "awg4_trigger"],
    )
    # DIG_0 Instructions
    hvi.execute_actions(
        "Trigger All",
        "DIG_0",
        ["daq1_trigger", "daq2_trigger", "daq3_trigger", "daq4_trigger"],
    )
    hvi.end_syncWhile

    log.info("SEQUENCER - CREATED")
    log.info(hvi.show_sequencer())

    return


if __name__ == "__main__":
    main()
