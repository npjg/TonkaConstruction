
import logging
import io
from enum import Enum

import self_documenting_struct as struct
from asset_extraction_framework.File import File
from asset_extraction_framework.Asset.Animation import Animation
from asset_extraction_framework.Asset.Image import RectangularBitmap
from asset_extraction_framework.Asset.Sound import Sound

## Each asset has a series of frames that can contain a still frame only, 
## audio and a still frame, or unnown data. All assets share this animation-
## like basic structure.
class Asset(Animation):
    # TODO: Refine these types.
    class AssetType(Enum):
        AUDIO_ONLY = 0
        EARTH_COMPONENT = 1
        TIMED_ANIMATION = 2
        CLICKABLE_STILL = 3
        SCRIPTED_ANIMATION = 4
        CURSOR = 5
        UNKNOWN = 6

    ## Specifices the contents of all frames in the asset.
    ## Provided once, at the start of the asset.
    class FrameContents(Enum):
        VIDEO_ONLY = 0x00
        AUDIO_AND_VIDEO = 0x08
        UNKNOWN = 0x0c

    ## Reads and parses a complete asset.
    ## \param[in,out] file - The module file that contains this asset.
    ##                The stream must be pointing to the first byte of the asset.
    def __init__(self, file: File):
        # SET THE METADATA.
        super().__init__()
        self.name = None
        self.alpha_color = 0x0f # Corresponds to 0x0dff0b in the palette.
        self.bitmaps_per_audio = 8

        # GET THE TYPE OF THE ASSET.
        # The asset type is determined by the first six bytes of the asset.
        # First, the type codes must be read.
        TYPE_CODE_COUNT = 3
        type_codes = []
        for _ in range(TYPE_CODE_COUNT):
            type_codes.append(struct.unpack.uint16_le(file.stream))
        # Then, the type codes are assigned to a human-readable type,
        # so the types are easier to manage.
        if type_codes == [0x00, 0x00, 0x00]:
            self.type = self.AssetType.AUDIO_ONLY
        elif type_codes == [0x00, 0x01, 0x01]:
            self.type = self.AssetType.EARTH_COMPONENT
        elif type_codes == [0x01, 0x01, 0x01]:
            self.type = self.AssetType.TIMED_ANIMATION
        elif type_codes == [0x02, 0x01, 0x01]:
            self.type = self.AssetType.CLICKABLE_STILL
        elif type_codes == [0x03, 0x01, 0x01]:
            self.type = self.AssetType.SCRIPTED_ANIMATION
        elif type_codes[0:2] == [0x01, 0x0c]:
            # The cursor type also stores cursor information in the type code.
            # TODO: Further specify these.
            self.type = self.AssetType.CURSOR
            self.cursor_directions = type_codes[-2]
            self.cursor_facets = type_codes[-1]
        else:
            # HALT ON AN UNKNOWN TYPE CODE.
            raise ValueError(f"Unknown asset type codes: {type_codes}")

        # CALCULATE THE NUMBER OF FRAMES IN THIS ANIMATION.
        frame_count = struct.unpack.uint16_le(file.stream)
        if self.type == self.AssetType.CURSOR:
            # For cursors, the frame count only indicates the number of .
            frame_count *= (self.cursor_directions * self.cursor_facets)

        # SET THE EXPECTED CONTENTS OF THE FRAMES IN THIS ASSET.
        # A frame can contain video only, video and audio, or have unknown contents.
        self.contents = self.FrameContents(struct.unpack.uint16_le(file.stream))

        # READ THE DIMENSIONS OF THE ANIMATION.
        # Note that these values might not be the true dimensions of the animation,
        # as would be calculated from the actual dimensions of the frames in the animation.
        self._width = struct.unpack.uint16_le(file.stream)
        self._height = struct.unpack.uint16_le(file.stream)

        # TODO: I don't know what's in here.
        self.unk1 = file.stream.read(0x56)

        # READ THE COORDINATES OF THE ANIMATION.
        self._left = struct.unpack.uint16_le(file.stream)
        self._top = struct.unpack.uint16_le(file.stream)

        # TODO: I don't know what's in here.
        self.unk2 = file.stream.read(0x04)

        # READ THE RESOLUTION OF THE ANIMATION. 
        # TODO: I don't think this is actually resolution.
        self.horizontal_resolution = struct.unpack.uint16_le(file.stream)
        self.vertical_resolution = struct.unpack.uint16_le(file.stream)

        # TODO: I don't know what's in here.
        self.unk3 = file.stream.read(0x0c)

        # READ THE HOTSPOT.
        # If this asset is not clickable, these will both be zero.
        self.hotspot_x = struct.unpack.uint16_le(file.stream)
        self.hotspot_y = struct.unpack.uint16_le(file.stream)

        # READ THE ANIMATION FRAME START POINTERS.
        if self.contents == self.FrameContents.VIDEO_ONLY:
            # These pointers are relative to the entire DAT file, not just this asset. 
            # Each points to the beginning of the header of a video frame in this animation.
            # For some reason, a pointer table is not provided for frames that also have audio.
            # These pointers are just ignored.
            frame_start_pointers = []
            for _ in range(frame_count):
                frame_start_pointers.append(file.stream.read(4))

        # READ THE ASSET FRAMES.
        for frame_id in range(frame_count):
            logging.debug(f" ### Frame {frame_id+1} of {frame_count} ###")
            # PARSE THE FRAME.
            # Frames can consist of only bitmap data or bitmap data followed by audio data.
            #
            # For animations with audio, the audio is interleaved such that audio occurs that lasts
            # the duration of the bitmap frames until the next occurrence of an audio chunk 
            # (or the end of the frame).
            # 
            # Note that this frequency effectively gives the framerate of the animation, since each 
            # audio chunk contains exactly one second of audio (or the remaining audio in the frame
            # if this is the last frame).
            #
            # Bitmap-only animations and frames between audio chunks have a single frame per iteration.
            asset_has_audio = (self.contents != self.FrameContents.VIDEO_ONLY)
            audio_expected_after_this_frame = (frame_id % self.bitmaps_per_audio == 0) and (asset_has_audio)
            frame = AssetFrame(file, frame_id, audio_expected = audio_expected_after_this_frame)

            # ADD ALL COMPLETE FRAMES TO THE BITMAP SET.
            # Extra frames should never exist in the first place, so they are just thrown away.
            if not frame.ignore_frame:
                frame._palette = file.background._palette
                self.frames.append(frame)

            # ADD ANY AUDIO TO THE AUDIO SET.
            if frame.audio is not None:
                self.sounds.append(frame.audio)

    ## Exports the assets in this module.
    ## \param[in] directory_path - The directory where the assets should be exported.
    ##            Asset exporters may create initial subdirectories.
    ## \param[in] command_line_arguments - All the command-line arguments provided to the 
    ##            script that invoked this function, so asset exporters can read any 
    ##            necessary formatting options.
    def export(self, directory_path: str, command_line_arguments):
        if not self.is_animation:
            # DISABLE ANIMATION EXPORT.
            # We want a discrete number of frames and/or audio files to be created,
            # rather than one animation file. Save the animation-related command line arguments.
            saved_bitmap_options = command_line_arguments.bitmap_options
            saved_animation_format = command_line_arguments.animation_format
            # Replace these arguments to disable animation export.
            command_line_arguments.bitmap_options = 'no_framing'
            command_line_arguments.animation_format = 'none'

            # EXPORT THE ASSET AS DISCRETE FRAMES/AUDIO FILES.
            super().export(directory_path, command_line_arguments)
            # Restore the former arguments.
            command_line_arguments.bitmap_options = saved_bitmap_options
            command_line_arguments.animation_format = saved_animation_format
        else:
            # EXPORT THE ASSET WITH THE REQUESTED SETTINGS.
            # Since this asset is an animation, we don't need to make
            # any change.
            super().export(directory_path, command_line_arguments)

    ## Returns True if the asset is an animation; False otherwise.
    ## Animation assets have bitmap frames intended to be placed in sequence,
    ## as an.. well.. animation. Non-animation assets only contain audio
    ## or they have a discrete set of bitmaps not intended to be placed as an
    ## animation. Instead, these assets are "libraries" with the appropriate 
    ## bitmap still frames chosen by the program.
    ##
    ## An asset's animation-ness determines how it is exported.
    @property
    def is_animation(self):
        # Cursors and audio-only assets are never animations.
        # Other asset types can be considered not animations
        # if they have a sufficiently few number of frames.
        DISCRETE_CUTOFF = 3
        return (self.type not in (self.AssetType.CURSOR, self.AssetType.AUDIO_ONLY)) and \
            (len(self.frames) > DISCRETE_CUTOFF)

    ## Returns True when the bitmap has unreasonably large dimensions.
    ## This usually indicates a parsing error or extra frame.
    @property
    def has_too_large_dimensions(self) -> bool:
        return (self.width > 0xffff) or (self.height > 0xffff)

