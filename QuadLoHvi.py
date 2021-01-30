# -*- coding: utf-8 -*-
"""
Created on Tue Nov 24 08:29:02 2020

@author: Guy McBride
"""

import sys
import os
import logging

log = logging.getLogger(__name__)

sys.path.append(
    "C:/Program Files/Keysight/PathWave Test Sync Executive 2020/api/python"
)
import keysight_hvi as kthvi

_hvi = None
_config = None


def configure(config):
    global _hvi, _config
    _config = config
    hviSystem = _defineSystem()
    sequencer = _defineSequence(hviSystem)
    log.info("Compiling HVI...")
    _hvi = sequencer.compile()
    log.info("Loading HVI to HW...")
    _hvi.load_to_hw()
    log.info("Starting HVI...")
    _hvi.run(_hvi.no_timeout)


def close():
    log.info("Releasing HVI...")
    _hvi.release_hw()


def _defineSystem():
    sys_def = kthvi.SystemDefinition("QuadLoSystemDefinition")

    # Add Chassis resources to HVI System Definition
    sys_def.chassis.add_auto_detect()

    # Add PXI trigger resources that we plan to use
    log.info("Adding PXIe triggers to the HVI environment...")
    pxiTriggers = []
    for trigger in _config.hvi.triggers:
        pxiTriggerName = "PXI_TRIGGER{}".format(trigger)
        pxiTrigger = getattr(kthvi.TriggerResourceId, pxiTriggerName)
        pxiTriggers.append(pxiTrigger)
    sys_def.sync_resources = pxiTriggers

    log.info("Adding modules to the HVI environment...")
    for module in _config.modules:
        sys_def.engines.add(module.handle.hvi.engines.main_engine, module.name)

        # Register the AWG and DAQ trigger actions and create 'general' names
        # for these to help when they are actually used in instructions
        log.info(f"...Declaring actions used by: {module.name}...")
        if "AWG" in module.name:
            triggerRoot = "awg"
        elif "DIG" in module.name:
            triggerRoot = "daq"
        channels = int(module.handle.getOptions("channels")[-1])
        for channel in range(1, channels + 1):
            actionName = "trigger{}".format(channel)
            triggerName = f"{triggerRoot}{channel}_trigger"
            actionId = getattr(module.handle.hvi.actions, triggerName)
            sys_def.engines[module.name].actions.add(actionId, actionName)

        # Register the FPGA resources used by HVI (exposes the registers)
        if "AWG" in module.name:
            log.info(f"...Declaring FPGA Registers used by: {module.name}...")
            sys_def.engines[module.name].fpga_sandboxes[0].load_from_k7z(
                os.getcwd() + "\\" + module.fpga.image_file
            )
    return sys_def


def _defineSequence(hviSystem):
    """
    Defines the one and only synchronous sequencer for this HVI.
    This will contain a bunch MultiSequence Blocks each containing sequences
    for individual modules.
    """
    log.info("Creating Main Sequencer Block...")
    sequencer = kthvi.Sequencer("QuadLoSequencer", hviSystem)
    _declareHviRegisters(sequencer.sync_sequence)

    # Reset the LOs and intialize any registers
    _SyncMultiSequenceBlocks.initialize(sequencer.sync_sequence, 30)

    # Create the while loop for triggering all modules a number of times
    # and, perhaps, reseting the AWG phase Reset each time.
    sync_while = _SyncWhileBlocks.MainLoop(sequencer.sync_sequence)
    if _config.hvi.get_constant("ResetPhase"):
        _SyncMultiSequenceBlocks.reset_phase(sync_while.sync_sequence, 260)
        _SyncMultiSequenceBlocks.trigger(sync_while.sync_sequence)
    else:
        _MultiSequenceBlocks.trigger(sync_while.sync_sequence, 260)
    return sequencer


def _declareHviRegisters(sync_sequence):
    log.info("Declaring HVI registers...")
    scopes = sync_sequence.scopes
    for module in _config.modules:
        for register in module.hvi_registers:
            log.info(
                f"...Adding register: {register.name}, "
                f"initial value: {register.value} to module: {module.name}"
            )
            registers = scopes[module.name].registers
            hviRegister = registers.add(register.name, kthvi.RegisterSize.SHORT)
            hviRegister.initial_value = register.value


class _SyncWhileBlocks:
    def MainLoop(sync_sequence, delay=70):
        whileRegister = sync_sequence.scopes["AWG_LEAD"].registers["LoopCounter"]
        whileLoops = _config.hvi.get_constant("NumberOfLoops")
        log.info("Creating Synchronized While loop, {whileLoops}...")
        sync_while_condition = kthvi.Condition.register_comparison(
            whileRegister, kthvi.ComparisonOperator.LESS_THAN, whileLoops
        )
        sync_while = sync_sequence.add_sync_while(
            "sync_while", delay, sync_while_condition
        )
        return sync_while


