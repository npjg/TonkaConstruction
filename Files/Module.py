
import os
import logging
from assets.File import File
from .Background import Background
from assets.Asserts import assert_equal
from .TonkaAsset import TonkaAsset

## Contains all the assets for a single scene.
## Each of these assets is stored in a chunk. 
class ModuleDAT(File):
    def __init__(self, filepath):
        # OPEN THE MODULE FILE.
        super().__init__(filepath)

        # REGISTER THE CHUNKS IN THIS FILE.
        # Each Module typically contains the assets for a single screen of the game,
        # and each of these assets is stored in a chunk. These chunks are referenced
        # by their byte position in this file.
        chunk_pointers = []
        chunk_count = self.uint16_le()
        logging.debug(f'Expecting {chunk_count} chunks in {filepath}')
        for index in range(chunk_count):
            chunk_pointer = self.uint32_le()
            chunk_pointers.append(chunk_pointer)
            logging.debug(f'Registered chunk {index + 1}\{chunk_count} @ 0x{chunk_pointer:012x}')
        # The pointer to the final chunk is the total length of this file.
        chunk_pointers.append(len(self.stream))
        assert_equal(self.uint16_le(), chunk_count)

        # TODO: I don't know what is here.
        self.unk1 = self.uint32_le()
        if self.unk1 != 0:
            logging.warning(f'Unk1: {self.unk1}')

        # READ THE BACKGROUND IMAGE FOR THIS SCREEN.
        # The background is always the first chunk of the module.
        end_of_background_pointer = chunk_pointers[0]
        background_size = end_of_background_pointer - self.stream.tell()
        logging.debug(f'*** CHUNK BACKGROUND (0x{self.stream.tell():012x} -> 0x{end_of_background_pointer:012x} [0x{background_size:04x} bytes]) ***')
        self.background = Background(self)
        # This is to ensure we are at the end of the background.
        assert_equal(self.position, chunk_pointers[0], "stream position")

        # READ EACH OF THE ASSETS IN THIS MODULE.
        for index in range(len(chunk_pointers) - 1):
            # RECORD THE LENGTH OF THIS ASSET.
            start_of_asset_pointer = chunk_pointers[index]
            end_of_asset_pointer = chunk_pointers[index + 1]
            asset_length = end_of_asset_pointer - start_of_asset_pointer
            logging.debug(f'*** CHUNK {index} (0x{start_of_asset_pointer:012x} -> 0x{end_of_asset_pointer:012x} [0x{asset_length:04x} bytes]) ***')

            # READ THE ASSET.
            # Ensure the stream is at the start of the asset.
            assert_equal(self.position, start_of_asset_pointer, "stream position")
            # Read the asset.
            asset = TonkaAsset(self)
            self.assets.append(asset)
    
    def export(self, filepath: str, command_line_arguments):
        # CALCULATE THE FOLDER FOR THIS FILE.
        file_filepath = super().export(filepath, command_line_arguments)

        # EXPORT THE BACKGROUND.
        # Because the background is not stored in the assets list,
        # it must be exported separately.
        background_filepath = os.path.join(file_filepath, self.filename)
        self.background.export(background_filepath, command_line_arguments.bitmap_format)
