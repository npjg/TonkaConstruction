#!/usr/bin/python3

import argparse
import logging
import struct
import os
from pathlib import Path
import glob
import mmap
import io
import subprocess
import uuid
import json

from mrcrowbar.utils import hexdump
from PIL import Image

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

def process(filename):
    logging.debug("Processing file: {}".format(filename))
    if args.export:
        Path(args.export).mkdir(parents=True, exist_ok=True)

    with open(filename, mode='rb') as f:
        stream = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
        module = Module(stream)
        module.export()

class Module:
    def __init__(self, stream):
        locs = []
        chunks = struct.unpack("<H", stream.read(2))[0]
        logging.debug("process: Expecting {} chunks".format(chunks))
        for i in range(chunks):
            loc = struct.unpack("<L", stream.read(4))[0]
            locs.append(loc)
            logging.debug("process: Registered chunk {}\{} @ 0x{:012x}".format(i+1, chunks, loc))

        locs.append(len(stream))

        value_assert(struct.unpack("<H", stream.read(2))[0], chunks)
        # logging.debug(stream.tell())
        unk1 = struct.unpack("<L", stream.read(4))[0]
        if unk1 != 0:
            logging.warning("process: Unk1: {}".format(unk1))

        logging.debug("*** CHUNK {} (0x{:012x} -> 0x{:012x} [0x{:04x} bytes]) *** ".format("BACKGROUND", stream.tell(), locs[0], locs[0]-stream.tell()))
        self.background = Background(stream)
        # if args.export:
        #     image = background.image
        #     background.image.save(os.path.join(args.export, "background.png"), 'png')

        self.animations = []
        for i in range(len(locs) - 1):
            logging.debug("*** CHUNK {} (0x{:012x} -> 0x{:012x} [0x{:04x} bytes]) *** ".format(i, locs[i], locs[i+1], locs[i+1]-locs[i]))
            assert stream.tell() == locs[i]

            unk1 = struct.unpack("<H", stream.read(2))[0]
            unk2 = struct.unpack("<H", stream.read(2))[0]
            unk3 = struct.unpack("<H", stream.read(2))[0]
            if unk1 == 0 and unk2 == 1 and unk3 == 1:
                self.animations.append(Animation(stream))
            else:
                logging.debug(" *** UNKNOWN ***")
                data = stream.read(locs[i+1] - locs[i] - 6)
            # if args.export:
            #     with open(os.path.join(args.export, "{}.dat".format(i)), 'wb') as out:
            #         out.write(data)
            # else:
            #     hexdump(data, end=0x100)

    def export(self):
        if not args.export:
            return

        # First, export the background.
        self.background.image.save(os.path.join(args.export, "background.png"), 'png')

        # Then, export animations.
        for animation_index, animation in enumerate(self.animations):
            animation_directory_name = os.path.join(args.export, f"ANIM-{animation_index}")
            Path(animation_directory_name).mkdir(parents=True, exist_ok=True)

            combined_audio = b''
            for frame_index, frame in enumerate(animation.frames):
                image = frame.image
                image.putpalette(self.background.palette.rgb_colors)
                image.save(os.path.join(animation_directory_name, f"{frame_index}.png"), 'png')
                # combined_audio += self.audio

           
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
        self.image_data_size = struct.unpack("<L", stream.read(4))[0]
        stream.read(0x0c)
        # value_assert(stream.read(0x0c), b'\x90\x94\x90\x90\x94\x90\x90\x94\x90\x90')
        self.image_data = stream.read(self.image_data_size)

    @property
    def image(self):
        # Is there ever any compresison in the background images?
        assert len(self.image_data) == self.image_data_size
        background = Image.frombytes('P', (self.width, self.height), self.image_data)
        background.putpalette(self.palette.rgb_colors)
        return background

