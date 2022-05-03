#!/usr/bin/python3

import argparse
import logging
from re import A
import struct
import os
import enum
from pathlib import Path
import glob
import mmap
import io
import subprocess
import uuid
import json

from mrcrowbar.utils import hexdump
from PIL import Image

class AssetTypes(enum.Enum):
    AUDIO_ONLY = 0
    EARTH_COMPONENT = 1
    TIMED_ANIMATION = 2
    CLICKABLE_STILL = 3
    SCRIPTED_ANIMATION = 4
    CURSOR = 5
    UNKNOWN = 6

class FrameContents(enum.Enum):
    VIDEO_ONLY = 0x00
    AUDIO_AND_VIDEO = 0x08
    UNKNOWN = 0x0c

class FrameValidationStatus(enum.Enum):
    VALID = 0
    EMPTY_FRAME = 1
    EXTRA_FRAME = 2
    COORDINATE_OUT_OF_BOUNDS = 3
    AUDIO_ONLY = 4

class BoundingBox:
    def __init__(self, top = None, left = None, bottom = None, right = None):
        self.top = top
        self.left = left
        self.bottom = bottom
        self.right = right

        if self.top and self.bottom:
            assert self.bottom > self.top
        
        if self.left and self.right:
            assert self.right > self.left

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    def __eq__(self, other):
        return self.top == other.top and self.left == other.left and self.bottom == other.bottom and self.right == other.right

def value_assert(stream, target, type="value", warn=False):
    ax = stream
    try:
        ax = stream.read(len(target))
    except AttributeError:
        pass

    msg = "Expected {} {}{}, received {}{}".format(
        type, target, " (0x{:0>4x})".format(target) if isinstance(target, int) else "",
        ax, " (0x{:0>4x})".format(ax) if isinstance(ax, int) else "",
    )
    if warn and ax != target:
        logging.warning(msg)
    else:
        assert ax == target, msg

def process_tonka_dat_file(filename):
    # PARSE THE DAT FILE.
    print("Processing file: {}".format(filename))
    with open(filename, mode='rb') as f:
        # MAP THE FILE TO A STREAM WITH READ-ONLY ACCESS.
        stream = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)

        # PARSE THE FILE INTO A MODULE.
        module = Module(stream)

        # EXPORT THE FILE'S CONTENTS.
        if args.export:
            Path(args.export).mkdir(parents=True, exist_ok=True)
            module.export()

