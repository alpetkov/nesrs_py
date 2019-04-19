
def read_ines_rom(rom_file):
    headers = rom_file.read(16)
    # Read trainer
    if headers[6] & 0x04 != 0:
        rom_file.read(512)
    # Read PRG ROM
    prg_rom = []
    if headers[4] > 0:
        for x in range(headers[4] * 16):
            prg_rom.append(rom_file.read(1024))
    # Read CHR ROM
    chr_rom = []
    if headers[5] > 0:
        for x in range(headers[5] * 8):
            chr_rom.append(rom_file.read(1024))

    prg_ram = [0 for x in range((headers[8] if headers[8] > 0 else 1) * 8 * 1024)]

    chr_mem = chr_rom
    is_chr_mem_ram = False
    if len(chr_rom) == 0:
        chr_mem = [[0 for y in range(1024)] for x in range(8)]
        is_chr_mem_ram = True

    return Cartridge(prg_rom, prg_ram, chr_mem, is_chr_mem_ram)


class Cartridge(object):

    def __init__(self, prg_rom, prg_ram, chr_mem, is_chr_mem_ram):
        self._prg_rom = prg_rom
        self._prg_ram = prg_ram
        self._chr_mem = chr_mem
        self._is_chr_mem_ram = is_chr_mem_ram

        self._prg_rom_map = [i & (len(self._prg_rom) - 1) for i in range(32)]

    def read_prg_memory(self, cpu_address):
        if 0x4020 <= cpu_address <= 0x5FFF:
            # Expansion ROM
            return 0
        elif 0x6000 <= cpu_address <= 0x7FFF:
            # RAM
            return self._prg_ram[cpu_address & 0x1FFF];
        elif 0x8000 <= cpu_address:
            # ROM
            return self._prg_rom[self._prg_rom_map[(cpu_address & 0x7FFF) >> 10]][(cpu_address & 0x03FF)]

        return 0

    def write_prg_memory(self, cpu_address, value):
        if 0x6000 <= cpu_address <= 0x7FFF:
            # RAM
            self._prg_ram[cpu_address & 0x1FFF] = value