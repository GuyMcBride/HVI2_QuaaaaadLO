import time
import logging
import hvi_wrap as hvi

log = logging.getLogger(__name__)


def check_status(config):
    versionReg = config.get_module("DIG_0").handle.FPGAgetSandBoxRegister(
        "PC_CH1_Version"
    )
    averagesReg = config.get_module("DIG_0").handle.FPGAgetSandBoxRegister(
        "PC_CH1_Averages"
    )
    triggersReg = config.get_module("DIG_0").handle.FPGAgetSandBoxRegister(
        "PC_CH1_Triggers"
    )
    durationReg = config.get_module("DIG_0").handle.FPGAgetSandBoxRegister(
        "PC_CH1_Duration"
    )
    statusReg = config.get_module("DIG_0").handle.FPGAgetSandBoxRegister(
        "PC_CH1_Status"
    )
    for i in range(2):
        time.sleep(1)
        log.info(f"Version: {versionReg.readRegisterInt32()}")
        log.info(f"Averages: {averagesReg.readRegisterInt32()}")
        log.info(f"Triggers: {triggersReg.readRegisterInt32()}")
        log.info(f"Duration: {durationReg.readRegisterInt32()}")
        log.info(f"Status: {statusReg.readRegisterInt32()}")
    return True


def configure_digitizer(module):
    controlReg = module.handle.FPGAgetSandBoxRegister("PC_CH1_Control")
    prescalerReg = module.handle.FPGAgetSandBoxRegister("PC_CH1_Prescaler")
    samplesReg = module.handle.FPGAgetSandBoxRegister("PC_CH1_Samples")
    flagsReg = module.handle.FPGAgetSandBoxRegister("PC_CH1_Flags")
    averagesReg = module.handle.FPGAgetSandBoxRegister("PC_CH1_Log2Averages")
    points_per_cycle = int(round(module.daqs[0].captureTime * module.sample_rate))
    log.info(f"Setting averager samples to {points_per_cycle}")
    samplesReg.writeRegisterInt32(points_per_cycle)
    log.info(f"Enabling Averager...")
    controlReg.writeRegisterInt32(0x2)
    controlReg.writeRegisterInt32(0x1)

    return



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
    gap = config.hvi.get_constant("Gap")
    trigger_awgs = ["awg1_trigger", "awg2_trigger", "awg3_trigger", "awg4_trigger"]
    trigger_daqs = ["daq1_trigger", "daq2_trigger", "daq3_trigger", "daq4_trigger"]

    """ Defines the complete HVI environment and HVI sequence"""
    # Create the main Sequencer and assign all the resources to be used
    hvi.define_system("FrameAverager HVI", modules=hvi_module_info)

    hvi.start_sync_multi_sequence_block("Initialize", delay=30)
    # AWG_LEAD Instructions
    hvi.set_register("Clear Loop Counter", "AWG_LEAD", "LoopCounter", 0)
    hvi.set_register("Clear Iteration Counter", "AWG_LEAD", "IterationCounter", 0)
    hvi.end_sync_multi_sequence_block()

    hvi.start_syncWhile_register(
        "Main Loop",
        "AWG_LEAD",
        "IterationCounter",
        "LESS_THAN",
        iteration_count,
        delay=70,
    )
    hvi.start_syncWhile_register(
        "Iteration Loop", "AWG_LEAD", "LoopCounter", "LESS_THAN", loop_count, delay=570
    )
    hvi.start_sync_multi_sequence_block("Trigger All", delay=260)
    # AWG_LEAD Instructions
    hvi.execute_actions("Trigger All", "AWG_LEAD", trigger_awgs)
    hvi.incrementRegister("Increment loop counter", "AWG_LEAD", "LoopCounter")
    hvi.delay("Wait Gap time", "AWG_LEAD", gap)
    # DIG_0 Instructions
    hvi.execute_actions("Trigger All", "DIG_0", trigger_daqs)
    hvi.end_sync_multi_sequence_block()
    hvi.end_syncWhile()  # Iteration Loop

    hvi.start_sync_multi_sequence_block("Change Frequency", delay=260)
    hvi.set_register("Clear Loop Counter", "AWG_LEAD", "LoopCounter", 0)
    hvi.incrementRegister("Increment Iteration counter", "AWG_LEAD", "IterationCounter")
    hvi.delay("Wait Gap time", "AWG_LEAD", 100)
    hvi.end_sync_multi_sequence_block()
    hvi.end_syncWhile()  # Main Loop

    log.info("SEQUENCER - CREATED")
    log.info(hvi.show_sequencer())
    return


def start():
    return hvi.start()


def close():
    return hvi.close()