class Module:
    def __init__(self, stream):
        # REGISTER THE CHUNKS IN THIS FILE.
        # Each Module typically contains the assets for a single screen of the game,
        # and each of these assets is stored in a chunk. These chunks are referenced
        # by their byte position in this file.
        chunk_pointers = []
        chunk_count = struct.unpack("<H", stream.read(2))[0]
        logging.debug("process_tonka_dat_file: Expecting {} chunk_count".format(chunk_count))
        for i in range(chunk_count):
            chunk_pointer = struct.unpack("<L", stream.read(4))[0]
            chunk_pointers.append(chunk_pointer)
            logging.debug("process_tonka_dat_file: Registered chunk {}\{} @ 0x{:012x}".format(i+1, chunk_count, chunk_pointer))
        # The pointer to the final chunk is the total length of this file.
        chunk_pointers.append(len(stream))
        value_assert(struct.unpack("<H", stream.read(2))[0], chunk_count)

        # TODO: I don't know what is here.
        unk1 = struct.unpack("<L", stream.read(4))[0]
        if unk1 != 0:
            logging.warning("process_tonka_dat_file: Unk1: {}".format(unk1))

        # READ THE BACKGROUND IMAGE FOR THIS MODULE.
        # The background is always the first chunk of the module.
        end_of_background_pointer = chunk_pointers[0]
        background_size = end_of_background_pointer - stream.tell()
        logging.debug("*** CHUNK {} (0x{:012x} -> 0x{:012x} [0x{:04x} bytes]) *** ".format("BACKGROUND", stream.tell(), end_of_background_pointer, background_size))
        self.background = Background(stream)
        # This is to ensure we are at the end of the background.
        value_assert(stream.tell(), chunk_pointers[0], "stream position")

        # READ EACH OF THE ASSETS IN THIS MODULE.
        self.assets = []
        for i in range(len(chunk_pointers) - 1):
            # RECORD THE LENGTH OF THIS ASSET.
            start_of_asset_pointer = chunk_pointers[i]
            end_of_asset_pointer = chunk_pointers[i+1]
            asset_length = end_of_asset_pointer - start_of_asset_pointer
            logging.debug("*** CHUNK {} (0x{:012x} -> 0x{:012x} [0x{:04x} bytes]) *** ".format(i, start_of_asset_pointer, end_of_asset_pointer, asset_length))

            # READ THE ASSET.
            # Ensure the stream is at the start of the asset.
            value_assert(stream.tell(), start_of_asset_pointer, "stream position")
            # Read the asset.
            asset = Asset(stream, asset_length)
            self.assets.append(asset)

    def export(self):
        # EXPORT THE BACKGROUND.
        background_filename = os.path.join(args.export, "background.png")
        self.background.image.save(background_filename, 'png')

        # EXPORT THE ASSETS.
        for animation_index, animation in enumerate(self.assets):
            logging.debug(f"  Animation dimensions: {animation.width} x {animation.height}")

            # CREATE THE EXPORT DIRECTORY.
            animation_directory_name = os.path.join(args.export, f"ANIM-{animation_index}-{animation.animation_contents.name}.{animation.type.name}")
            Path(animation_directory_name).mkdir(parents=True, exist_ok=True)
            logging.debug(f"Saving to: {animation_directory_name}")

            # EXPORT THE VIDEO/AUDIO IN EACH FRAME.
            # Since the whole game has a constant framerate and each asset has audio of a constant bitrate, 
            # all the audio for each asset can be joined to a single stream.
            full_animation_audio_data = b''
            for frame_index, frame in enumerate(animation.frames):
                # EXPORT THE IMAGE IN THIS FRAME.
                if frame.valid:
                    # GET THE RAW ANIMATION IMAGE FOR THIS FRAME.
                    # Since only frames that actually exist were added to the framesets, 
                    # we can loop through all the frames in the frameset without further
                    # validity checking.
                    logging.debug(f"  Frame dimensions: {frame.width} x {frame.height}")
                    image = frame.image
                    # The palette is the same palette as occurs in the background image for this module.
                    image.putpalette(self.background.palette.rgb_colors)

                    # DETERMINE WHETHER IMAGE RE-FRAMING IS REQUIRED.
                    true_animation_bounding_box = animation.true_bounding_box
                    nominal_dimensions_true = true_animation_bounding_box == animation.bounding_box
                    reframe_image: bool = args.apply_true_animation_dimensions  and not animation.is_discrete and not nominal_dimensions_true

                    # FRAME THE IMAGE ON THE APPROPRIATE CANVAS.
                    # When image re-framing has been requested, the animation has continuous (non-discrete) frames, 
                    # and the true dimensions are not the nominal dimensions, the image must be re-framed - that is,
                    # a new canvas is created with the true size of the animation, and the image is placed in the appropriate
                    # place within that new canvas. Thus, all the images for this animation will have the same dimensions.
                    if reframe_image:
                        # CREATE THE FULL-SIZED FRAME TO HOLD THE ANIMATION IMAGE.
                        # The full frame must be filled with the alpha color.
                        ALPHA_COLOR = 0x0f # Corresponds to 0x0dff0b in the palette.
                        full_frame_dimensions = (true_animation_bounding_box.width, true_animation_bounding_box.height)
                        full_frame = Image.new('P', full_frame_dimensions, color=ALPHA_COLOR)
                        # The palette is the same palette as occurs in the background image for this module.
                        full_frame.putpalette(self.background.palette.rgb_colors)

                        # PASTE THE ANIMATION IMAGE IN THE APPROPRIATE PLACE.
                        image_location = (frame.left - true_animation_bounding_box.left, frame.top - true_animation_bounding_box.top)
                        full_frame.paste(image, box=image_location)

                        # SAVE THE PROPERLY SIZED AND POSITIONED ANIMATION FRAME.
                        frame_filename = os.path.join(animation_directory_name, f"{frame_index}.png")
                        full_frame.save(frame_filename, 'png')
                    else:
                        # If no adjustment is required, the image can be written as it is.
                        frame_filename = os.path.join(animation_directory_name, f"{frame_index}.png")
                        image.save(frame_filename, 'png')

                # ADD THE AUDIO DATA FROM THIS FRAME.
                full_animation_audio_data += frame.audio_data

            # EXPORT THE AUDIO FOR THIS ASSET.
            animation_has_audio = len(full_animation_audio_data) > 0
            if animation_has_audio:
                AUDIO_TYPE = 'u16le'
                BITRATE = '11.025k'
                CHANNEL_COUNT = '1'
                audio_filename = os.path.join(animation_directory_name, f"audio.wav")
                audio_conversion_command = ['ffmpeg', '-y', '-f', AUDIO_TYPE, '-ar', BITRATE, '-ac', CHANNEL_COUNT, '-i', 'pipe:', audio_filename]
                with subprocess.Popen(audio_conversion_command, stdin=subprocess.PIPE, stdout=subprocess.STDOUT if args.debug else subprocess.DEVNULL) as ffmpeg:
                    ffmpeg.stdin.write(full_animation_audio_data)
                    ffmpeg.communicate()

