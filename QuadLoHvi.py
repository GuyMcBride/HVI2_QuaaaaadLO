# -*- coding: utf-8 -*-
"""
Created on Tue Nov 24 08:29:02 2020

@author: Guy McBride
"""

import sys
import os
import logging

log = logging.getLogger(__name__)

sys.path.append('C:/Program Files/Keysight/PathWave Test Sync Executive 2020/api/python')
import keysight_hvi as kthvi

_hvi = None

def configure(config):
    global _hvi
    hviSystem = _defineSystem(config)
    sequencer = _defineSequences(config, hviSystem)
    log.info("Compiling HVI...")
    _hvi = sequencer.compile()
    log.info("Loading HVI to HW...")
    _hvi.load_to_hw()
    log.info("Starting HVI...")
    _hvi.run(_hvi.no_timeout)
    
def close():
    log.info("Releasing HVI...")
    _hvi.release_hw()


def _defineSystem(config):
    sys_def = kthvi.SystemDefinition("QuadLoSystemDefinition")
    
    # Add Chassis resources to HVI System Definition
    sys_def.chassis.add_auto_detect()
    
    # Add PXI trigger resources that we plan to use
    pxiTriggers = []
    for trigger in config.hvi.triggers:
        pxiTriggerName = "PXI_TRIGGER{}".format(trigger)
        pxiTrigger = getattr(kthvi.TriggerResourceId, pxiTriggerName)
        pxiTriggers.append(pxiTrigger)
    sys_def.sync_resources = pxiTriggers
    
    log.info("Adding modules to the HVI environment...")
    for module in config.modules:
        engine_name = "{}_{}".format(module.model, module.slot)
        sys_def.engines.add(module.handle.hvi.engines.main_engine,
                            engine_name)

        # Register the AWG and DAQ trigger actions and create 'general' names
        # for these to help when they are actually used in instructions
        log.info("Adding actions to {} that will be used by HVI...".format(engine_name))
        if module.model == "M3202A":
            triggerRoot = 'awg'
        elif module.model == "M3102A":
            triggerRoot = 'daq'
        channels =  int(module.handle.getOptions('channels')[-1])
        for channel in range(1, channels + 1):
            actionName = 'trigger{}'.format(channel)
            triggerName = '{}{}_trigger'.format(triggerRoot, channel)
            actionId = getattr(module.handle.hvi.actions, triggerName)
            sys_def.engines[engine_name].actions.add(actionId, actionName)
        
        # Register the FPGA resources used by HVI (exposes the registers)
        if module.model == "M3202A":
            sys_def.engines[engine_name].fpga_sandboxes[0].load_from_k7z(os.getcwd() + '\\' + module.fpga.file_name)
    return(sys_def)

    
def _defineSequences(config, hviSystem):
    log.info("Creating Main Sequencer Block...")
    sequencer = kthvi.Sequencer("QuadLoSequencer", hviSystem)
    _declareFpgaRegisters(config, sequencer)
    #Reset the LOs and intialize any registers
    reset_block = sequencer.sync_sequence.add_sync_multi_sequence_block("ResetPhase", 30)
    _resetPhaseSequence(reset_block.sequences['M3202A_2'])
    _resetPhaseSequence(reset_block.sequences['M3202A_4'])
    #Issue triggers to all AWGs and DAQ channels
    sync_block = sequencer.sync_sequence.add_sync_multi_sequence_block("TriggerAll", 30)
    _triggerAllSequence(sync_block.sequences['M3202A_2'])
    _triggerAllSequence(sync_block.sequences['M3202A_4'])
    _triggerAllSequence(sync_block.sequences['M3102A_7'])
    return(sequencer)

def _declareFpgaRegisters(config, sequencer):
    for module in config.hvi.modules:
        for register in module.fpga.hviRegisters:
            engine_name = "{}_{}".format(module.model, module.slot)
            registers = sequencer.sync_sequence.scopes[engine_name].registers
            phaseReset = registers.add(register.name, kthvi.RegisterSize.SHORT)
            phaseReset.initial_value = register.value

def _resetPhaseSequence(sequence):
    regCmd = sequence.instruction_set.fpga_register_write
    phaseReset_register = sequence.engine.fpga_sandboxes[0].fpga_registers["Register_Bank_PhaseReset"]
    instruction = sequence.add_instruction("AssertPhaseReset", 60, regCmd.id)
    instruction.set_parameter(regCmd.fpga_register.id, phaseReset_register)
    instruction.set_parameter(regCmd.value.id, 1)
    instruction = sequence.add_instruction("DisassertPhaseReset", 60, regCmd.id)
    instruction.set_parameter(regCmd.fpga_register.id, phaseReset_register)
    instruction.set_parameter(regCmd.value.id, 0)

def _triggerAllSequence(sequence):
    log.info("Creating Sequence for Main AWG ({})...".format(sequence.engine.name))
    log.info("...Add 'Trigger All' instruction to triggerAWGs on all channels...")
    actionCmd = sequence.instruction_set.action_execute
    actionParams = [sequence.engine.actions['trigger1'],
                    sequence.engine.actions['trigger2'],
                    sequence.engine.actions['trigger3'],
                    sequence.engine.actions['trigger4']]
    instruction = sequence.add_instruction("Trigger All Channels", 
                                           10, 
                                           actionCmd.id)
    instruction.set_parameter(actionCmd.action.id, actionParams)
    