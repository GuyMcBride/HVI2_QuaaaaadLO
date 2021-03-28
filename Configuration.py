# -*- coding: utf-8 -*-
"""
Created on Fri Nov  6 09:08:30 2020

@author: gumcbrid
"""

import os
import yaml
import json
from dataclasses import dataclass, field
import logging.config


def setup_logging(
    default_path="logging.json", default_level=logging.INFO, env_key="LOG_CFG"
):
    """Setup logging configuration"""
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, "rt") as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


setup_logging()

log = logging.getLogger(__name__)


@dataclass
class QueueItem:
    pulse_id: int
    trigger: bool
    start_time: float
    cycles: int


@dataclass
class Queue:
    channel: int
    cyclic: bool
    items: [QueueItem]


@dataclass
class Register:
    name: str = ""
    value: int = 0


@dataclass
class Fpga:
    image_file: str = ""
    vanilla_file: str = ""
    pc_registers: [Register] = field(default_factory=list)
    hvi_registers: [Register] = field(default_factory=list)

    def get_hvi_register_value(self, name):
        return [i.value for i in self.hvi_registers if i.name == name][0]

@dataclass
class SubPulseDescriptor:
    carrier: float
    width: float
    toa: float
    amplitude: float
    bandwidth: float


@dataclass
class PulseDescriptor:
    id: int
    pri: float()
    pulses: [SubPulseDescriptor] = field(default_factory=list)


@dataclass
class ModuleDescriptor:
    name: str
    model: str
    channels: int
    sample_rate: float
    slot: int
    fpga: Fpga
    hvi_registers: [Register]


@dataclass
class AwgDescriptor(ModuleDescriptor):
    pulseDescriptors: [PulseDescriptor]
    queues: [Queue] = field(default_factory=list)
    handle: int = 0


@dataclass
class DaqDescriptor:
    channel: int
    captureTime: float
    captureCount: int
    trigger: bool
    triggerDelay: int = 0


@dataclass
class DigDescriptor(ModuleDescriptor):
    daqs: [DaqDescriptor]
    handle: int = 0


@dataclass
class HviConstant:
    name: str = ""
    value: int = 0


@dataclass
class Hvi:
    triggers: [int]
    modules: [ModuleDescriptor]
    constants: [HviConstant] = field(default_factory=list)

    def get_constant(self, constant):
        return [i.value for i in self.constants if i.name == constant][0]


@dataclass
class Config:
    modules: [ModuleDescriptor]
    hvi: Hvi

    def get_module(self, name):
        return [i for i in self.modules if i.name == name][0]


def loadConfig(configFile: str = "latest"):
    if configFile == "latest":
        if os.path.exists("./config_hist"):
            latest_hist = 0
            for file in os.listdir("./config_hist"):
                name = os.path.splitext(file)[0]
                hist = int(name.split("_")[-1])
                if hist > latest_hist:
                    latest_hist = hist
            configFile = "./config_hist/config_" + str(latest_hist) + ".yaml"
        else:
            configFile = "config_default.yaml"

    with open(configFile, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    log.info("Opened: {}".format(configFile))
    return config