class Background:
    def __init__(self, stream):
        start = stream.tell()
        unk1 = struct.unpack("<H", stream.read(2))[0]
        unk2 = struct.unpack("<H", stream.read(2))[0]
        unk3 = struct.unpack("<H", stream.read(2))[0]
        unk4 = struct.unpack("<H", stream.read(2))[0]
        unk5 = struct.unpack("<H", stream.read(2))[0]

        self.filename = stream.read(0x50).rstrip(b'\x00')

        unk6 = struct.unpack("<L", stream.read(4))[0]
        unk7 = struct.unpack("<L", stream.read(4))[0]
        unk8 = struct.unpack("<L", stream.read(4))[0]
        unk8_1 = struct.unpack("<L", stream.read(4))[0]
        stream.read(0x24)
        unk9 = struct.unpack("<L", stream.read(4))[0]
        unk10 = struct.unpack("<L", stream.read(4))[0]
        stream.read(0x14)

        self.palette = Palette(stream)
        self.width = struct.unpack("<L", stream.read(4))[0]
        self.height = struct.unpack("<L", stream.read(4))[0]
        self.compressed_image_data_size = struct.unpack("<L", stream.read(4))[0]

        # TODO: Unknown data
        stream.read(0x0c)

        # The image data is always uncompressed.
        self.uncompressed_image_bytes = stream.read(self.compressed_image_data_size)

    @property
    def image(self):
        assert len(self.uncompressed_image_bytes) == self.compressed_image_data_size
        background = Image.frombytes('P', (self.width, self.height), self.uncompressed_image_bytes)
        background.putpalette(self.palette.rgb_colors)
        return background

