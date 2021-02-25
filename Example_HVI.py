import time
import logging
import sys

sys.path.append(r"C:\Program Files (x86)\Keysight\SD1\Libraries\Python")
import keysightSD1 as key

import hvi_wrap as hvi

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Define a simple AWG 'test' module
module1 = hvi.ModuleDescriptor("AWG_0")
module2 = hvi.ModuleDescriptor("AWG_1")
modules = [module1, module2]

module1.handle = key.SD_AOU()
module1.handle.openWithOptions(
    "M3202A",
    1,
    2,
    "simulate=true, channelNumbering=Keysight",
)
module2.handle = key.SD_AOU()
module2.handle.openWithOptions(
    "M3202A",
    1,
    4,
    "simulate=true, channelNumbering=Keysight",
)

# Create the main Sequencer and assign all the resources to be used
hvi.define_system("Example HVI", modules=modules, simulate=True)

# Wrap this in one block so that triggering of all channels in the
# following while loop stay fully time aligned.
hvi.start_sync_multi_sequence_block("Set Amplitude Block", 30)
log.info("Creating Sequence for each module for Example Block...")
hvi.awg_set_amplitude("Set Amplitude CH1", module1.name, 1, 0.5)

# trigger all channels for all modules
hvi.start_sync_multi_sequence_block("Trigger all Block", 10)
for module in modules:
    hvi.execute_actions(
        "Trigger all",
        module.name,
        ["awg1_trigger", "awg2_trigger", "awg3_trigger", "awg4_trigger"],
    )

# End of HVI definition

log.info("")
log.info("SEQUENCER - CREATED")
log.info(hvi.show_sequencer())

hvi.start()
log.info("Waiting for stuff to happen...")
time.sleep(1)
# Tidy up
hvi.close()
for module in modules:
    module.handle.close()

log.info("All Done!!")
