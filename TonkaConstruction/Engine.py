#! python3

from asset_extraction_framework.CommandLine import CommandLineArguments
from asset_extraction_framework.Application import Application, FileDetectionEntry

from typing import List
from TonkaConstruction.Module import Module

# DEFINE THE FILE TYPES IN THIS APPLICATION.
def main(raw_command_line: List[str] = None):
    file_detection_entries = [
        FileDetectionEntry(filename_regex = 'module.*\.dat$', case_sensitive = False, file_processor = Module)]

    # PARSE THE COMMAND-LINE ARGUMENTS.
    APPLICATION_NAME = 'Tonka'
    APPLICATION_DESCRIPTION = 'Tonka Construction (1997)'
    command_line_arguments = CommandLineArguments(APPLICATION_NAME, APPLICATION_DESCRIPTION).parse(raw_command_line)

    # PARSE THE ASSETS.
    tonka = Application(APPLICATION_NAME)
    tonka.process(command_line_arguments.input, file_detection_entries)

    # EXPORT THE ASSETS, IF REQUESTED.
    if command_line_arguments.export:
        tonka.export(command_line_arguments)

# TODO: Get good documentation here.
if __name__ == '__main__':
    main()