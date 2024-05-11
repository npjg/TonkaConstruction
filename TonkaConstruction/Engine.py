#! python3

from typing import List
import os

from asset_extraction_framework.CommandLine import CommandLineArguments
from asset_extraction_framework.Application import Application

from TonkaConstruction.Module import Module

class TonkaConstruction(Application):
    def __init__(self, application_name: str):
        super().__init__(application_name)
        self.modules = []

    def process(self, input_paths):
        # READ EACH OF THE MODULES.
        matched_module_filepaths = self.find_matching_files(input_paths, r'module.*\.dat$', case_sensitive = False)
        for module_filepath in matched_module_filepaths:
            print(f'INFO: Processing {module_filepath}')
            module = Module(module_filepath)
            self.modules.append(module)

    def export_assets(self, command_line_arguments):
            application_export_subdirectory: str = os.path.join(command_line_arguments.export, self.application_name)
            for index, module in enumerate(self.modules):
                print(f'INFO: Exporting assets in {module.filepath}')
                module.export_assets(application_export_subdirectory, command_line_arguments)

    # This is in a separate function becuase even on fast computers it 
    # can take a very long time and often isn't necessary.
    def export_metadata(self, command_line_arguments):
        application_export_subdirectory: str = os.path.join(command_line_arguments.export, self.application_name)
        for module in self.modules:
            print(f'INFO: Exporting metadata for {module.filename}')
            module.export_metadata(application_export_subdirectory)

# DEFINE THE FILE TYPES IN THIS APPLICATION.
def main(raw_command_line: List[str] = None):
    # PARSE THE COMMAND-LINE ARGUMENTS.
    APPLICATION_NAME: str = 'Tonka'
    APPLICATION_DESCRIPTION: str = 'Tonka Construction (1997)'
    command_line_arguments = CommandLineArguments(APPLICATION_NAME, APPLICATION_DESCRIPTION).parse(raw_command_line)

    # PARSE THE ASSETS.
    tonka: TonkaConstruction = TonkaConstruction(APPLICATION_NAME)
    tonka.process(command_line_arguments.input)

    # EXPORT THE ASSETS, IF REQUESTED.
    if command_line_arguments.export:
        tonka.export_assets(command_line_arguments)
        tonka.export_metadata(command_line_arguments)

# TODO: Get good documentation here.
if __name__ == '__main__':
    main()