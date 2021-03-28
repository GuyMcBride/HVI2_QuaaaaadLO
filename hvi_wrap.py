# -*- coding: utf-8 -*-
"""
Created on Tue Nov 24 08:29:02 2020

@author: Guy McBride
"""

import sys
import os
import logging
from dataclasses import dataclass, field
from collections import deque

sys.path.append(
    r"C:/Program Files/Keysight/PathWave Test Sync Executive 2020 Update 1.0/api/python"
)
import keysight_hvi as kthvi

sys.path.append(r"C:\Program Files (x86)\Keysight\SD1\Libraries\Python")
import keysightSD1 as key


log = logging.getLogger(__name__)

# Cached record of modules that are used in the HVI.
modules = None
system_definition = None
sequencer = None
current_sync_sequence = deque()
current_block = deque()
hvi_handle = None


@dataclass
class ModuleDescriptor:
    """Holds a 'description' of a used module """

    name: str
    events: [str] = field(default_factory=list)
    actions: [str] = field(default_factory=list)
    hvi_registers: [str] = field(default_factory=list)
    fpga: str = None
    handle: int = None
    _current_sequence = None


def define_system(name: str, **kwargs):
    global modules, system_definition, sequencer, current_sync_sequence
    pxi_triggers = [trigger for trigger in range(8)]

    defaultKwargs = {
        "chassis_list": [1],
        "pxi_triggers": pxi_triggers,
        "modules": [],
        "simulate": False,
    }
    kwargs = {**defaultKwargs, **kwargs}
    modules = kwargs["modules"]

    system_definition = kthvi.SystemDefinition(name)
    for chassis in kwargs["chassis_list"]:
        if kwargs["simulate"]:
            system_definition.chassis.add_with_options(
                chassis, "Simulate=True,DriverSetup=model=M9018B,NoDriver=True"
            )
        else:
            system_definition.chassis.add(chassis)

    # Add PXI trigger resources that we plan to use
    log.info("Adding PXIe triggers to the HVI environment...")
    pxiTriggers = []
    for trigger in kwargs["pxi_triggers"]:
        pxiTriggerName = "PXI_TRIGGER{}".format(trigger)
        pxiTrigger = getattr(kthvi.TriggerResourceId, pxiTriggerName)
        pxiTriggers.append(pxiTrigger)
    system_definition.sync_resources = pxiTriggers

    log.info("Adding modules to the HVI environment...")
    for module in kwargs["modules"]:
        module._current_sequence = deque()
        system_definition.engines.add(
            module.handle.hvi.engines.main_engine, module.name
        )
        log.info(f"...Declaring actions used by: {module.name}...")
        if module.actions is not None:
            if len(module.actions) == 0:
                actions = [
                    a for a in dir(module.handle.hvi.actions) if not a.startswith("_")
                ]
            else:
                actions = module.actions
            for action in actions:
                log.info(f"...adding: {action}")
                action_id = getattr(module.handle.hvi.actions, action)
                system_definition.engines[module.name].actions.add(action_id, action)

        log.info(f"...Declaring events used by: {module.name}...")
        if module.events is not None:
            if len(module.events) == 0:
                events = [
                    e for e in dir(module.handle.hvi.events) if not e.startswith("_")
                ]
            else:
                events = module.events
            for event in events:
                log.info(f"...adding: {event}")
                event_id = getattr(module.handle.hvi.events, event)
                system_definition.engines[module.name].events.add(event_id, event)

        # Register the FPGA resources used by HVI (exposes the registers)
        if module.fpga:
            log.info(f"...Declaring FPGA Registers used by: {module.name}...")
            system_definition.engines[module.name].fpga_sandboxes[0].load_from_k7z(
                os.getcwd() + "\\" + module.fpga
            )
        for register in system_definition.engines[module.name].fpga_sandboxes[0].fpga_registers:
            log.info(f"...... {register.name}")
            
    log.info("Creating Main Sequencer Block...")
    sequencer = kthvi.Sequencer(f"{name}_Sequencer", system_definition)
    current_sync_sequence.append(sequencer.sync_sequence)

    log.info("Declaring HVI registers...")
    scopes = sequencer.sync_sequence.scopes
    for module in kwargs["modules"]:
        for register in module.hvi_registers:
            log.info(
                f"...Adding register: {register}, "
                f"initial value: 0 to module: {module.name}"
            )
            registers = scopes[module.name].registers
            hviRegister = registers.add(register, kthvi.RegisterSize.SHORT)
            hviRegister.initial_value = 0
    return


