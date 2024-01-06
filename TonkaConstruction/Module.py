
import os
import logging

import self_documenting_struct as struct
from asset_extraction_framework.File import File
from asset_extraction_framework.Asserts import assert_equal

from .Background import Background
from .Asset import Asset

## Contains all the assets for a single scene.
## Each of the assets is stored in a chunk in this file.
class Module(File):
    ## Parses the module.
    ## \param[in] filepath - The full path to the module file.
    def __init__(self, filepath: str):
        # OPEN THE MODULE FILE.
        super().__init__(filepath)

        # REGISTER THE CHUNKS IN THIS FILE.
        # Each Module typically contains the assets for a single screen of the game,
        # and each of these assets is stored in a chunk. These chunks are referenced
        # by their byte position in this file.
        chunk_pointers = []
        chunk_count = struct.unpack.uint16_le(self.stream)
        logging.debug(f'Expecting {chunk_count} chunks in {filepath}')
        for index in range(chunk_count):
            # REGISTER THIS CHUNK.
            chunk_pointer = struct.unpack.uint32_le(self.stream)
            chunk_pointers.append(chunk_pointer)
            logging.debug(f'Registered chunk {index + 1}\{chunk_count} @ 0x{chunk_pointer:012x}')
        # The pointer to the final chunk is the total length of this file.
        total_file_length = len(self.stream)
        chunk_pointers.append(total_file_length)
        # For some reason the chunk count is included twice.
        # We will just verify they are equal.
        redundant_chunk_count = struct.unpack.uint16_le(self.stream)
        assert_equal(redundant_chunk_count, chunk_count)
        # TODO: I don't know what is here.
        self.unk1 = struct.unpack.uint32_le(self.stream)
        logging.debug(f'Unk1: {self.unk1}')

        # READ THE BACKGROUND IMAGE FOR THIS SCREEN.
        # The background is always the first chunk of the module.
        end_of_background_pointer = chunk_pointers[0]
        background_size = end_of_background_pointer - self.stream.tell()
        logging.debug(f'*** CHUNK BACKGROUND (0x{self.stream.tell():012x} -> 0x{end_of_background_pointer:012x} [0x{background_size:04x} bytes]) ***')
        self.background = Background(self)
        # Ensure we are at the end of the background.
        self.assert_at_stream_position(chunk_pointers[0])

        # READ EACH OF THE ASSETS IN THIS MODULE.
        for index in range(len(chunk_pointers) - 1):
            # CALCULATE THE LENGTH OF THIS ASSET.
            start_of_asset_pointer = chunk_pointers[index]
            end_of_asset_pointer = chunk_pointers[index + 1]
            asset_length = end_of_asset_pointer - start_of_asset_pointer

            # READ THE ASSET.
            stream_at_start_of_asset = self.assert_at_stream_position(start_of_asset_pointer, warn_only = True)
            if not stream_at_start_of_asset:
                # Ensure the stream is at the start of the asset.
                # If we need to seek, a warning will be issued.
                # TODO: Figure out the instance where this is required.
                self.stream.seek(start_of_asset_pointer)
            # Read the asset.
            asset = Asset(self)
            self.assets.append(asset)
    
    ## Exports the assets in this module.
    ## \param[in] directory_path - The directory where the assets should be exported.
    ##            Asset exporters may create initial subdirectories.
    ## \param[in] command_line_arguments - All the command-line arguments provided to the 
    ##            script that invoked this function, so asset exporters can read any 
    ##            necessary formatting options.
    def export(self, directory_path: str, command_line_arguments):
        # EXPORT THE ASSETS IN THE ASSETS LIST.
        # The base class takes care of these.
        export_path = super().export(directory_path, command_line_arguments)

        # EXPORT THE BACKGROUND.
        # Because the background is not stored in the assets list,
        # it must be exported separately.
        self.background.export(export_path, command_line_arguments)