class Asset:
    def __init__(self, stream, size):
        logging.debug(" *** ASSET *** ")

        # GET THE TYPE OF THE ASSET.
        # The asset type is determined by the first six bytes of the asset.
        # First, the type codes must be read.
        TYPE_CODE_COUNT = 3
        type_codes = []
        for _ in range(TYPE_CODE_COUNT):
            type_codes.append(struct.unpack("<H", stream.read(2))[0])
        # Then, the type codes are assigned to a human-readable type,
        # so the types are easier to manage.
        if type_codes == [0x00, 0x00, 0x00]:
            self.type = AssetTypes.AUDIO_ONLY
        elif type_codes == [0x00, 0x01, 0x01]:
            self.type = AssetTypes.EARTH_COMPONENT
        elif type_codes == [0x01, 0x01, 0x01]:
            self.type = AssetTypes.TIMED_ANIMATION
        elif type_codes == [0x02, 0x01, 0x01]:
            self.type = AssetTypes.CLICKABLE_STILL
        elif type_codes == [0x03, 0x01, 0x01]:
            self.type = AssetTypes.SCRIPTED_ANIMATION
        elif type_codes[0:2] == [0x01, 0x0c]:
            # The cursor type also stores cursor information in the type code.
            self.type = AssetTypes.CURSOR
            self.cursor_directions = type_codes[-2]
            self.cursor_facets = type_codes[-1]
        else:
            # HALT ON AN UNKNOWN TYPE CODE.
            raise ValueError(f"Unknown asset type codes: {type_codes}")
        logging.debug(f" Asset Type: {self.type.name}")

        # CALCULATE THE NUMBER OF FRAMES IN THIS ANIMATION.
        frame_count = struct.unpack("<H", stream.read(2))[0]
        if self.type == AssetTypes.CURSOR:
            # For cursors, the frame count only indicates the number of .
            frame_count *= self.cursor_directions * self.cursor_facets
        logging.debug(f" Expecting {frame_count} frames")

        # SET THE EXPECTED CONTENTS OF THIS FRAME.
        # A frame can contain video only, video and audio, or have unknown contents.
        self.animation_contents = FrameContents(struct.unpack("<H", stream.read(2))[0])
        logging.debug(f" Frame contents: {self.animation_contents.name}")

        # READ THE DIMENSIONS OF THE ANIMATION.
        # Note that these values might not be the true dimensions of the animation,
        # as would be calculated from the actual dimensions of the frames in the animation.
        self.width = struct.unpack("<H", stream.read(2))[0]
        self.height = struct.unpack("<H", stream.read(2))[0]
        logging.debug(f" Animation dimensions: {self.width} x {self.height}")

        # TODO: I don't know what's in here.
        hexdump(stream.read(0x56))

        # READ THE COORDINATES OF THE ANIMATION.
        self.left = struct.unpack("<H", stream.read(2))[0]
        self.top = struct.unpack("<H", stream.read(2))[0]
        logging.debug(f" Animation position: ({self.left}, {self.top})")

        # TODO: I don't know what's in here.
        hexdump(stream.read(0x04))

        # READ THE RESOLUTION OF THE ANIMATION. 
        # TODO: I don't think this is actually animation.
        self.horizontal_resolution = struct.unpack("<H", stream.read(2))[0]
        self.vertical_resolution = struct.unpack("<H", stream.read(2))[0]
        logging.debug(f" Resolution: {self.horizontal_resolution} x {self.vertical_resolution}")

        # TODO: I don't know what's in here.
        hexdump(stream.read(0x0c))

        # READ THE ANIMATION FRAME START POINTERS.
        if self.animation_contents == FrameContents.VIDEO_ONLY:
            # TODO: I don't know what's in here.
            hexdump(stream.read(4))

            # READ THE FRAME START POINTERS.
            # These pointers are relative to the entire DAT file, not just this asset. 
            # Each points to the beginning of the header of a video frame in this animation.
            # For some reason, a pointer table is not provided for frames that also have audio.
            # These pointers are just ignored.
            frame_start_pointers = []
            for _ in range(frame_count):
                frame_start_pointers.append(stream.read(4))

        # READ THE ANIMATION FRAMES.
        self.frames = []
        for frame_id in range(frame_count):
            logging.debug(f" ### Frame {frame_id+1} of {frame_count} ###")
            # For some reason, there is junk data before the first frame of non-video-only animations.
            # This data is just ignored.
            first_frame_of_non_video_only_animation = self.animation_contents != FrameContents.VIDEO_ONLY and frame_id == 0
            if first_frame_of_non_video_only_animation:
                # TODO: I don't know what's in here.
                hexdump(stream.read(4))

            # PARSE THE FRAME.
            # For animations with audio, the audio is interleaved such that audio occurs in chunk_count 
            # that last the duration of the video frames until the next occurrence of an audio chunk (or the end of the frame).
            # Note that this frequency effectively gives the framerate of the video, since each 
            # audio chunk contains exactly one second of audio (or the remaining audio in the frame if this is the last frame).
            # Video-only animations and frames between audio chunk_count have a single frame per iteration.
            ANIMATION_FRAMES_PER_AUDIO_CHUNK = 8
            audio_expected = (self.animation_contents != FrameContents.VIDEO_ONLY) and (frame_id % ANIMATION_FRAMES_PER_AUDIO_CHUNK == 0)
            frame = AnimationFrame(stream, frame_id, read_audio=audio_expected)
            if audio_expected:
                logging.debug("Audio expected")
            # Invalid frames should not be added to the frameset.
            # This avoids problems later with validating frame values before they are used.
            if frame.valid:
                self.frames.append(frame)
            elif frame.validity == FrameValidationStatus.AUDIO_ONLY:
                self.frames.append(frame)
            elif frame.validity == FrameValidationStatus.EMPTY_FRAME:
                # Empty frames are not considered an error condition, so we will not warn about them.
                pass
            else:
                logging.warning(f"Read invalid frame ({frame_id}): {frame.validity.name} (@0x{stream.tell():012x})")

    @property
    def is_discrete(self):
        # These asset types have frames not intended to be played continuously, as an animation.
        # Instead, these asset types are "libraries" with the appropriate frames chosen under program control.
        return self.type == AssetTypes.CURSOR or self.type == AssetTypes.EARTH_COMPONENT

    @property
    def right(self):
        return self.left + self.width

    @property
    def bottom(self):
        return self.top + self.height

    @property
    def bounding_box(self):
        # Note that this bounding box might not be the true bounding box the animation, 
        # as would be calculated from the actual dimensions of the frames in the animation.
        return BoundingBox(self.top, self.left, self.bottom, self.right)

    @property
    def true_bounding_box(self):
        # MAKE SURE FRAMES ARE PRESENT.
        # If there are not frames present, the calls further on will error out
        # because the will be fed empty lists.
        no_frames_present = len(self.frames) == 0
        if no_frames_present:
            return

        # GET ALL THE BOUNDING BOXES IN THE ANIMATION.
        frame_bounding_boxes = [frame.bounding_box for frame in self.frames]

        # FIND THE SMALLEST RECTANGLE THAT CONTAINS ALL THE FRAME BOUNDING BOXES.
        # This smallest rectangle will have the following vertices:
        # Left: The left vertex of the leftmost bounding box.
        # Top: The top vertex of the topmost bounding box.
        # Right: The right vertex of the rightmost bounding box.
        # Bottom: The bottom vertext of the bottommost bounding box.
        true_left = min([bounding_box.left for bounding_box in frame_bounding_boxes])
        true_top = min([bounding_box.top for bounding_box in frame_bounding_boxes])
        true_right = max([bounding_box.right for bounding_box in frame_bounding_boxes])
        true_bottom = max([bounding_box.bottom for bounding_box in frame_bounding_boxes])
        return BoundingBox(true_top, true_left, true_bottom, true_right)