def start():
    global hvi_handle
    log.info("Compiling HVI...")
    hvi_handle = sequencer.compile()
    log.info("Loading HVI to HW...")
    hvi_handle.load_to_hw()
    log.info("Starting HVI...")
    hvi_handle.run(hvi_handle.no_timeout)
    return


def close():
    log.info("Releasing HVI...")
    hvi_handle.release_hw()


def show_sequencer():
    return sequencer.sync_sequence.to_string(kthvi.OutputFormat.DEBUG)


# Helper Functions


def _get_module(name):
    return [i for i in modules if i.name == name][0]


def _get_current_sequence(module_name):
    return _get_module(module_name)._current_sequence[-1]


def _push_current_sequence(module_name, sequence):
    _get_module(module_name)._current_sequence.append(sequence)


def _pop_current_sequence(module_name):
    _get_module(module_name)._current_sequence.pop()


def _statement_name(sequence, name):
    statement_names = [s.name for s in sequence.statements if s.name.startswith(name)]
    if len(statement_names) == 0:
        statement_name = name
    else:
        statement_name = f"{name}_{len(statement_names)}"
    return statement_name


def _sync_statement_name(sequence, name):
    statement_names = [
        s.name for s in sequence.sync_statements if s.name.startswith(name)
    ]
    if len(statement_names) == 0:
        statement_name = name
    else:
        statement_name = f"{name}_{len(statement_names)}"
    return statement_name


# Syncronous Block Statements


def start_syncWhile_register(name, engine, register, comparison, value, delay=70):
    global current_sync_sequence
    sequence = current_sync_sequence[-1]
    statement_name = _sync_statement_name(sequence, name)
    whileRegister = sequencer.sync_sequence.scopes[engine].registers[register]
    comparison_operator = getattr(kthvi.ComparisonOperator, comparison)

    log.info(f"Creating Synchronized While loop, {value} iterations...")
    condition = kthvi.Condition.register_comparison(
        whileRegister, comparison_operator, value
    )
    while_sequence = sequencer.sync_sequence.add_sync_while(
        statement_name, delay, condition
    )
    current_sync_sequence.append(while_sequence.sync_sequence)
    return


def end_syncWhile():
    global current_sync_sequence
    current_sync_sequence.pop()


def start_sync_multi_sequence_block(name, delay=30):
    global current_block, modules
    sequence = current_sync_sequence[-1]
    statement_name = _sync_statement_name(sequence, name)
    block = sequence.add_sync_multi_sequence_block(statement_name, delay)
    current_block.append(block)
    for module in modules:
        module._current_sequence.append(block.sequences[module.name])
    return


def end_sync_multi_sequence_block():
    global current_block
    current_block.pop()
    for module in modules:
        module._current_sequence.pop()


# Native HVI Sequence Instructions


def if_register_comparison(name, module, register, comparison, value, delay=10):
    """
    Inserts an 'if' statement in the flow following instructions
    are only executed if condition evalutes to True. This should be terminated
    with
    """
    sequence = _get_current_sequence(module)
    statement_name = _statement_name(sequence, name)
    comparison_operator = getattr(kthvi.ComparisonOperator, comparison)
    if_condition = kthvi.Condition.register_comparison(
        register, comparison_operator, value
    )
    enable_matching_branches = True
    if_statement = sequence.add_if(
        statement_name, delay, if_condition, enable_matching_branches
    )
    _push_current_sequence(module, if_statement.if_branch.sequence)


def end_if(module):
    _pop_current_sequence(module)


def set_register(name, module, register, value, delay=10):
    """Sets <register> in <module> to <value>"""
    sequence = _get_current_sequence(module)
    statement_name = _statement_name(sequence, name)
    register_id = sequence.scope.registers[register]
    log.info(f"......{statement_name}")
    instruction = sequence.add_instruction(
        statement_name, delay, sequence.instruction_set.assign.id
    )
    instruction.set_parameter(
        sequence.instruction_set.assign.destination.id, register_id
    )
    instruction.set_parameter(sequence.instruction_set.assign.source.id, value)


def incrementRegister(name, module, register, delay=10):
    """Increments <register> in <module>"""
    addToRegister(name, module, register, 1, delay)


