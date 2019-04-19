from .context import nesrs
import nesrs.cartridge
import nesrs.cpu
import os
import unittest


def pad(value):
    if value < 10:
        return '  ' + str(value)
    elif value < 100:
        return ' ' + str(value)
    else:
        return '' + str(value)


def to_hex(i):
    hex = format(i, 'x').upper()
    if len(hex) % 2 != 0:
        hex = '0' + hex;

    return hex;


def get_nestest_log_lines(nestest_file):
    content = []
    for line in nestest_file:
        line = line.strip()

        new_line = line[0: 4]
        new_line += '    '
        new_line += line[line.index('A:') : line.index(' SL')]

        content.append(new_line)

    return content


class Nestest(unittest.TestCase):

    def test_log(self):
        nestest_log_lines = []
        with open(os.path.join(os.path.dirname(__file__), 'nestest.log'), 'r') as nestest_file:
            nestest_log_lines = get_nestest_log_lines(nestest_file)

        cartridge = None
        with open(os.path.join(os.path.dirname(__file__), 'nestest.nes'), 'rb') as nestest_rom_file:
            cartridge = nesrs.cartridge.read_ines_rom(nestest_rom_file)

        cpu_memory = nesrs.cpu.CpuMemory(cartridge)
        cpu = nesrs.cpu.CPU(cpu_memory)

        cpu._a = 0x00
        cpu._x = 0x00
        cpu._y = 0x00
        cpu._s = 0xFD
        cpu._p = 0x24
        cpu._pc = 0xC000

        cycles = 0
        for x in range(len(nestest_log_lines)):
            actual_log_line = ''
            actual_log_line += to_hex(cpu._pc)
            actual_log_line += '    '
            actual_log_line += 'A:' + to_hex(cpu._a)
            actual_log_line += ' '
            actual_log_line += 'X:' + to_hex(cpu._x)
            actual_log_line += ' '
            actual_log_line += 'Y:' + to_hex(cpu._y)
            actual_log_line += ' '
            actual_log_line += 'P:' + to_hex(cpu._p)
            actual_log_line += ' '
            actual_log_line += 'SP:' + to_hex(cpu._s)
            cycles += cpu.op_cycles * 3
            cycles %= 341
            actual_log_line += ' '
            actual_log_line += 'CYC:' + pad(cycles)

            self.assertEqual(actual_log_line, nestest_log_lines[x])

            cpu.execute_op()