## Reads and parses a frame in an asset.
## \param[in,out] file - The module file that contains this asset.
##                The stream must be pointing to the first byte of the asset.
## \param[in] frame_index - The position of this frame in the asset.
## \param[in] audio_expected - Whether or not to read audio in this frame.
##            If this is set but the frame indicates it has no audio,
##            no audio will be read.
class AssetFrame(RectangularBitmap):
    def __init__(self, file: File, frame_index: int, audio_expected = False):
        super().__init__()

        # MARK THE FRAME VALID.
        # The frame will be marked invalid if there are any problems parsing it.
        # If the frame is not marked valid, it will appear to have no dimensions.
        self.ignore_frame = False
        self.audio = None

        # READ THE FRAME'S DIMENSIONS.
        self._width = struct.unpack.uint32_le(file.stream)
        self._height = struct.unpack.uint32_le(file.stream)
        # On audio-only assets, sometimes there is a junk frame at the end.
        # Not sure why. They can be discarded.
        skip_frame = (self.is_inconsistent) or (self.has_too_large_dimensions)
        if skip_frame:
            # UN-READ ALL BYTES READ FOR THIS FRAME.
            # This data was not supposed to be consumed in the first place, as
            # it actually belongs to the next chunk of data. It is not a real frame.
            # Thus, the stream should be rewound as if this data was never read
            # as part of a frame.
            file.rewind(8)

            # END PARSING THIS FRAME.
            self.ignore_frame = True
            return

        # READ THE NOMINAL BITMAP SIZE, IN BYTES.
        self.uncompressed_image_size = struct.unpack.uint32_le(file.stream)
        self.compressed_image_data_size = struct.unpack.uint32_le(file.stream)

        # READ THE AUDIO LENGTH.
        # Each audio chunk stores exactly one second of audio at the given sampling frequency.
        self.audio_length_in_bytes = struct.unpack.uint32_le(file.stream)
        # Normally, each audio chunk stores exactly one second of audio at an 8-bit
        # sampling frequency (bitrate). Thus the number of bytes to read is the same
        # as the sampling frequency in Hertz.
        #
        # But for some reason, when the sampling frequency is 22.050kHz (0x5622) 
        # and this audio chunk is the first one read, the amount of audio present
        # is actually double the sampling frequency. So this adjustment made.
        first_frame = (frame_index == 0)
        double_audio_length = (first_frame == True) and (self.audio_length_in_bytes == 0x5622)
        if double_audio_length:
            self.audio_length_in_bytes *= 2

        # READ THE FRAME STARTING COORDINATES.
        self._left = struct.unpack.int16_le(file.stream)
        self._top = struct.unpack.int16_le(file.stream)

        # READ THE AUDIO FOR THIS FRAME.
        # Even when audio is expected, the audio length
        # could still be zero to indicate no audio is actually present.
        audio_available_to_read = (audio_expected) and (self.audio_length_in_bytes > 0)
        if audio_available_to_read:
            # TODO: Can we turn this into a memoryview? And only reference the original file?
            self.audio = Sound()
            self.audio._pcm = file.stream.read(self.audio_length_in_bytes)
            self.audio._big_endian = False
            self.audio._sample_width = 1
            self.audio._sample_rate = 22050
            self.audio._channel_count = 1

        # DECOMPRESS THE BITMAP FOR THIS FRAME.
        if self.compressed_image_data_size > 0:
            self.raw = file.stream.read(self.compressed_image_data_size)

    @property
    def pixels(self):
        if not self.ignore_frame and self.compressed_image_data_size > 0:
            self.decompress_bitmap()
            return self._pixels

    # \return True when the image has one zero and one nonzero dimension.
    # The image should not be processed in this state.
    @property
    def is_inconsistent(self) -> bool:
        return (self.width == 0 and self.height != 0) or (self.width != 0 and self.height == 0)

    ## Returns True when the bitmap has unreasonably large dimensions.
    ## This usually indicates a parsing error or extra frame.
    @property
    def has_too_large_dimensions(self) -> bool:
        return (self.width > 0xffff) or (self.height > 0xffff)

    ## Applies Apple PackBits to decompress the bitmap bitstream.
    def decompress_bitmap(self):
        # UNCOMPRESS THE COMPRESSED IMAGE STREAM.
        # First, we must have a empty place to put the uncompressed bytes.
        self._pixels = b''
        compressed_image_data = io.BytesIO(self.raw)
        compressed_image_data.seek(0)
        # Read the full number of compressed bytes.
        while compressed_image_data.tell() < self.compressed_image_data_size:
            # Read the operation byte. 
            n = struct.unpack.int8(compressed_image_data)
            # An operation byte inclusively between 0x00 (+0) and 0x7f (+127) indicates
            # an uncompressed run of the value of the operation byte plus one.
            if n >= 0 and n <= 127:
                run_length = n+1
                self._pixels += compressed_image_data.read(run_length)
            # An operation byte inclusively between 0x81 (-127) and 0xff (-1) indicates
            # the next byte is a color that should be repeated for a run of (-n+1) pixels.
            elif n >= -127 and n <= -1:
                color_byte = compressed_image_data.read(1)
                run_length = -n+1
                color_run = color_byte * run_length
                self._pixels += color_run
