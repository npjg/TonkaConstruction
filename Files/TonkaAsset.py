
import logging
import io
from assets.Asset.Animation import Animation
from assets.Asset.Image import RectangularBitmap
from assets.Asset.Sound import Sound
from enum import Enum

# Rather interestingly, each asset in this game
# is in an animation-like structure.
class TonkaAsset(Animation):
    # TODO: Refine these types.
    class AssetTypes(Enum):
        AUDIO_ONLY = 0
        EARTH_COMPONENT = 1
        TIMED_ANIMATION = 2
        CLICKABLE_STILL = 3
        SCRIPTED_ANIMATION = 4
        CURSOR = 5
        UNKNOWN = 6

    class FrameContents(Enum):
        VIDEO_ONLY = 0x00
        AUDIO_AND_VIDEO = 0x08
        UNKNOWN = 0x0c

    def __init__(self, file):
        super().__init__()
        self.alpha_color = 0x0f # Corresponds to 0x0dff0b in the palette.
        self.bitmaps_per_audio = 8

        # GET THE TYPE OF THE ASSET.
        # The asset type is determined by the first six bytes of the asset.
        # First, the type codes must be read.
        TYPE_CODE_COUNT = 3
        type_codes = []
        for _ in range(TYPE_CODE_COUNT):
            type_codes.append(file.uint16_le())
        # Then, the type codes are assigned to a human-readable type,
        # so the types are easier to manage.
        if type_codes == [0x00, 0x00, 0x00]:
            self.type = self.AssetTypes.AUDIO_ONLY
        elif type_codes == [0x00, 0x01, 0x01]:
            self.type = self.AssetTypes.EARTH_COMPONENT
        elif type_codes == [0x01, 0x01, 0x01]:
            self.type = self.AssetTypes.TIMED_ANIMATION
        elif type_codes == [0x02, 0x01, 0x01]:
            self.type = self.AssetTypes.CLICKABLE_STILL
        elif type_codes == [0x03, 0x01, 0x01]:
            self.type = self.AssetTypes.SCRIPTED_ANIMATION
        elif type_codes[0:2] == [0x01, 0x0c]:
            # The cursor type also stores cursor information in the type code.
            self.type = self.AssetTypes.CURSOR
            self.cursor_directions = type_codes[-2]
            self.cursor_facets = type_codes[-1]
        else:
            # HALT ON AN UNKNOWN TYPE CODE.
            raise ValueError(f"Unknown asset type codes: {type_codes}")

        # CALCULATE THE NUMBER OF FRAMES IN THIS ANIMATION.
        frame_count = file.uint16_le()
        if self.type == self.AssetTypes.CURSOR:
            # For cursors, the frame count only indicates the number of .
            frame_count *= self.cursor_directions * self.cursor_facets

        # SET THE EXPECTED CONTENTS OF THIS FRAME.
        # A frame can contain video only, video and audio, or have unknown contents.
        self.contents = self.FrameContents(file.uint16_le())

        # READ THE DIMENSIONS OF THE ANIMATION.
        # Note that these values might not be the true dimensions of the animation,
        # as would be calculated from the actual dimensions of the frames in the animation.
        self._width = file.uint16_le()
        self._height = file.uint16_le()

        # TODO: I don't know what's in here.
        self.unk1 = file.read(0x56)

        # READ THE COORDINATES OF THE ANIMATION.
        self._left = file.uint16_le()
        self._top = file.uint16_le()

        # TODO: I don't know what's in here.
        self.unk2 = file.read(0x04)

        # READ THE RESOLUTION OF THE ANIMATION. 
        # TODO: I don't think this is actually resolution.
        self.horizontal_resolution = file.uint16_le()
        self.vertical_resolution = file.uint16_le()

        # TODO: I don't know what's in here.
        self.unk3 = file.read(0x0c)

        # READ THE HOTSPOT.
        # If this asset is not clickable, these will both be zero.
        self.hotspot_x = file.uint16_le()
        self.hotspot_y = file.uint16_le()

        # READ THE ANIMATION FRAME START POINTERS.
        if self.contents == self.FrameContents.VIDEO_ONLY:
            # These pointers are relative to the entire DAT file, not just this asset. 
            # Each points to the beginning of the header of a video frame in this animation.
            # For some reason, a pointer table is not provided for frames that also have audio.
            # These pointers are just ignored.
            frame_start_pointers = []
            for _ in range(frame_count):
                frame_start_pointers.append(file.read(4))

        # READ THE ANIMATION FRAMES.
        for frame_id in range(frame_count):
            logging.debug(f" ### Frame {frame_id+1} of {frame_count} ###")

            # PARSE THE FRAME.
            # For animations with audio, the audio is interleaved such that audio occurs that lasts
            # the duration of the video frames until the next occurrence of an audio chunk 
            # (or the end of the frame).
            # 
            # Note that this frequency effectively gives the framerate of the video, since each 
            # audio chunk contains exactly one second of audio (or the remaining audio in the frame
            # if this is the last frame).
            #
            # Video-only animations and frames between audio chunk_count have a single frame per iteration.
            audio_expected = (self.contents != self.FrameContents.VIDEO_ONLY) and \
                (frame_id % self.bitmaps_per_audio == 0)
            frame = TonkaAssetFrame(file, frame_id, read_audio = audio_expected)

            # ADD ALL COMPLETE FRAMES TO THE BITMAP SET.
            # Extra frames should never exist in the first place, so they are just thrown away.
            if not frame.ignore_frame:
                frame.palette = file.background.palette
                self.bitmaps.append(frame)

            # ADD ANY FOUND AUDIO TO THE AUDIO SET.
            if frame.audio is not None:
                # CREATE A SOUND ASSET.
                sound = Sound()
                sound.pcm = frame.audio
                sound.audio_type = 'u16le'
                sound.bitrate = '11.025k'
                sound.channel_count = 1
                self.audios.append(sound)

    def export(self, filepath, command_line_arguments):
        if self.is_discrete:
            # DISABLE ANIMATION EXPORT.
            # Save the animation-related command line arguments.
            saved_bitmap_options = command_line_arguments.bitmap_options
            saved_animation_format= command_line_arguments.animation_format
            # Replace these arguments to disable animation export.
            command_line_arguments.bitmap_options = 'no_framing'
            command_line_arguments.animation_format = 'none'
            # Export the asset discretely, regardless of the settings.
            super().export(filepath, command_line_arguments)
            # Restore the former arguments.
            command_line_arguments.bitmap_options = saved_bitmap_options
            command_line_arguments.animation_format = saved_animation_format
        else:
            # EXPORT THE ASSET WITH THE REQUESTED SETTINGS.
            super().export(filepath, command_line_arguments)

    @property
    def is_discrete(self):
        # These asset types have frames not intended to be played continuously, as an animation.
        # Instead, these asset types are "libraries" with the appropriate frames chosen under program control.
        # There are also other animations that are sometimes discrete if the frame count is low enough.
        DISCRETE_CUTOFF = 3
        return (self.type == self.AssetTypes.CURSOR) or \
            (self.type == self.AssetTypes.AUDIO_ONLY) or \
            (len(self.bitmaps) <= DISCRETE_CUTOFF)