class _SyncMultiSequenceBlocks:
    """
    All sequences for all modules sit within MultiSequenceBlocks. These blocks ensure
    that all the sequences for all the modules have finished before the block exits.
    Thus all modules stay synchronized as they leave the block.
    """

    def initialize(sync_sequence, delay=10):
        """
        In this block all modules are initialized:
            The AWGs are have all their LOs phase reset.
            The Lead AWG has its loop counter initialized.
            The Digitizers are unaffected.
        """
        block = sync_sequence.add_sync_multi_sequence_block("Initialize Block", delay)
        log.info("Creating Sequences for Initialization Block...")
        for engine in sync_sequence.engines:
            log.info(f"...Sequence for: {engine.name}")
            sequence = block.sequences[engine.name]
            if "AWG" in engine.name:
                _Statements.writeFpgaRegister(sequence, "HVI_GLOBAL_PhaseReset", 0b0000)
                _Statements.writeFpgaRegister(sequence, "HVI_GLOBAL_PhaseReset", 0b1111)
                _Statements.writeFpgaRegister(sequence, "HVI_GLOBAL_PhaseReset", 0b0000)
            if "AWG_LEAD" in engine.name:
                _Statements.setRegister(sequence, "LoopCounter", 0)
        return

    def reset_phase(sync_sequence, delay=10):
        """
        The AWGs are have all their LOs phase reset.
        The Digitizers are unaffected.
        """
        block = sync_sequence.add_sync_multi_sequence_block("Reset Phase Block", delay)
        log.info("Creating Sequences for Reset Phase Block...")
        for engine in sync_sequence.engines:
            log.info(f"...Sequence for: {engine.name}")
            sequence = block.sequences[engine.name]
            if "AWG" in engine.name:
                _Statements.writeFpgaRegister(sequence, "HVI_GLOBAL_PhaseReset", 0b0000)
                _Statements.writeFpgaRegister(sequence, "HVI_GLOBAL_PhaseReset", 0b1111)
                _Statements.writeFpgaRegister(sequence, "HVI_GLOBAL_PhaseReset", 0b0000)
        return

    def trigger(sync_sequence, delay=10):
        """
        In this block all modules are triggered:
            All channels of the AWGs are triggered.
            All channels of the Digitizers are triggered.
            The 'Lead AWG' decrements its loop counter and delays for a time
             defined in 'Gap' constant.
        """
        block = sync_sequence.add_sync_multi_sequence_block("Trigger Block", delay)
        log.info("Creating Sequences for Trigger Block...")
        for engine in sync_sequence.engines:
            log.info(f"...Sequence for: {engine.name}")
            sequence = block.sequences[engine.name]
            _Statements.triggerAll(sequence)
            if "AWG_LEAD" in engine.name:
                _Statements.incrementRegister(sequence, "LoopCounter")
                gap = _config.hvi.get_constant("Gap")
                log.info(f"......Adding delay of {gap} ns")
                sequence.add_delay("Gap delay", gap)
        return


class _Statements:
    """
    The syntax of adding instructions to the HVI sequence can be
     verbose and cumbersome.
    This class provides a more succinct way af adding these instructions
     in the form of 'Statements'.
    """

    def triggerAll(sequence):
        inst_name = "TriggerAll"
        statement_name = f"{inst_name}_{sequence.statements.count}"
        log.info(f"......{inst_name}")
        actionCmd = sequence.instruction_set.action_execute
        actionParams = [
            sequence.engine.actions["trigger1"],
            sequence.engine.actions["trigger2"],
            sequence.engine.actions["trigger3"],
            sequence.engine.actions["trigger4"],
        ]
        instruction = sequence.add_instruction(statement_name, 20, actionCmd.id)
        instruction.set_parameter(actionCmd.action.id, actionParams)

    def setRegister(sequence, name, value, delay=10):
        inst_name = f"Set HVI register {name} to {value}"
        register = sequence.scope.registers[name]
        # instruction names must be unique, so use satement count as 'uniquifyer'
        statement_name = f"{inst_name}_{sequence.statements.count}"
        log.info(f"......{inst_name}")
        instruction = sequence.add_instruction(
            name, delay, sequence.instruction_set.assign.id
        )
        instruction.set_parameter(
            sequence.instruction_set.assign.destination.id, register
        )
        instruction.set_parameter(sequence.instruction_set.assign.source.id, 0)

    def incrementRegister(sequence, name, delay=10):
        inst_name = f"Increment register {name}"
        register = sequence.scope.registers[name]
        # instruction names must be unique, so use satement count as 'uniquifyer'
        statement_name = f"{inst_name}_{sequence.statements.count}"
        log.info(f"......{inst_name}")
        instruction = sequence.add_instruction(
            statement_name, delay, sequence.instruction_set.add.id
        )
        instruction.set_parameter(sequence.instruction_set.add.destination.id, register)
        instruction.set_parameter(
            sequence.instruction_set.add.left_operand.id, register
        )
        instruction.set_parameter(sequence.instruction_set.add.right_operand.id, 1)

    def writeFpgaRegister(sequence, name, value):
        """
        Writes <value> to module's FPGA register: <name>.

        sequence : instance of modules sequencer within the HVI Sync Block
        name : name of the HVI register
        value : to be written to the register
        """
        inst_name = f"Set FPGA register {name} to {value}"
        register = sequence.engine.fpga_sandboxes[0].fpga_registers[name]
        # instruction names must be unique, so use satement count as 'uniquifyer'
        statement_name = f"{inst_name}_{sequence.statements.count}"
        log.info(f"......{inst_name}")
        regCmd = sequence.instruction_set.fpga_register_write
        instruction = sequence.add_instruction(statement_name, 10, regCmd.id)
        instruction.set_parameter(regCmd.fpga_register.id, register)
        instruction.set_parameter(regCmd.value.id, value)
