
import self_documenting_struct as struct
from asset_extraction_framework.Asset.Image import RectangularBitmap
from asset_extraction_framework.Asset.Palette import RgbPalette

## Provides a background for each module.
class Background(RectangularBitmap):
    def __init__(self, file):
        super().__init__()
        self.name = "Background"
        self.unk1 = struct.unpack.uint16_le(file.stream)
        self.unk2 = struct.unpack.uint16_le(file.stream)
        self.unk3 = struct.unpack.uint16_le(file.stream)
        self.unk4 = struct.unpack.uint16_le(file.stream)
        self.unk5 = struct.unpack.uint16_le(file.stream)
        self.filename = file.stream.read(0x50).rstrip(b'\x00')
        self.unk6 = struct.unpack.uint32_le(file.stream)
        self.unk7 = struct.unpack.uint32_le(file.stream)
        self.unk8 = struct.unpack.uint32_le(file.stream)
        self.unk8_1 = struct.unpack.uint32_le(file.stream)
        self.unk12 = file.stream.read(0x24)
        self.unk9 = struct.unpack.uint32_le(file.stream)
        self.unk10 = struct.unpack.uint32_le(file.stream)
        self.unk13 = file.stream.read(0x14)
        self._palette = RgbPalette(file.stream, has_entry_alignment = True, total_palette_entries = 0x100, blue_green_red_order = True)
        self._width = struct.unpack.uint32_le(file.stream)
        self._height = struct.unpack.uint32_le(file.stream)
        pixel_count = struct.unpack.uint32_le(file.stream)
        self.unk14 = file.stream.read(0x0c)

        # The image data is always uncompressed.
        self._pixels = file.stream.read(pixel_count)