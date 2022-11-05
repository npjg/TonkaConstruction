from assets.Asset.Image import RectangularBitmap
from assets.Asset.Palette import RgbPalette

class Background(RectangularBitmap):
    def __init__(self, file):
        super().__init__()

        self.name = "Background"

        # TODO: Unknown data.
        self.unk1 = file.uint16_le()
        self.unk2 = file.uint16_le()
        self.unk3 = file.uint16_le()
        self.unk4 = file.uint16_le()
        self.unk5 = file.uint16_le()

        self.filename = file.read(0x50).rstrip(b'\x00')

        # TODO: Unknown data.
        self.unk6 = file.uint32_le()
        self.unk7 = file.uint32_le()
        self.unk8 = file.uint32_le()
        self.unk8_1 = file.uint32_le()
        self.unk12 = file.read(0x24)
        self.unk9 = file.uint32_le()
        self.unk10 = file.uint32_le()
        self.unk13 = file.read(0x14)

        self.palette = RgbPalette(file, expected_total_entries = 0x100, blue_green_red_order = True)
        self._width = file.uint32_le()
        self._height = file.uint32_le()
        pixel_count = file.uint32_le()

        # TODO: Unknown data.
        self.unk14 = file.read(0x0c)

        # The image data is always uncompressed.
        self.pixels = file.read(pixel_count)