class AnimationFrame:
    def __init__(self, stream, frame_index, read_audio = False):
        # MARK THE FRAME VALID.
        # The frame will be marked invalid if there are any problems parsing it.
        # If the frame is not marked valid, it will appear to have no dimensions.
        self.validity = FrameValidationStatus.VALID
        self.audio_data = b''

        # READ THE FRAME'S DIMENSIONS.
        self.width = struct.unpack("<L", stream.read(4))[0]
        self.height = struct.unpack("<L", stream.read(4))[0]
        if self.width == 0 and self.height == 0:
            # An empty frame is not invalid, per se, but we want to mark it so.
            self.validity = FrameValidationStatus.EMPTY_FRAME
        # On audio_only chunk_count, sometimes there is one more frame than
        # necessary. Not sure why. But here we just discard those frames.
        frame_has_height_but_zero_width = self.width == 0 and self.height != 0
        frame_has_width_but_zero_height = self.width != 0 and self.height == 0
        frame_has_dimensions_too_large = self.width > 0xffff or self.height > 0xffff
        skip_frame = frame_has_height_but_zero_width or frame_has_width_but_zero_height or frame_has_dimensions_too_large
        if skip_frame:
            # UN-READ ALL BYTES READ FOR THIS FRAME.
            # This data was not supposed to be consumed in the first place, as
            # it actually belongs to the next chunk of data. It is not a real frame.
            # Thus, the stream should be rewound as if this data was never read
            # as part of a frame.
            stream.seek(stream.tell() - 8)

            # END PARSING THIS FRAME.
            self.validity = FrameValidationStatus.EXTRA_FRAME
            return
        logging.debug(f"  Frame dimensions: {self.width} x {self.height}")

        # READ THE IMAGE SIZES, IN BYTES.
        self.uncompressed_image_size = struct.unpack("<L", stream.read(4))[0]
        self.compressed_image_data_size = struct.unpack("<L", stream.read(4))[0]
        logging.debug(f"  Uncompressed frame size: {self.uncompressed_image_size}")
        logging.debug(f"  Compressed image data size: {self.compressed_image_data_size}")

        # READ THE AUDIO FOR THIS FRAME.
        # The presence of audio affects the position of other non-audio-related elements,
        # so these are also read in a different order depending on whether audio is expected.
        if read_audio:
            # READ THE AUDIO BITRATE.
            # Each audio chunk stores exactly one second of audio at the given sampling frequency.
            self.bitrate = struct.unpack("<L", stream.read(4))[0]
            logging.debug(f"  Bitrate: {self.bitrate} {hex(stream.tell())}")

            # READ THE FRAME STARTING COORDINATES.
            self.left = struct.unpack("<h", stream.read(2))[0]
            self.top = struct.unpack("<h", stream.read(2))[0]
            logging.debug(f"  Position: ({self.left}, {self.top})")

            # ACTUALLY READ THE AUDIO.
            # Even when audio is expected, the self.bitrate could still be zero to indicate no audio is actually present.
            zero_bitrate = self.bitrate == 0
            if not zero_bitrate:
                # STORE THE RAW AUDIO DATA.
                # Normally, each audio chunk stores exactly one second of audio at the given sampling frequency (bitrate).
                # Thus the number of bytes to read is the same as the sampling frequency in Hertz.
                # But for some reason, when the sampling frequency is 22.050kHz (0x5622) and this audio chunk is the first one read,
                # the amount of audio present is actually double the sampling frequency. So this adjustment made.
                first_frame = frame_index == 0
                double_bitrate = first_frame and self.bitrate == 0x5622
                if double_bitrate:
                    self.bitrate *= 2
                logging.debug(f"  Reading {self.bitrate} bytes of audio")
                self.audio_data = stream.read(self.bitrate)
        else:
            # TODO: I don't know what these are.
            a = struct.unpack("<h", stream.read(2))[0]
            b = struct.unpack("<h", stream.read(2))[0]

            # READ THE FRAME STARTING COORDINATES.
            # If either the width or the height exceeds this sanity-checking value, 
            # the frame will be marked invalid. No known frames in the game have either
            # coordinate exceeding this threshold.
            # I don't know all the reasons why a frame would have crazy coordinates,
            # but it has been observed to occur in cursors particularly.
            COORDINATE_SANITY_THRESHOLD = 1440
            self.left = struct.unpack("<h", stream.read(2))[0]
            if abs(self.left) > COORDINATE_SANITY_THRESHOLD:
                # MARK THE FRAME INVALID.
                self.validity = FrameValidationStatus.COORDINATE_OUT_OF_BOUNDS
            self.top = struct.unpack("<h", stream.read(2))[0]
            if abs(self.top) > COORDINATE_SANITY_THRESHOLD:
                # MARK THE FRAME INVALID.
                self.validity = FrameValidationStatus.COORDINATE_OUT_OF_BOUNDS
            logging.debug(f"  Position: ({self.left}, {self.top})")

        # UNCOMPRESS THE COMPRESSED IMAGE STREAM.
        # The compression algorithm is Apple's PackBits.
        # First, we must have a empty place to put the uncompressed bytes.
        self.uncompressed_image_bytes = b''
        compressed_image_data_start = stream.tell()
        # Read the full number of compressed bytes.
        while stream.tell() - compressed_image_data_start < self.compressed_image_data_size:
            n = int.from_bytes(stream.read(1), byteorder="little", signed=True)
            # Read the operation byte. 
            # An operation byte inclusively between 0x00 (+0) and 0x7f (+127) indicates
            # an uncompressed run of the value of the operation byte plus one.
            if n >= 0 and n <= 127:
                run_length = n+1
                self.uncompressed_image_bytes += stream.read(run_length)
            # An operation byte inclusively between 0x81 (-127) and 0xff (-1) indicates
            # the next byte is a color that should be repeated for a run of (-n+1) pixels.
            elif n >= -127 and n <= -1:
                color_byte = stream.read(1)
                run_length = -n+1
                color_run = color_byte * run_length
                self.uncompressed_image_bytes += color_run

    @property
    def valid(self):
        return self.validity == FrameValidationStatus.VALID

    @property
    def image(self):
        # RETURN THE IMAGE ONLY IF THE FRAME IS VALID.
        if self.valid:
            frame = Image.frombytes('P', (self.width, self.height), self.uncompressed_image_bytes)
            return frame
        else:
            # If the frame is invalid, the required fields might not even be populated
            # or might be populated with garbage that would cause a crash.
            return None

    @property
    def right(self):
        return self.left + self.width

    @property
    def bottom(self):
        return self.top + self.height

    @property
    def bounding_box(self):
        # RETURN THE BOUNDING BOX ONLY IF THE FRAME IS VALID.
        if self.valid:
            return BoundingBox(self.top, self.left, self.bottom, self.right)
        else:
            # If the frame is invalid, the required fields might not even be populated
            # or might be populated with garbage that would cause a crash.
            return None