class Animation:
    def __init__(self, stream):
        logging.debug(" *** ANIMATION *** ")
        # Starting at offset 0x06.
        frame_count = struct.unpack("<H", stream.read(2))[0]
        logging.debug(f" Expecting {frame_count} frames")

        animation_type = struct.unpack("<H", stream.read(2))[0]
        logging.debug(f" Animation type: {animation_type}")

        self.width = struct.unpack("<H", stream.read(2))[0]
        self.height = struct.unpack("<H", stream.read(2))[0]
        logging.debug(f" Animation dimensions: {self.width} x {self.height}")

        # I don't know what's in here.
        data = stream.read(0x56)
        # hexdump(data)
        # print(data)
        if data == b'\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
            print("Match")
            input()
        # stream.read(2)
        # unk1 = struct.unpack("<Q", stream.read(8))[0]
        # unk2 = struct.unpack("<Q", stream.read(8))[0]
        # stream.read(0x14)
        # unk3 = struct.unpack("<Q", stream.read(8))[0]
        # stream.read(0x24)
        # unk4 = struct.unpack("<L", stream.read(4))[0]
        # logging.debug(f'{unk1} {unk2} {unk3} {unk4}')

        self.left = struct.unpack("<H", stream.read(2))[0]
        self.top = struct.unpack("<H", stream.read(2))[0]
        logging.debug(f" Animation position: ({self.left}, {self.top})")

        stream.read(0x04)

        self.horizontal_resolution = struct.unpack("<H", stream.read(2))[0]
        self.vertical_resolution = struct.unpack("<H", stream.read(2))[0]

        self.frames = []
        stream.read(0x0c)

        if animation_type == 0x00:
            stream.read(4)
        for frame_id in range(frame_count):
            logging.debug(f" ### Frame {frame_id} ###")
            if animation_type == 0x00 or (animation_type == 0x08 and frame_id == 0):
                stream.read(4)

            if animation_type == 0x00:
                self.frames.append(AnimationFrame(stream))
            else:
                ANIMATION_FRAMES_PER_AUDIO_CHUNK = 7
                chunk_should_have_audio = frame_id % (ANIMATION_FRAMES_PER_AUDIO_CHUNK + 1) == 0
                if chunk_should_have_audio:
                    logging.warning("HAS AUDIO")
                self.frames.append(AnimationFrame(stream, chunk_should_have_audio, frame_id == 0))

class AnimationFrame:
    def __init__(self, stream, read_audio = False, first_audio = False):
        self.width = struct.unpack("<L", stream.read(4))[0]
        while self.width > 0xffff:
            logging.warning("Skipping junk data")
            self.width = struct.unpack("<L", stream.read(4))[0]

        self.height = struct.unpack("<L", stream.read(4))[0]
        logging.debug(f"  Frame dimensions: {self.width} x {self.height}")

        self.uncompressed_image_size = struct.unpack("<L", stream.read(4))[0]
        self.image_data_size = struct.unpack("<L", stream.read(4))[0]
        logging.debug(f"  Uncompressed frame size: {self.uncompressed_image_size}")
        logging.debug(f"  Compressed image data size: {self.image_data_size}")

        self.audio_data = b''
        if read_audio:
            bitrate = struct.unpack("<L", stream.read(4))[0]
            hexdump(stream.read(4))
            # value_assert(struct.unpack("<L", stream.read(4))[0], 0)
            if first_audio:
                self.audio_data = stream.read(bitrate * 2)
            else:
                self.audio_data = stream.read(bitrate)
        else:
            stream.read(0x08)
            
        self.image_data = b''
        stream_start = stream.tell()
        while stream.tell() - stream_start < self.image_data_size:
            n = int.from_bytes(stream.read(1), byteorder="little", signed=True)
            if n >= 0 and n <= 127:
                self.image_data += stream.read(n+1)
            elif n >= -127 and n <= -1:
                color = stream.read(1)
                self.image_data += color * (-n+1)

    @property
    def image(self):
        frame = Image.frombytes('P', (self.width, self.height), self.image_data)
        return frame

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

        assert len(self.rgb_colors) == 0x300
            # if value != b'\x00':
            #     print(hex(stream.tell()))
            #     print(value)
            #     assert value == b'\x00'

def main():
    process(args.input)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="tonka", formatter_class=argparse.RawTextHelpFormatter,
         description="""Parse asset structures and extract assets from Tonka Construction (1996) module data."""
    )

    parser.add_argument(
        "input", help="Pass a DAT filename to process the file."
    )

    parser.add_argument(
        "export", nargs='?', default=None,
        help="Specify the location for exporting assets, or omit to skip export."
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    main()
