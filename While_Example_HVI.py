import time
import logging
import sys

sys.path.append(r"C:\Program Files (x86)\Keysight\SD1\Libraries\Python")
import keysightSD1 as key

import hvi_wrap as hvi

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Define a simple AWG 'test' module
module = hvi.ModuleDescriptor("AWG_0", hvi_registers=["loopcntr"])

module.handle = key.SD_AOU()
module.handle.openWithOptions(
    "M3202A",
    0,
    2,
    "simulate=true, channelNumbering=Keysight",
)

# Create the main Sequencer and assign all the resources to be used
hvi.define_system("Example HVI", modules=[module], simulate=True)

# The first block sets the amplitude on just one module
# This is initialization code for relevant modules.
hvi.start_sync_multi_sequence_block("Set Amplitudes", 30)
hvi.set_register("Zero loop counter", module.name, "loopcntr", 0)

# This sets up a while loop (based on a register incrementing)
# in which a block of two instructions
# are repeated a number of times
hvi.start_syncWhile_register(
    "AmplitudeLoop", module.name, "loopcntr", "LESS_THAN", 5, 70
)
# This block that contains the instructions. All instructions
# must be in a sync_block
hvi.start_sync_multi_sequence_block("Trigger", 260)
hvi.execute_actions(
    "Trigger all",
    module.name,
    ["awg1_trigger", "awg2_trigger", "awg3_trigger", "awg4_trigger"],
)
hvi.awg_set_amplitude("Set Amplitude CH1", module.name, 1, 0.5)
hvi.incrementRegister("Increment Loop Counter", module.name, "loopcntr")
# Marks the end of the while block. There could be several sync_blocks
# within the while loop
hvi.end_syncWhile()

# Finally a block executes a single instruction.
hvi.start_sync_multi_sequence_block("Set Amplitudes", 100)
hvi.awg_set_amplitude("Set Amplitude CH1", module.name, 1, 0.5)

log.info("")
log.info("SEQUENCER - CREATED")
log.info(hvi.show_sequencer())

hvi.start()
log.info("Waiting for stuff to happen...")
time.sleep(1)
# Tidy up
hvi.close()
module.handle.close()
log.info("All Done!!")