class Palette:
    def __init__(self, stream):
        # For background images, the palette starts at 0xAA.
        self.rgb_colors = b''
        TOTAL_PALETTE_ENTRIES = 0x100
        for palette_index in range(TOTAL_PALETTE_ENTRIES):
            blue_green_red_color_bytes = bytearray(stream.read(3))
            blue_green_red_color_bytes.reverse()
            self.rgb_colors += blue_green_red_color_bytes

            # The colors are padded to align with the dword boundary (32 bits).
            # Thus, since there are only three colors of 8 bits each,
            # the last 8 bits should always be zero.
            value = stream.read(1)

        assert len(self.rgb_colors) == TOTAL_PALETTE_ENTRIES * 3

def main():
    process_tonka_dat_file(args.input)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="tonka", formatter_class=argparse.RawTextHelpFormatter,
        description="""Parse asset structures and extract assets from Tonka Construction (1996) module data."""
    )

    parser.add_argument(
        "input", help="Pass a DAT filename to process_tonka_dat_file the file."
    )

    parser.add_argument(
        "export", nargs='?', default=None,
        help="Specify the location for exporting assets, or omit to skip export."
    )

    parser.add_argument(
        "--apply-true-animation-dimensions", '-a', action="store_true", default=False,
        help="""When present, place each animation frame in its proper place on a canvas the size of the entire animation. 
Otherwise, when omitted, export each frame of the animation on a canvas that exactly fits only that frame.""")

    parser.add_argument(
        "--debug", "-d", action="store_true", default=False,
        help="When present, print verbose debugging information to stdout as parsing proceeds."
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    main()