class TonkaAssetFrame(RectangularBitmap):
    def __init__(self, file, frame_index, read_audio = False):
        super().__init__()

        # MARK THE FRAME VALID.
        # The frame will be marked invalid if there are any problems parsing it.
        # If the frame is not marked valid, it will appear to have no dimensions.
        self.ignore_frame = False
        self.audio = None

        # READ THE FRAME'S DIMENSIONS.
        self._width = file.uint32_le()
        self._height = file.uint32_le()
        # On audio_only chunks, sometimes there is one more frame than
        # necessary. Not sure why. But here we just discard those frames.
        frame_has_dimensions_too_large = self.width > 0xffff or self.height > 0xffff
        skip_frame = (self.is_inconsistent) or (frame_has_dimensions_too_large)
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

        # READ THE NOMINAL IMAGE SIZES, IN BYTES.
        self.uncompressed_image_size = file.uint32_le()
        self.compressed_image_data_size = file.uint32_le()

        # READ THE AUDIO BITRATE.
        # Each audio chunk stores exactly one second of audio at the given sampling frequency.
        self.bitrate = file.uint32_le()

        # READ THE FRAME STARTING COORDINATES.
        self._left = file.int16_le()
        self._top = file.int16_le()

        # READ THE AUDIO FOR THIS FRAME.
        # The presence of audio affects the position of other non-audio-related elements,
        # so these are also read in a different order depending on whether audio is expected.
        if read_audio and self.bitrate > 0:
            # Normally, each audio chunk stores exactly one second of audio at the given sampling frequency (bitrate).
            # Thus the number of bytes to read is the same as the sampling frequency in Hertz.
            # But for some reason, when the sampling frequency is 22.050kHz (0x5622) and this audio chunk is the first one read,
            # the amount of audio present is actually double the sampling frequency. So this adjustment made.
            first_frame = frame_index == 0
            # Even when audio is expected, the self.bitrate could still be zero to indicate no audio is actually present.
            double_bitrate = (first_frame == True) and (self.bitrate == 0x5622)
            if double_bitrate:
                self.bitrate *= 2
            self.audio = file.read(self.bitrate)

        self.raw = file.read(self.compressed_image_data_size)
        self.decompress_bitmap()

    def decompress_bitmap(self):
        # UNCOMPRESS THE COMPRESSED IMAGE STREAM.
        # The compression algorithm is Apple's PackBits.
        # First, we must have a empty place to put the uncompressed bytes.
        self.pixels = b''
        compressed_image_data = io.BytesIO(self.raw)
        compressed_image_data.seek(0)
        # Read the full number of compressed bytes.
        while compressed_image_data.tell() < self.compressed_image_data_size:
            # Read the operation byte. 
            n = int.from_bytes(compressed_image_data.read(1), byteorder="little", signed=True)
            # An operation byte inclusively between 0x00 (+0) and 0x7f (+127) indicates
            # an uncompressed run of the value of the operation byte plus one.
            if n >= 0 and n <= 127:
                run_length = n+1
                self.pixels += compressed_image_data.read(run_length)
            # An operation byte inclusively between 0x81 (-127) and 0xff (-1) indicates
            # the next byte is a color that should be repeated for a run of (-n+1) pixels.
            elif n >= -127 and n <= -1:
                color_byte = compressed_image_data.read(1)
                run_length = -n+1
                color_run = color_byte * run_length
                self.pixels += color_run
