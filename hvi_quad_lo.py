import logging
import time
import hvi_wrap as hvi

log = logging.getLogger(__name__)


def check_status(config):
    #    register_runtime = hvi.sync_sequence.scopes["AWG_LEAD"].registers["LoopCounter"]
    #    count = register_runtime.read
    loop_counter = hvi.read_register_runtime("AWG_LEAD", "LoopCounter")
    while loop_counter < 0:
        log.info(f"loop: {loop_counter}")
        loop_counter = hvi.read_register_runtime("AWG_LEAD", "LoopCounter")
    AB = hvi.read_register_runtime("AWG_LEAD", "AB")
    log.info(f"Multiplier result: {AB}")
    return True


def configure_hvi(config):
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
    iteration_count = config.hvi.get_constant("NumberOfIterations")
    frequency_increment = config.hvi.get_constant("FrequencyIncrement")
    phase_increment = config.hvi.get_constant("PhaseIncrement")
    amplitude_increment = config.hvi.get_constant("AmplitudeIncrement")
    gap = config.hvi.get_constant("Gap")
    trigger_awgs = ["awg1_trigger", "awg2_trigger", "awg3_trigger", "awg4_trigger"]
    trigger_daqs = ["daq1_trigger", "daq2_trigger", "daq3_trigger", "daq4_trigger"]

    """ Defines the complete HVI environment and HVI sequence"""
    # Create the main Sequencer and assign all the resources to be used
    hvi.define_system("QuadLo HVI", modules=hvi_module_info)

    hvi.start_sync_multi_sequence_block("Initialize", delay=30)
    # AWG_LEAD Instructions
    lo_freq_0A = config.get_module("AWG_LEAD").fpga.get_hvi_register_value(
        "HVI_CH1_PhaseIncA0"
    )
    lo_freq_0B = config.get_module("AWG_LEAD").fpga.get_hvi_register_value(
        "HVI_CH1_PhaseIncB0"
    )
    lo_amplitude = config.get_module("AWG_LEAD").get_register_value("AmplitudeIterator")
    ch1_offset = config.get_module("AWG_LEAD").fpga.get_hvi_register_value(
        "HVI_CH1_Offset"
    )
    ch4_offset = config.get_module("AWG_LEAD").fpga.get_hvi_register_value(
        "HVI_CH4_Offset"
    )

    hvi.set_register(
        "Set Initial Frequency", "AWG_LEAD", "FrequencyIterator", lo_freq_0A
    )
    hvi.writeFpgaRegister("Set CH1 LO0A", "AWG_LEAD", "HVI_CH1_PhaseIncA0", lo_freq_0A)
    hvi.writeFpgaRegister("Set CH1 LO0B", "AWG_LEAD", "HVI_CH1_PhaseIncB0", lo_freq_0B)

    hvi.writeFpgaRegister("Set CH3 LO0A", "AWG_LEAD", "HVI_CH3_PhaseIncA0", lo_freq_0A)
    hvi.writeFpgaRegister("Set CH3 LO0B", "AWG_LEAD", "HVI_CH3_PhaseIncB0", lo_freq_0B)

    hvi.writeFpgaRegister("Set CH4 LO0A", "AWG_LEAD", "HVI_CH4_PhaseIncA0", lo_freq_0A)
    hvi.writeFpgaRegister("Set CH4 LO0B", "AWG_LEAD", "HVI_CH4_PhaseIncB0", lo_freq_0B)

    hvi.writeFpgaRegister("Set CH1 Offset", "AWG_LEAD", "HVI_CH1_Offset", ch1_offset)
    hvi.writeFpgaRegister("Set CH4 Offset", "AWG_LEAD", "HVI_CH4_Offset", ch4_offset)

    hvi.set_register(
        "Set Initial Amplitude", "AWG_LEAD", "AmplitudeIterator", lo_amplitude
    )
    hvi.delay("Wait for register", "AWG_LEAD", 60)
    hvi.writeFpgaRegister(
        "Set CH1 LO Amplitude", "AWG_LEAD", "HVI_CH1_Amplitude0", "AmplitudeIterator"
    )
    hvi.writeFpgaRegister(
        "Set CH3 LO Amplitude", "AWG_LEAD", "HVI_CH3_Amplitude0", "AmplitudeIterator"
    )
    hvi.writeFpgaRegister(
        "Set CH4 LO Amplitude", "AWG_LEAD", "HVI_CH4_Amplitude0", "AmplitudeIterator"
    )

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
    hvi.set_register("Clear Iteration Counter", "AWG_LEAD", "IterationCounter", 0)

    # Test the multiplier function
    hvi.writeFpgaRegister("Set multA", "AWG_LEAD", "HVI_GLOBAL_MultA", 0x3)
    hvi.writeFpgaRegister("Set multB", "AWG_LEAD", "HVI_GLOBAL_MultB", 0x4)
    hvi.readFpgaRegister("Read multAB", "AWG_LEAD", "HVI_GLOBAL_MultAB", "AB", delay=20)

    # Test adding to queue
    mode = hvi.key.SD_TriggerModes.SWHVITRIG
    hvi.awg_queue_wave("Test Queuing", "AWG_LEAD", 3, 1, mode, "LoopCounter")

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
    hvi.end_sync_multi_sequence_block()

    hvi.start_syncWhile_register(
        "Main Loop",
        "AWG_LEAD",
        "IterationCounter",
        "LESS_THAN",
        iteration_count,
        delay=80,
    )
    hvi.start_syncWhile_register(
        "Iteration Loop", "AWG_LEAD", "LoopCounter", "LESS_THAN", loop_count, delay=570
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
        hvi.end_sync_multi_sequence_block()
        hvi.start_sync_multi_sequence_block("Trigger All")
    else:
        hvi.start_sync_multi_sequence_block("Trigger All", delay=260)

    # AWG_LEAD Instructions
    hvi.execute_actions("Trigger All", "AWG_LEAD", trigger_awgs)
    hvi.incrementRegister("Increment loop counter", "AWG_LEAD", "LoopCounter")
#    hvi.delay("Wait Gap time", "AWG_LEAD", "GapIterator")
    hvi.delay("Wait Gap time", "AWG_LEAD", gap)

    # AWG_FOLLOW_0 Instructions
    hvi.execute_actions("Trigger All", "AWG_FOLLOW_0", trigger_awgs)

    # DIG_0 Instructions
    hvi.execute_actions("Trigger All", "DIG_0", trigger_daqs)
    hvi.end_sync_multi_sequence_block()
    hvi.end_syncWhile()

    # End Iteration Loop
    hvi.start_sync_multi_sequence_block("Change Frequency", delay=260)
    # AWG_LEAD Instructions
    hvi.set_register("Clear Loop Counter", "AWG_LEAD", "LoopCounter", 0)
    hvi.incrementRegister("Increment Iteration counter", "AWG_LEAD", "IterationCounter")
#    hvi.addToRegister(
#        "Increment Frequency", "AWG_LEAD", "FrequencyIterator", frequency_increment
    hvi.subtractFromRegister(
        "Increment Frequency", "AWG_LEAD", "FrequencyIterator", frequency_increment
    )
    hvi.addToRegister("Increment Phase", "AWG_LEAD", "PhaseIterator", phase_increment)
    hvi.addToRegister(
        "Increment Amplitude", "AWG_LEAD", "AmplitudeIterator", amplitude_increment
    )
    hvi.delay("Wait for register", "AWG_LEAD", 60)
    hvi.writeFpgaRegister(
        "Set CH1 LO Amplitude",
        "AWG_LEAD",
        "HVI_CH1_Amplitude0",
        "AmplitudeIterator",
    )
    hvi.writeFpgaRegister(
        "Set CH3 LO Amplitude",
        "AWG_LEAD",
        "HVI_CH3_Amplitude0",
        "AmplitudeIterator",
    )
    hvi.writeFpgaRegister(
        "Set CH4 LO Amplitude",
        "AWG_LEAD",
        "HVI_CH4_Amplitude0",
        "AmplitudeIterator",
    )
    hvi.writeFpgaRegister(
        "Set Frequency CH1", "AWG_LEAD", "HVI_CH1_PhaseIncA0", "FrequencyIterator"
    )
    hvi.writeFpgaRegister(
        "Set Frequency CH3", "AWG_LEAD", "HVI_CH3_PhaseIncA0", "FrequencyIterator"
    )
    hvi.writeFpgaRegister(
        "Set Frequency CH4", "AWG_LEAD", "HVI_CH4_PhaseIncA0", "FrequencyIterator"
    )
    hvi.writeFpgaRegister(
        "Set Phase CH1", "AWG_LEAD", "HVI_CH1_Phase0", "PhaseIterator"
    )
    hvi.writeFpgaRegister(
        "Set Phase CH3", "AWG_LEAD", "HVI_CH3_Phase0", "PhaseIterator"
    )
    hvi.writeFpgaRegister(
        "Set Phase CH4", "AWG_LEAD", "HVI_CH4_Phase0", "PhaseIterator"
    )
    hvi.end_sync_multi_sequence_block()
    hvi.end_syncWhile()
    # End Main Loop
    log.info("SEQUENCER - CREATED")
    log.info(hvi.show_sequencer())
    return


def start():
    return hvi.start()


def close():
    return hvi.close()
