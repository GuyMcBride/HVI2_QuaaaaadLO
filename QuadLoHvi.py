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
            sys_def.engines[engine_name].fpga_sandboxes[0].load_from_k7z(os.getcwd() + '\\' + module.fpga.image_file)
    return(sys_def)

    
def _defineSequences(config, hviSystem):
    log.info("Creating Main Sequencer Block...")
    sequencer = kthvi.Sequencer("QuadLoSequencer", hviSystem)
    _declareHviRegisters(config, sequencer)
    #Reset the LOs and intialize any registers
    reset_block = sequencer.sync_sequence.add_sync_multi_sequence_block("ResetPhase", 30)
# TODO: Fix this when HVI iteration issue fixed 
    for ii in range(len(hviSystem.engines)):
        if 'M32' in hviSystem.engines[ii].name:
            _Sequences.resetPhase(reset_block.sequences[hviSystem.engines[ii].name])

    #Issue triggers to all AWGs and DAQ channels
    sync_block = sequencer.sync_sequence.add_sync_multi_sequence_block("TriggerAll", 220)
# TODO: Fix this when HVI iteration issue fixed 
    log.info("Creating Sequences for Triggering Loop...")
    for ii in range(len(hviSystem.engines)):
        _Sequences.triggerLoop(sync_block.sequences[hviSystem.engines[ii].name])
    return(sequencer)

def _declareHviRegisters(config, sequencer):
# TODO: Fix this when HVI iiteration issue fixed 
    log.info("Creating registers for triggering Loop...")
    for constant in config.hvi.constants:
        engines = sequencer.sync_sequence.engines
        scopes = sequencer.sync_sequence.scopes
        for ii in range(len(scopes)):
            scope = scopes[ii]
            log.info("Adding register: {} to engine: {}".format(constant.name, 
                                                                engines[ii].name))
            registers = scope.registers
            register = registers.add(constant.name, kthvi.RegisterSize.SHORT)
            register.initial_value = constant.value
        

class _Sequences:
    def resetPhase(sequence):
        phaseReset_register = sequence.engine.fpga_sandboxes[0].fpga_registers["Register_Bank_PhaseReset"]
        # Set the Phase Reset line to the LOs low
        _Statements.writeFpgaRegister(sequence, 'Pre Phase Reset', phaseReset_register, 0)
        # Set the Phase Reset line to the LOs High (cause them to enter 'reset state')
        _Statements.writeFpgaRegister(sequence, 'Phase Reset', phaseReset_register, 0)
        # Set the Phase Reset line to the LOs low (cause them to start up)
        _Statements.writeFpgaRegister(sequence, 'Post Phase Reset', phaseReset_register, 0)
    
    def triggerLoop(sequence):
        whileSequence = _Statements.whileLoop(sequence, 
                                              "Loop Triggers",
                                              sequence.scope.registers['NumberOfLoops'])
        _Statements.triggerAll(whileSequence, "Trigger All Channels")
        _Statements.decrementRegister(whileSequence, 
                                         "Decrement Loop Counter", 
                                         sequence.scope.registers['NumberOfLoops'],
                                         200000)
    

class _Statements:
    def whileLoop(sequence, name, loopCounter):
        log.info("...Add 'While...' instruction to {}...".format(sequence.engine.name))
        condition = kthvi.Condition.register_comparison(loopCounter, 
                                                        kthvi.ComparisonOperator.GREATER_THAN, 
                                                        1)
        whileLoop = sequence.add_while(name, 70, condition)
        return(whileLoop.sequence)

    def triggerAll(sequence, name):
        log.info("...Add 'TriggerAll' instruction to {}...".format(sequence.engine.name))
        actionCmd = sequence.instruction_set.action_execute
        actionParams = [sequence.engine.actions['trigger1'],
                        sequence.engine.actions['trigger2'],
                        sequence.engine.actions['trigger3'],
                        sequence.engine.actions['trigger4']]
        instruction = sequence.add_instruction(name, 
                                               100, 
                                               actionCmd.id)
        instruction.set_parameter(actionCmd.action.id, actionParams)
    
    def decrementRegister(sequence, name, counter, delay = 10):
        log.info("...Add 'Decrement loop counter' instruction to {}...".format(sequence.engine.name))
        instruction = sequence.add_instruction(name, 
                                               delay, 
                                               sequence.instruction_set.subtract.id)
        instruction.set_parameter(sequence.instruction_set.subtract.destination.id, counter)
        instruction.set_parameter(sequence.instruction_set.subtract.left_operand.id, counter)
        instruction.set_parameter(sequence.instruction_set.subtract.right_operand.id, 1)
    
    def writeFpgaRegister(sequence, name, register, value):
        log.info("...Add {} instruction to {}...".format(name,
                                                         sequence.engine.name))
        regCmd = sequence.instruction_set.fpga_register_write
        instruction = sequence.add_instruction(name, 
                                               60, 
                                               regCmd.id)
        instruction.set_parameter(regCmd.fpga_register.id, register)
        instruction.set_parameter(regCmd.value.id, 0)