def addToRegister(name, module, register, value, delay=10):
    """Adds <value> to <register> in <module>"""
    sequence = _get_current_sequence(module)
    statement_name = _statement_name(sequence, name)
    register_id = sequence.scope.registers[register]
    log.info(f"......{statement_name}")
    instruction = sequence.add_instruction(
        statement_name, delay, sequence.instruction_set.add.id
    )
    instruction.set_parameter(sequence.instruction_set.add.destination.id, register_id)
    instruction.set_parameter(sequence.instruction_set.add.left_operand.id, register_id)
    instruction.set_parameter(sequence.instruction_set.add.right_operand.id, value)


def writeFpgaRegister(name, module, register, value, delay=10):
    """
    Writes <value> to module's FPGA register: <register>.

    name : title given to this instruction.
    register : name of the FPGA register
    value : to be written to the register
    """
    sequence = _get_current_sequence(module)
    statement_name = _statement_name(sequence, name)
    register_id = sequence.engine.fpga_sandboxes[0].fpga_registers[register]
    log.info(f"......{statement_name}")
    reg_cmd = sequence.instruction_set.fpga_register_write
    instruction = sequence.add_instruction(statement_name, delay, reg_cmd.id)
    instruction.set_parameter(reg_cmd.fpga_register.id, register_id)
    instruction.set_parameter(reg_cmd.value.id, value)


def execute_actions(name, module, actions, delay=10):
    """
    Adds an instruction called <name> to sequence for <engine> to the current block
    to execute all <actions>
    """
    sequence = _get_current_sequence(module)
    statement_name = _statement_name(sequence, name)
    log.info(f"......{statement_name}")
    actionCmd = sequence.instruction_set.action_execute
    actionParams = [sequence.engine.actions[action] for action in actions]
    instruction = sequence.add_instruction(statement_name, delay, actionCmd.id)
    instruction.set_parameter(actionCmd.action.id, actionParams)


def delay(name, module, delay=10):
    """
    Adds an instruction called <name> to sequence for <module> to the current block
    to delay for <delay> ns.
    """
    sequence = _get_current_sequence(module)
    statement_name = _statement_name(sequence, name)
    log.info(f"......{statement_name}")
    sequence.add_delay(name, delay)


# AWG specific HVI Sequence Instructions


def awg_set_amplitude(name, module, channel, value, delay=10):
    """
    Adds an instruction called <name> to <module>'s sequence to set amplitude
    of <channel> to <value>
    """
    module_name = module
    sequence = _get_current_sequence(module)
    statement_name = _statement_name(sequence, name)
    log.info(f"......{name}")
    for module in modules:
        if module.name == module_name:
            break
    command = module.handle.hvi.instruction_set.set_amplitude
    instruction = sequence.add_instruction(statement_name, delay, command.id)
    instruction.set_parameter(command.channel.id, channel)
    instruction.set_parameter(command.value.id, value)


if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)

    # Define a simple AWG 'test' module
    module = ModuleDescriptor(
        "AWG_0",
        hvi_registers=["loopcntr"],
    )

    module.handle = key.SD_AOU()
    module.handle.openWithOptions(
        "M3202A",
        0,
        2,
        "simulate=true, channelNumbering=Keysight",
    )

    # Create the main Sequencer and assign all the resources to be used
    define_system("Example HVI", modules=[module], simulate=True)

    # The first block executes a single instruction
    start_sync_multi_sequence_block("Set Amplitudes", 30)
    awg_set_amplitude("Set Amplitude CH1", module.name, 1, 0.5)
    end_sync_multi_sequence_block()

    # This sets up a while loop in which a block of two instructions
    # are repeated a number of times
    start_syncWhile_register(
        "AmplitudeLoop", module.name, "loopcntr", "LESS_THAN", 5, 70
    )
    start_sync_multi_sequence_block("Trigger", 260)
    execute_actions(
        "Trigger all",
        module.name,
        ["awg1_trigger", "awg2_trigger", "awg3_trigger", "awg4_trigger"],
    )
    awg_set_amplitude("Set Amplitude CH1", module.name, 1, 0.5)
    end_sync_multi_sequence_block()
    end_syncWhile()

    # Finally a block executes a single instruction.
    start_sync_multi_sequence_block("Set Amplitudes", 100)
    awg_set_amplitude("Set Amplitude CH1", module.name, 1, 0.5)
    end_sync_multi_sequence_block()

    log.info("")
    log.info("SEQUENCER - CREATED")
    log.info(show_sequencer())

    start()
    log.info("Waiting for stuff to happen...")
    time.sleep(1)
    # Tidy up
    close()
    module.handle.close()
    log.info("All Done!!")
