#!/usr/bin/python3

from assets.CommandLine import CommandLineArguments
from assets.Application import Application, FileDetectionEntry
from .Files.Module import ModuleDAT

# DEFINE THE FILE TYPES IN THIS APPLICATION.
file_detection_entries = [
    FileDetectionEntry(filename_regex = 'module.*\.dat$', case_sensitive = False, file_processor = ModuleDAT)
]

APPLICATION_NAME = 'Tonka'
APPLICATION_DESCRIPTION = 'Tonka Construction (1997)'

command_line_arguments = CommandLineArguments(APPLICATION_NAME, APPLICATION_DESCRIPTION).parse()
tonka = Application(APPLICATION_NAME, APPLICATION_DESCRIPTION)
tonka.process(command_line_arguments.input, file_detection_entries)

# EXPORT THE ASSETS, IF REQUESTED.
if command_line_arguments.export:
    tonka.export(command_line_arguments)
