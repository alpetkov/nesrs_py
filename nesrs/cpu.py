from enum import Enum

C_FLAG = 0x01
Z_FLAG = 0x02
I_FLAG = 0x04
D_FLAG = 0x08
B_FLAG = 0x10
R_FLAG = 0x20
V_FLAG = 0x40
N_FLAG = 0x80

OP_CYCLES = [
   7, 6, 2, 8, 3, 3, 5, 5, 3, 2, 2, 2, 4, 4, 6, 6,
   2, 5, 2, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
   6, 6, 2, 8, 3, 3, 5, 5, 4, 2, 2, 2, 4, 4, 6, 6,
   2, 5, 2, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
   6, 6, 2, 8, 3, 3, 5, 5, 3, 2, 2, 2, 3, 4, 6, 6,
   2, 5, 2, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
   6, 6, 2, 8, 3, 3, 5, 5, 4, 2, 2, 2, 5, 4, 6, 6,
   2, 5, 2, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
   2, 6, 2, 6, 3, 3, 3, 3, 2, 2, 2, 2, 4, 4, 4, 4,
   2, 6, 2, 6, 4, 4, 4, 4, 2, 5, 2, 5, 5, 5, 5, 5,
   2, 6, 2, 6, 3, 3, 3, 3, 2, 2, 2, 2, 4, 4, 4, 4,
   2, 5, 2, 5, 4, 4, 4, 4, 2, 4, 2, 4, 4, 4, 4, 4,
   2, 6, 2, 8, 3, 3, 5, 5, 2, 2, 2, 2, 4, 4, 6, 6,
   2, 5, 2, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
   2, 6, 3, 8, 3, 3, 5, 5, 2, 2, 2, 2, 4, 4, 6, 6,
   2, 5, 2, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
   ]


def is_page_boundary_crossed(address1, address2):
    return (address1 >> 8) != (address2 >> 8)


class InterruptType(Enum):
    RESET = 0
    NMI = 1
    IRQ = 2


class CpuAddressingMode(Enum):
    # 1. Accumulator addressing - ACC
    ACC = 0
    # 2. Implied addressing - IMPL
    IMPL = 1

    # 3. Immediate addressing - IMM
    IMM = 2

    # 4. Absolute addressing - ABS
    ABS = 3

    # 5. Zero page addressing - ZP
    ZP = 4

    # 6. Indexed zero page addressing with register X - ZP, X
    ZPX = 5

    # 7. Indexed zero page addressing with register Y - ZP, Y
    ZPY = 6

    # 8. Indexed absolute addressing with register X - ABS, X
    ABSX = 7  # countAdditionalCycleOnPageBoundaryCrossed - FALSE
    ABSX_ = 8  # countAdditionalCycleOnPageBoundaryCrossed - TRUE

    # 9. Indexed absolute addressing with register Y - ABS, Y
    ABSY = 9  # countAdditionalCycleOnPageBoundaryCrossed - FALSE
    ABSY_ = 10  # countAdditionalCycleOnPageBoundaryCrossed - TRUE

    # 10. Relative addressing - REL
    REL = 11

    # 11. Indexed indirect (pre-indexed) addressing with register X - (IND, X)
    INDX = 12

    # 12. Indirect indexed (post-indexed) addressing with register Y - (IND), Y
    IND_Y = 13  # countAdditionalCycleOnPageBoundaryCrossed - FALSE
    IND_Y_ = 14  # countAdditionalCycleOnPageBoundaryCrossed - TRUE

    # 13. Absolute indirect addressing - IND
    IND = 15  # isPageWrappingAllowed - TRUE
    IND_ = 16  # isPageWrappingAllowed - FALSE


class CpuMemory(object):
    def __init__(self, cartridge):
        self._ram = [0 for i in range(0x800)]  # 2Kb
        self._cartridge = cartridge

    def read_memory(self, address):
        decoded_address = self._decode_cpu_address(address)

        if 0x0 <= decoded_address <= 0x07FF:
            # RAM
            return self._ram[decoded_address]

        elif 0x4020 <= decoded_address:
            # Cartridge
            return self._cartridge.read_prg_memory(decoded_address)

        return 0

    def write_memory(self, address, value):
        decoded_address = self._decode_cpu_address(address)

        if 0x0 <= decoded_address <= 0x07FF:
            # RAM
            self._ram[decoded_address] = value;
        elif 0x4020 <= decoded_address:
            # Cartridge
            self._cartridge.write_prg_memory(decoded_address, value)

    @staticmethod
    def _decode_cpu_address(address):
        if address < 0x2000:
            # RAM
            address = address & 0x07FF
        elif address < 0x4000:
            # PPU Registers
            address = 0x2000 | (address & 0x0007)

        return address


class CPU(object):

    def __init__(self, cpu_memory):
        self._cpu_memory = cpu_memory

        self._a = 0x00
        self._x = 0x00
        self._y = 0x00
        self._s = 0x00
        self._p = 0x00
        self._pc = 0x00
        self.op_cycles = 0
        self._pending_interrupt = None

        self._addressing_mode_map = {
            CpuAddressingMode.ACC: lambda: 0,
            CpuAddressingMode.IMPL: lambda: 0,
            CpuAddressingMode.IMM: lambda: self._calculate_memory_address_imm(),
            CpuAddressingMode.ABS: lambda: self._calculate_memory_address_abs(),
            CpuAddressingMode.ZP: lambda: self._calculate_memory_address_zp(),
            CpuAddressingMode.ZPX: lambda: self._calculate_memory_address_zpx(),
            CpuAddressingMode.ZPY: lambda: self._calculate_memory_address_zpy(),
            CpuAddressingMode.ABSX: lambda: self._calculate_memory_address_absx(False),
            CpuAddressingMode.ABSX_: lambda: self._calculate_memory_address_absx(True),
            CpuAddressingMode.ABSY: lambda: self._calculate_memory_address_absy(False),
            CpuAddressingMode.ABSY_: lambda: self._calculate_memory_address_absy(True),
            CpuAddressingMode.REL: lambda: self._calculate_memory_address_rel(),
            CpuAddressingMode.INDX: lambda: self._calculate_memory_address_indx_(),
            CpuAddressingMode.IND_Y: lambda: self._calculate_memory_address_ind_y(False),
            CpuAddressingMode.IND_Y_: lambda: self._calculate_memory_address_ind_y(True),
            CpuAddressingMode.IND: lambda: self._calculate_memory_address_ind(False),
            CpuAddressingMode.IND_: lambda: self. _calculate_memory_address_ind(True)
        }

        self._op_code_map = {
            # 1. ADC
            0x69: lambda: self._op_adc(CpuAddressingMode.IMM),
            0x65: lambda: self._op_adc(CpuAddressingMode.ZP),
            0x75: lambda: self._op_adc(CpuAddressingMode.ZPX),
            0x6D: lambda: self._op_adc(CpuAddressingMode.ABS),
            0x7D: lambda: self._op_adc(CpuAddressingMode.ABSX_),
            0x79: lambda: self._op_adc(CpuAddressingMode.ABSY_),
            0x61: lambda: self._op_adc(CpuAddressingMode.INDX),
            0x71: lambda: self._op_adc(CpuAddressingMode.IND_Y_),

            # 2. AND
            0x29: lambda: self._op_and(CpuAddressingMode.IMM),
            0x25: lambda: self._op_and(CpuAddressingMode.ZP),
            0x35: lambda: self._op_and(CpuAddressingMode.ZPX),
            0x2D: lambda: self._op_and(CpuAddressingMode.ABS),
            0x3D: lambda: self._op_and(CpuAddressingMode.ABSX_),
            0x39: lambda: self._op_and(CpuAddressingMode.ABSY_),
            0x21: lambda: self._op_and(CpuAddressingMode.INDX),
            0x31: lambda: self._op_and(CpuAddressingMode.IND_Y_),

            # 3. ASL
            0x0A: lambda: self._op_asl(CpuAddressingMode.ACC),
            0x06: lambda: self._op_asl(CpuAddressingMode.ZP),
            0x16: lambda: self._op_asl(CpuAddressingMode.ZPX),
            0x0E: lambda: self._op_asl(CpuAddressingMode.ABS),
            0x1E: lambda: self._op_asl(CpuAddressingMode.ABSX),

            # 4. BCC
            0x90: lambda: self._op_bcc(CpuAddressingMode.REL),

            # 5. BCS
            0xB0: lambda: self._op_bcs(CpuAddressingMode.REL),

            # 6. BEQ
            0xF0: lambda: self._op_beq(CpuAddressingMode.REL),

            # 7. BIT
            0x24: lambda: self._op_bit(CpuAddressingMode.ZP),
            0x2C: lambda: self._op_bit(CpuAddressingMode.ABS),

            # 8. BMI
            0x30: lambda: self._op_bmi(CpuAddressingMode.REL),

            # 9. BNE
            0xD0: lambda: self._op_bne(CpuAddressingMode.REL),

            # 10. BPL
            0x10: lambda: self._op_bpl(CpuAddressingMode.REL),

            # 11. BRK
            0x00: lambda: self._op_brk(),

            # 12. BVC
            0x50: lambda: self._op_bvc(CpuAddressingMode.REL),

            # 13. BVS
            0x70: lambda: self._op_bvs(CpuAddressingMode.REL),

            # 14. CLC
            0x18: lambda: self._op_clc(),

            # 15. CLD
            0xD8: lambda: self._op_cld(),

            # 16. CLI
            0x58: lambda: self._op_cli(),

            # 17. CLV
            0xB8: lambda: self._op_clv(),

            # 18. CMP
            0xC9: lambda: self._op_cmp(CpuAddressingMode.IMM),
            0xC5: lambda: self._op_cmp(CpuAddressingMode.ZP),
            0xD5: lambda: self._op_cmp(CpuAddressingMode.ZPX),
            0xCD: lambda: self._op_cmp(CpuAddressingMode.ABS),
            0xDD: lambda: self._op_cmp(CpuAddressingMode.ABSX_),
            0xD9: lambda: self._op_cmp(CpuAddressingMode.ABSY_),
            0xC1: lambda: self._op_cmp(CpuAddressingMode.INDX),
            0xD1: lambda: self._op_cmp(CpuAddressingMode.IND_Y_),

            # 19. CPX
            0xE0: lambda: self._op_cpx(CpuAddressingMode.IMM),
            0xE4: lambda: self._op_cpx(CpuAddressingMode.ZP),
            0xEC: lambda: self._op_cpx(CpuAddressingMode.ABS),

            # 20. CPY
            0xC0: lambda: self._op_cpy(CpuAddressingMode.IMM),
            0xC4: lambda: self._op_cpy(CpuAddressingMode.ZP),
            0xCC: lambda: self._op_cpy(CpuAddressingMode.ABS),

            # 21. DEC
            0xC6: lambda: self._op_dec(mode=CpuAddressingMode.ZP),
            0xD6: lambda: self._op_dec(mode=CpuAddressingMode.ZPX),
            0xCE: lambda: self._op_dec(mode=CpuAddressingMode.ABS),
            0xDE: lambda: self._op_dec(mode=CpuAddressingMode.ABSX),

            # 22. DEX
            0xCA: lambda: self._op_dex(),

            # 23. DEY
            0x88: lambda: self._op_dey(),

            # 24. EOR
            0x49: lambda: self._op_eor(CpuAddressingMode.IMM),
            0x45: lambda: self._op_eor(CpuAddressingMode.ZP),
            0x55: lambda: self._op_eor(CpuAddressingMode.ZPX),
            0x4D: lambda: self._op_eor(CpuAddressingMode.ABS),
            0x5D: lambda: self._op_eor(CpuAddressingMode.ABSX_),
            0x59: lambda: self._op_eor(CpuAddressingMode.ABSY_),
            0x41: lambda: self._op_eor(CpuAddressingMode.INDX),
            0x51: lambda: self._op_eor(CpuAddressingMode.IND_Y_),

            # 25. INC
            0xE6: lambda: self._op_inc(CpuAddressingMode.ZP),
            0xF6: lambda: self._op_inc(CpuAddressingMode.ZPX),
            0xEE: lambda: self._op_inc(CpuAddressingMode.ABS),
            0xFE: lambda: self._op_inc(CpuAddressingMode.ABSX),

            # 26. INX
            0xE8: lambda: self._op_inx(),

            # 27. INY
            0xC8: lambda: self._op_iny(),

            # 28. JMP
            0x4C: lambda: self._op_jmp(CpuAddressingMode.ABS),
            0x6C: lambda: self._op_jmp(CpuAddressingMode.IND_),

            # 29. JSR
            0x20: lambda: self._op_jsr(CpuAddressingMode.ABS),

            # 30. LDA
            0xA9: lambda: self._op_lda(CpuAddressingMode.IMM),
            0xA5: lambda: self._op_lda(CpuAddressingMode.ZP),
            0xB5: lambda: self._op_lda(CpuAddressingMode.ZPX),
            0xAD: lambda: self._op_lda(CpuAddressingMode.ABS),
            0xBD: lambda: self._op_lda(CpuAddressingMode.ABSX_),
            0xB9: lambda: self._op_lda(CpuAddressingMode.ABSY_),
            0xA1: lambda: self._op_lda(CpuAddressingMode.INDX),
            0xB1: lambda: self._op_lda(CpuAddressingMode.IND_Y_),

            # 31. LDX
            0xA2: lambda: self._op_ldx(CpuAddressingMode.IMM),
            0xA6: lambda: self._op_ldx(CpuAddressingMode.ZP),
            0xB6: lambda: self._op_ldx(CpuAddressingMode.ZPY),
            0xAE: lambda: self._op_ldx(CpuAddressingMode.ABS),
            0xBE: lambda: self._op_ldx(CpuAddressingMode.ABSY_),

            # 32. LDY
            0xA0: lambda: self._op_ldy(CpuAddressingMode.IMM),
            0xA4: lambda: self._op_ldy(CpuAddressingMode.ZP),
            0xB4: lambda: self._op_ldy(CpuAddressingMode.ZPX),
            0xAC: lambda: self._op_ldy(CpuAddressingMode.ABS),
            0xBC: lambda: self._op_ldy(CpuAddressingMode.ABSX_),

            # 33. LSR
            0x4A: lambda: self._op_lsr(CpuAddressingMode.ACC),
            0x46: lambda: self._op_lsr(CpuAddressingMode.ZP),
            0x56: lambda: self._op_lsr(CpuAddressingMode.ZPX),
            0x4E: lambda: self._op_lsr(CpuAddressingMode.ABS),
            0x5E: lambda: self._op_lsr(CpuAddressingMode.ABSX),

            # 34. NOP
            0xEA: lambda: None,

            # 35. ORA
            0x09: lambda: self._op_ora(CpuAddressingMode.IMM),
            0x05: lambda: self._op_ora(CpuAddressingMode.ZP),
            0x15: lambda: self._op_ora(CpuAddressingMode.ZPX),
            0x0D: lambda: self._op_ora(CpuAddressingMode.ABS),
            0x1D: lambda: self._op_ora(CpuAddressingMode.ABSX_),
            0x19: lambda: self._op_ora(CpuAddressingMode.ABSY_),
            0x01: lambda: self._op_ora(CpuAddressingMode.INDX),
            0x11: lambda: self._op_ora(CpuAddressingMode.IND_Y_),

            # 36. PHA
            0x48: lambda: self._op_pha(),

            # 37. PHP
            0x08: lambda: self._op_php(),

            # 38. PLA
            0x68: lambda: self._op_pla(),

            # 39. PLP
            0x28: lambda: self._op_plp(),

            # 40. ROL
            0x2A: lambda: self._op_rol(CpuAddressingMode.ACC),
            0x26: lambda: self._op_rol(CpuAddressingMode.ZP),
            0x36: lambda: self._op_rol(CpuAddressingMode.ZPX),
            0x2E: lambda: self._op_rol(CpuAddressingMode.ABS),
            0x3E: lambda: self._op_rol(CpuAddressingMode.ABSX),

            # 41. ROR
            0x6A: lambda: self._op_ror(CpuAddressingMode.ACC),
            0x66: lambda: self._op_ror(CpuAddressingMode.ZP),
            0x76: lambda: self._op_ror(CpuAddressingMode.ZPX),
            0x6E: lambda: self._op_ror(CpuAddressingMode.ABS),
            0x7E: lambda: self._op_ror(CpuAddressingMode.ABSX),

            # 42. RTI
            0x40: lambda: self._op_rti(),

            # 43. RTS
            0x60: lambda: self._op_rts(),

            # 44. SBC
            0xE9: lambda: self._op_sbc(CpuAddressingMode.IMM),
            0xE5: lambda: self._op_sbc(CpuAddressingMode.ZP),
            0xF5: lambda: self._op_sbc(CpuAddressingMode.ZPX),
            0xED: lambda: self._op_sbc(CpuAddressingMode.ABS),
            0xFD: lambda: self._op_sbc(CpuAddressingMode.ABSX_),
            0xF9: lambda: self._op_sbc(CpuAddressingMode.ABSY_),
            0xE1: lambda: self._op_sbc(CpuAddressingMode.INDX),
            0xF1: lambda: self._op_sbc(CpuAddressingMode.IND_Y_),

            # 45. SEC
            0x38: lambda: self._op_sec(),

            # 46. SED
            0xF8: lambda: self._op_sed(),

            # 47. SEI
            0x78: lambda: self._op_sei(),

            # 48. STA
            0x85: lambda: self._op_sta(CpuAddressingMode.ZP),
            0x95: lambda: self._op_sta(CpuAddressingMode.ZPX),
            0x8D: lambda: self._op_sta(CpuAddressingMode.ABS),
            0x9D: lambda: self._op_sta(CpuAddressingMode.ABSX),
            0x99: lambda: self._op_sta(CpuAddressingMode.ABSY),
            0x81: lambda: self._op_sta(CpuAddressingMode.INDX),
            0x91: lambda: self._op_sta(CpuAddressingMode.IND_Y),

            # 49. STX
            0x86: lambda: self._op_stx(CpuAddressingMode.ZP),
            0x96: lambda: self._op_stx(CpuAddressingMode.ZPY),
            0x8E: lambda: self._op_stx(CpuAddressingMode.ABS),

            # 50. STY
            0x84: lambda: self._op_sty(CpuAddressingMode.ZP),
            0x94: lambda: self._op_sty(CpuAddressingMode.ZPX),
            0x8C: lambda: self._op_sty(CpuAddressingMode.ABS),

            # 51. TAX
            0xAA: lambda: self._op_tax(),

            # 52. TAY
            0xA8: lambda: self._op_tay(),

            # 53. TSX
            0xBA: lambda: self._op_tsx(),

            # 54. TXA
            0x8A: lambda: self._op_txa(),

            # 55. TXS
            0x9A: lambda: self._op_txs(),

            # 56. TYA
            0x98: lambda: self._op_tya(),

            # Unofficial opcodes

            # DOP
            0x04: lambda: self._op_dop(CpuAddressingMode.ZP),
            0x14: lambda: self._op_dop(CpuAddressingMode.ZPX),
            0x34: lambda: self._op_dop(CpuAddressingMode.ZPX),
            0x44: lambda: self._op_dop(CpuAddressingMode.ZP),
            0x54: lambda: self._op_dop(CpuAddressingMode.ZPX),
            0x64: lambda: self._op_dop(CpuAddressingMode.ZP),
            0x74: lambda: self._op_dop(CpuAddressingMode.ZPX),
            0x80: lambda: self._op_dop(CpuAddressingMode.IMM),
            0x82: lambda: self._op_dop(CpuAddressingMode.IMM),
            0x89: lambda: self._op_dop(CpuAddressingMode.IMM),
            0xC2: lambda: self._op_dop(CpuAddressingMode.IMM),
            0xD4: lambda: self._op_dop(CpuAddressingMode.ZPX),
            0xE2: lambda: self._op_dop(CpuAddressingMode.IMM),
            0xF4: lambda: self._op_dop(CpuAddressingMode.ZPX),

            # TOP
            0x0C: lambda: self._op_top(CpuAddressingMode.ABS),
            0x1C: lambda: self._op_top(CpuAddressingMode.ABSX_),
            0x3C: lambda: self._op_top(CpuAddressingMode.ABSX_),
            0x5C: lambda: self._op_top(CpuAddressingMode.ABSX_),
            0x7C: lambda: self._op_top(CpuAddressingMode.ABSX_),
            0xDC: lambda: self._op_top(CpuAddressingMode.ABSX_),
            0xFC: lambda: self._op_top(CpuAddressingMode.ABSX_),

            # LAX
            0xA7: lambda: self._op_lax(CpuAddressingMode.ZP),
            0xB7: lambda: self._op_lax(CpuAddressingMode.ZPY),
            0xAF: lambda: self._op_lax(CpuAddressingMode.ABS),
            0xBF: lambda: self._op_lax(CpuAddressingMode.ABSY),
            0xA3: lambda: self._op_lax(CpuAddressingMode.INDX),
            0xB3: lambda: self._op_lax(CpuAddressingMode.IND_Y_),

            # AAX
            0x87: lambda: self._op_aax(CpuAddressingMode.ZP),
            0x97: lambda: self._op_aax(CpuAddressingMode.ZPY),
            0x83: lambda: self._op_aax(CpuAddressingMode.INDX),
            0x8F: lambda: self._op_aax(CpuAddressingMode.ABS),

            # SBC
            0xEB: lambda: self._op_sbc(CpuAddressingMode.IMM),

            # DCP
            0xC7: lambda: self._op_dcp(CpuAddressingMode.ZP),
            0xD7: lambda: self._op_dcp(CpuAddressingMode.ZPX),
            0xCF: lambda: self._op_dcp(CpuAddressingMode.ABS),
            0xDF: lambda: self._op_dcp(CpuAddressingMode.ABSX),
            0xDB: lambda: self._op_dcp(CpuAddressingMode.ABSY),
            0xC3: lambda: self._op_dcp(CpuAddressingMode.INDX),
            0xD3: lambda: self._op_dcp(CpuAddressingMode.IND_Y),

            # ISC
            0xE7: lambda: self._op_isc(CpuAddressingMode.ZP),
            0xF7: lambda: self._op_isc(CpuAddressingMode.ZPX),
            0xEF: lambda: self._op_isc(CpuAddressingMode.ABS),
            0xFF: lambda: self._op_isc(CpuAddressingMode.ABSX),
            0xFB: lambda: self._op_isc(CpuAddressingMode.ABSY),
            0xE3: lambda: self._op_isc(CpuAddressingMode.INDX),
            0xF3: lambda: self._op_isc(CpuAddressingMode.IND_Y),

            # SLO
            0x07: lambda: self._op_slo(CpuAddressingMode.ZP),
            0x17: lambda: self._op_slo(CpuAddressingMode.ZPX),
            0x0F: lambda: self._op_slo(CpuAddressingMode.ABS),
            0x1F: lambda: self._op_slo(CpuAddressingMode.ABSX),
            0x1B: lambda: self._op_slo(CpuAddressingMode.ABSY),
            0x03: lambda: self._op_slo(CpuAddressingMode.INDX),
            0x13: lambda: self._op_slo(CpuAddressingMode.IND_Y),

            # RLA
            0x27: lambda: self._op_rla(CpuAddressingMode.ZP),
            0x37: lambda: self._op_rla(CpuAddressingMode.ZPX),
            0x2F: lambda: self._op_rla(CpuAddressingMode.ABS),
            0x3F: lambda: self._op_rla(CpuAddressingMode.ABSX),
            0x3B: lambda: self._op_rla(CpuAddressingMode.ABSY),
            0x23: lambda: self._op_rla(CpuAddressingMode.INDX),
            0x33: lambda: self._op_rla(CpuAddressingMode.IND_Y),

            # SRE
            0x47: lambda: self._op_sre(CpuAddressingMode.ZP),
            0x57: lambda: self._op_sre(CpuAddressingMode.ZPX),
            0x4F: lambda: self._op_sre(CpuAddressingMode.ABS),
            0x5F: lambda: self._op_sre(CpuAddressingMode.ABSX),
            0x5B: lambda: self._op_sre(CpuAddressingMode.ABSY),
            0x43: lambda: self._op_sre(CpuAddressingMode.INDX),
            0x53: lambda: self._op_sre(CpuAddressingMode.IND_Y),

            # RRA
            0x67: lambda: self._op_rra(CpuAddressingMode.ZP),
            0x77: lambda: self._op_rra(CpuAddressingMode.ZPX),
            0x6F: lambda: self._op_rra(CpuAddressingMode.ABS),
            0x7F: lambda: self._op_rra(CpuAddressingMode.ABSX),
            0x7B: lambda: self._op_rra(CpuAddressingMode.ABSY),
            0x63: lambda: self._op_rra(CpuAddressingMode.INDX),
            0x73: lambda: self._op_rra(CpuAddressingMode.IND_Y),
        }

    #
    # Actions
    #
    def turn_on(self):
        self.op_cycles = 7
        self._a = 0x00
        self._x = 0x00
        self._y = 0x00
        self._s = 0xFF
        self._p = B_FLAG | R_FLAG | I_FLAG
        self._pc = self._read_memory(0xFFFD) << 8 | self._read_memory(0xFFFC)

    def reset(self):
        self._request_interrupt(InterruptType.RESET)

    def nmi(self):
        self._request_interrupt(InterruptType.NMI)

    def irq(self):
        self._request_interrupt(InterruptType.IRQ)

    def execute_op(self):
        if self._pending_interrupt is not None:
            self._execute_pending_interrupt_op()
        else:
            op_code = self._read_memory(self._pc)
            self._pc += 1
            self.op_cycles = OP_CYCLES[op_code]
            self._execute_op(op_code)

    def _request_interrupt(self, interrupt_type):
        if self._pending_interrupt is None:
            self._pending_interrupt = interrupt_type
        elif self._pending_interrupt == InterruptType.IRQ:
            self._pending_interrupt = interrupt_type
        elif self._pending_interrupt == InterruptType.NMI:
            if interrupt_type == InterruptType.RESET:
                self._pending_interrupt = interrupt_type
        elif self._pending_interrupt == InterruptType.RESET:
            # Already requested
            pass

    def _execute_pending_interrupt_op(self):
        self.op_cycles = 0

        if self._pending_interrupt == InterruptType.RESET:
            self.op_cycles = 7
            self._a = 0x00
            self._x = 0x00
            self._y = 0x00
            self._s = 0xFF
            self._p = Z_FLAG | R_FLAG
            self._pc = (self._read_memory(0xFFFD) << 8) | self._read_memory(0xFFFC)

        elif self._pending_interrupt == InterruptType.NMI:
            self.op_cycles = 7
            self._push((self._pc >> 8) & 0xFF)
            self._push(self._pc & 0x00FF)
            self._push(self._p & ~B_FLAG)
            self._p = self._p & ~D_FLAG
            self._pc = (self._read_memory(0xFFFB) << 8) | self._read_memory(0xFFFA)

        elif self._pending_interrupt == InterruptType.IRQ and ((self._p & I_FLAG) == 0):
            self.op_cycles = 7
            self._push((self._pc >> 8) & 0xFF)
            self._push(self._pc & 0x00FF)
            self._push(self._p & ~B_FLAG)
            self._p = self._p & ~D_FLAG
            self._p = self._p & ~I_FLAG
            self._pc = (self._read_memory(0xFFFF) << 8) | self._read_memory(0xFFFE)

        self._pending_interrupt = None

    #
    # Memory management
    #
    def _read_memory(self, address):
        return self._cpu_memory.read_memory(address)

    def _write_memory(self, address, value):
        self._cpu_memory.write_memory(address, value)

    #
    # Addressing modes
    #
    # 1. Accumulator addressing - ACC
    # 2. Implied addressing - IMPL

    # 3. Immediate addressing - IMM
    def _calculate_memory_address_imm(self):
        result = self._pc
        self._pc += 1
        return result

    # 4. Absolute addressing - ABS
    def _calculate_memory_address_abs(self):
        low = self._read_memory(self._pc)
        self._pc += 1
        high = self._read_memory(self._pc)
        self._pc += 1
        return 0xFFFF & ((high << 8) | low)

    # 5. Zero page addressing - ZP
    def _calculate_memory_address_zp(self):
        low = self._read_memory(self._pc)
        self._pc += 1
        return low

    # 6. Indexed zero page addressing with register X - ZP,X
    def _calculate_memory_address_zpx(self):
        low = self._read_memory(self._pc)
        self._pc += 1
        return 0x00FF & (self._x + low)

    # 7. Indexed zero page addressing with register Y - ZP,Y
    def _calculate_memory_address_zpy(self):
        low = self._read_memory(self._pc)
        self._pc += 1
        return 0x00FF & (self._y + low)

    # 8. Indexed absolute addressing with register X - ABS,X
    def _calculate_memory_address_absx(self, count_additional_cycle_on_page_boundary_crossed):
        low = self._read_memory(self._pc)
        self._pc += 1
        high = self._read_memory(self._pc)
        self._pc += 1
        address = 0xFFFF & ((high << 8) | low)
        result_address = 0xFFFF & (address + self._x)
        if count_additional_cycle_on_page_boundary_crossed and is_page_boundary_crossed(address, result_address):
            self.op_cycles += 1

        return result_address

    # 9. Indexed absolute addressing with register Y - ABS,Y
    def _calculate_memory_address_absy(self, count_additional_cycle_on_page_boundary_crossed):
        low = self._read_memory(self._pc)
        self._pc += 1
        high = self._read_memory(self._pc)
        self._pc += 1
        address = 0xFFFF & ((high << 8) | low)
        result_address = 0xFFFF & (address + self._y)
        if count_additional_cycle_on_page_boundary_crossed and is_page_boundary_crossed(address, result_address):
            self.op_cycles += 1

        return result_address

    # 10. Relative addressing - REL
    def _calculate_memory_address_rel(self):
        inc = self._read_memory(self._pc)
        self._pc += 1
        is_positive = True
        if inc & 0x80 == 0:
            # Positive or Zero
            offset = inc & 0x7F
        else:
            # Negative
            offset = 0x7F + 1 - (inc & 0x7F)
            is_positive = False

        address = self._pc + offset if is_positive else self._pc - offset

        return 0xFFFF & address

    # 11. Indexed indirect (pre-indexed) addressing with register X - (IND,X)
    def _calculate_memory_address_indx_(self):
        low = self._read_memory(self._pc)
        self._pc += 1
        address = 0x00FF & (low + self._x)
        next_address = 0x00FF & (address + 1)
        return 0xFFFF & ((self._read_memory(next_address) << 8) | self._read_memory(address))

    # 12. Indirect indexed (post-indexed) addressing with register Y - (IND),Y
    def _calculate_memory_address_ind_y(self, count_additional_cycle_on_page_boundary_crossed):
        low = self._read_memory(self._pc)
        self._pc += 1
        low_address = self._read_memory(low)
        high_address = self._read_memory(0x00FF & (low + 1))
        address = 0xFFFF & ((high_address << 8) | low_address)
        result_address = 0xFFFF & (address + self._y)
        if count_additional_cycle_on_page_boundary_crossed and is_page_boundary_crossed(address, result_address):
            self.op_cycles += 1

        return result_address

    # 13. Absolute indirect addressing - IND
    def _calculate_memory_address_ind(self, is_page_wrapping_not_allowed):
        low = self._read_memory(self._pc)
        self._pc += 1
        high = self._read_memory(self._pc)
        self._pc += 1
        address = 0xFFFF & ((high << 8) | low)
        next_address = address + 1
        if (address & 0xFF) == 0xFF:
            if is_page_wrapping_not_allowed:
                next_address = address & 0xFF00

        return 0xFFFF & ((self._read_memory(next_address) << 8) | self._read_memory(address))

    def _calculate_memory_address(self, addressing_mode):
        address = self._addressing_mode_map[addressing_mode]()

        return address

    #
    # Stack manipulations
    #
    def _push(self, value):
        self._write_memory(0x0100 | self._s, value)
        self._s = 0xFF if self._s == 0x00 else self._s - 1

    def _pop(self):
        self._s = 0x00 if self._s == 0xFF else self._s + 1

        return self._read_memory(0x0100 | self._s)

    #
    # Ops
    #
    def _execute_op(self, op_code):
        try:
            self._op_code_map[op_code]()
        except KeyError:
            pass

    def _op_adc(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)

        res = self._a + value + (1 if (self._p & C_FLAG) != 0 else 0)

        self._p = self._p & ~(N_FLAG | V_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (res & N_FLAG)  # N
        self._p = self._p | (V_FLAG if (~(self._a ^ value) & (self._a ^ (res & 0xFF)) & 0x80) != 0 else 0)  # V
        self._p = self._p | (Z_FLAG if (res & 0xFF) == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if res > 0xFF else 0)  # C

        self._a = res & 0xFF

    def _op_and(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)

        self._a = self._a & value
        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (self._a & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if self._a == 0 else 0)  # Z

    def _op_asl(self, mode):
        if mode == CpuAddressingMode.ACC:
            self._a = self._op_asl_int(self._a)
        else:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

            new_value = self._op_asl_int(value)
            self._write_memory(address, new_value)

    def _op_asl_int(self, value):
        res = (value << 1) & 0xFF
        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (res & 0x80) > 0 else 0)  # N
        self._p = self._p | (Z_FLAG if res == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (value & 0x80) > 0 else 0)  # C

        return res

    def _op_bcc(self, mode):
        self._op_branch((self._p & C_FLAG) == 0, self._calculate_memory_address(mode))

    def _op_bcs(self, mode):
        self._op_branch((self._p & C_FLAG) != 0, self._calculate_memory_address(mode))

    def _op_beq(self, mode):
        self._op_branch((self._p & Z_FLAG) != 0, self._calculate_memory_address(mode))

    def _op_bmi(self, mode):
        self._op_branch((self._p & N_FLAG) != 0, self._calculate_memory_address(mode))

    def _op_bne(self, mode):
        self._op_branch((self._p & Z_FLAG) == 0, self._calculate_memory_address(mode))

    def _op_bpl(self, mode):
        self._op_branch((self._p & N_FLAG) == 0, self._calculate_memory_address(mode))

    def _op_bvc(self, mode):
        self._op_branch((self._p & V_FLAG) == 0, self._calculate_memory_address(mode))

    def _op_bvs(self, mode):
        self._op_branch((self._p & V_FLAG) != 0, self._calculate_memory_address(mode))

    def _op_branch(self, condition, jump_address):
        if condition:
            if is_page_boundary_crossed(self._pc, jump_address):
                self.op_cycles += 2
            else:
                self.op_cycles += 1

            self._pc = jump_address

    def _op_bit(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)

        self._p = self._p & ~(N_FLAG | V_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (value & 0x80) != 0 else 0)  # N
        self._p = self._p | (V_FLAG if (value & 0x40) != 0 else 0)  # V
        self._p = self._p | (Z_FLAG if (self._a & value) == 0 else 0)  # Z

    def _op_brk(self):
        self._pc += 1  # skip next bite (usually it is a NOP or number that is analyzed by the interrupt handler)
        self._push(self._pc >> 8)  # push high bits
        self._push(self._pc & 0xFF)  # push low bits
        self._p = self._p | B_FLAG  # B
        self._push(self._p)
        self._pc = (self._read_memory(0xFFFF) << 8) | self._read_memory(0xFFFE)

    def _op_clc(self):
        self._p = self._p & ~C_FLAG

    def _op_cld(self):
        self._p = self._p & ~D_FLAG

    def _op_cli(self):
        self._p = self._p & ~I_FLAG

    def _op_clv(self):
        self._p = self._p & ~V_FLAG

    def _op_cmp(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)
        self._op_compare(self._a, value)

    def _op_cpx(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)
        self._op_compare(self._x, value)

    def _op_cpy(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)
        self._op_compare(self._y, value)

    def _op_compare(self, register, value):
        res = (register - value) & 0xFF
        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (res & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if res == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if register >= value else 0)  # C

    def _op_dec(self, mode=None, value=None):
        if mode is not None:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

        result = (value - 1) & 0xFF
        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (result & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if result == 0 else 0)  # Z

        if mode is not None:
            self._write_memory(address, result)

        return result

    def _op_dex(self):
        self._x = self._op_dec(mode=None, value=self._x)

    def _op_dey(self):
        self._y = self._op_dec(mode=None, value=self._y)

    def _op_eor(self, mode=None, value=None):
        if mode is not None:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

        self._a = self._a ^ value
        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (self._a & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if self._a == 0 else 0)  # Z

    def _op_inc(self, mode=None, value=None):
        if mode is not None:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

        result = (value + 1) & 0xFF
        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (result & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if result == 0 else 0)  # Z

        if mode is not None:
            self._write_memory(address, result)

        return result

    def _op_inx(self):
        self._x = self._op_inc(mode=None, value=self._x)

    def _op_iny(self):
        self._y = self._op_inc(mode=None, value=self._y)

    def _op_jmp(self, mode):
        address = self._calculate_memory_address(mode)
        self._pc = address

    def _op_jsr(self, mode):
        address = self._calculate_memory_address(mode)
        self._pc -= 1
        self._push(self._pc >> 8)
        self._push(self._pc & 0xFF)
        self._pc = address

    def _op_lda(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)
        self._a = self._op_load(value)

    def _op_ldx(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)
        self._x = self._op_load(value)

    def _op_ldy(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)
        self._y = self._op_load(value)

    def _op_load(self, value):
        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (value & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if value == 0 else 0)  # Z
        return value

    def _op_lsr(self, mode):
        if mode == CpuAddressingMode.ACC:
            address = 0
            value = self._a
        else:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

        result = 0x7F & (value >> 1)
        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # clear flags
        self._p = self._p | (Z_FLAG if result == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (value & 0x01) != 0 else 0)  # C

        if mode == CpuAddressingMode.ACC:
            self._a = result
        else:
            self._write_memory(address, result)

    def _op_ora(self, mode=None, value=None):
        if mode is not None:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

        self._a = self._a | value
        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (self._a & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if self._a == 0 else 0)  # Z

    def _op_pha(self):
        self._push(self._a)

    def _op_php(self):
        self._push(self._p | B_FLAG)

    def _op_pla(self):
        self._a = self._pop()

        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG & self._a)  # N
        self._p = self._p | (Z_FLAG if self._a == 0 else 0)  # Z

    def _op_plp(self):
        self._p = self._pop() & ~B_FLAG | R_FLAG

    def _op_rol(self, mode):
        if mode == CpuAddressingMode.ACC:
            address = 0
            value = self._a
        else:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

        res = (value << 1) & 0xFF
        res = res | (1 if (self._p & C_FLAG) != 0 else 0)
        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (res & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if res == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (value & 0x80) != 0 else 0)  # C

        if mode == CpuAddressingMode.ACC:
            self._a = res
        else:
            self._write_memory(address, res)

    def _op_ror(self, mode):
        if mode == CpuAddressingMode.ACC:
            address = 0
            value = self._a
        else:
            address = self._calculate_memory_address(mode)
            value = self._read_memory(address)

        res = (value >> 1) & 0xFF
        res = res | (0x80 if (self._p & C_FLAG) != 0 else 0)
        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (res & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if res == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (value & 0x01) != 0 else 0)  # C

        if mode == CpuAddressingMode.ACC:
            self._a = res
        else:
            self._write_memory(address, res)

    def _op_rti(self):
        self._p = self._pop() & ~B_FLAG
        self._p = self._p | R_FLAG
        pcl = self._pop()
        pch = self._pop()
        self._pc = (pch << 8) | pcl

    def _op_rts(self):
        pcl = self._pop()
        pch = self._pop()
        self._pc = (pch << 8) | pcl
        self._pc += 1

    def _op_sbc(self, mode):
        address = self._calculate_memory_address(mode)
        value = self._read_memory(address)

        result = self._a - value - (0 if (self._p & C_FLAG) != 0 else 1)

        self._p = self._p & ~(N_FLAG | V_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (result & N_FLAG)  # N
        self._p = self._p | (V_FLAG if ((self._a ^ value) & (self._a ^ (0xFF & result)) & 0x80) != 0 else 0)  # V
        self._p = self._p | (Z_FLAG if (result & 0xFF) == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (result & 0x100) == 0 else 0)  # C

        self._a = 0xFF & result

    def _op_sec(self):
        self._p = self._p | C_FLAG

    def _op_sed(self):
        self._p = self._p | D_FLAG

    def _op_sei(self):
        self._p = self._p | I_FLAG

    def _op_sta(self, mode):
        address = self._calculate_memory_address(mode)
        self._write_memory(address, self._a)

    def _op_stx(self, mode):
        address = self._calculate_memory_address(mode)
        self._write_memory(address, self._x)

    def _op_sty(self, mode):
        address = self._calculate_memory_address(mode)
        self._write_memory(address, self._y)

    def _op_tax(self):
        self._x = self._a
        self._transfer(self._x)

    def _op_tay(self):
        self._y = self._a
        self._transfer(self._y)

    def _op_tsx(self):
        self._x = self._s
        self._transfer(self._x)

    def _op_txa(self):
        self._a = self._x
        self._transfer(self._a)

    def _op_txs(self):
        self._s = self._x

    def _op_tya(self):
        self._a = self._y
        self._transfer(self._a)

    def _transfer(self, to_register):
        self._p = self._p & ~(N_FLAG | Z_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (to_register & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if to_register == 0 else 0)  # Z

    def _op_dop(self, mode):
        # DOP double NOP
        self._read_memory(self._calculate_memory_address(mode))

    def _op_top(self, mode):
        # TOP triple NOP
        self._read_memory(self._calculate_memory_address(mode))

    def _op_lax(self, mode):
        # LAX Load accumulator and X register with memory Status flags: N,Z

        address = self._calculate_memory_address(mode)
        self._a = self._op_load(self._read_memory(address))
        self._x = self._a

    def _op_aax(self, mode):
        # AAX (SAX) [AXS] AND X register with accumulator and store result in memory.
        address = self._calculate_memory_address(mode)

        result = self._a & self._x
        self._write_memory(address, result)

    def _op_dcp(self, mode):
        # DCP (DCP) [DCM]
        address = self._calculate_memory_address(mode)

        value = self._read_memory(address)
        value = 0xFF & (value - 1)

        value_to_test = self._a - value

        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (value_to_test & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if (value_to_test == 0) else 0)  # Z
        self._p = self._p | (C_FLAG if (value_to_test & 0x100) == 0 else 0)  # C

        self._write_memory(address, value)

    def _op_isc(self, mode):
        # ISC (ISB) [INS] Increase memory by one, then subtract memory from accumulator (with borrow).

        address = self._calculate_memory_address(mode)

        value = self._read_memory(address)
        value = 0xFF & (value + 1)

        result = self._a - value - (0 if (self._p & C_FLAG) != 0 else 1)

        self._p = self._p & ~(N_FLAG | V_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (V_FLAG if ((self._a ^ value) & (self._a ^ (result & 0xFF)) & 0x80) != 0 else 0)  # V
        self._p = self._p | (C_FLAG if (result & 0x100) == 0 else 0)  # C
        self._a = result & 0xFF
        self._p = self._p | (Z_FLAG if (self._a & 0xFF) == 0 else 0)  # Z
        self._p = self._p | (self._a & N_FLAG)  # N

        self._write_memory(address, value)

    def _op_slo(self, mode):
        # SLO (SLO) [ASO] Shift left one bit in memory, then OR accumulator with memory.
        address = self._calculate_memory_address(mode)

        value = self._read_memory(address)
        result = (value << 1) & 0xFF

        self._a = self._a | result

        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (self._a & N_FLAG)  # N
        self._p = self._p | (Z_FLAG if self._a == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (value & 0x80) != 0 else 0)  # C

        self._write_memory(address, result)

    def _op_rla(self, mode):
        # RLA (RLA) [RLA] Rotate one bit left in memory, then AND accumulator with memory.
        address = self._calculate_memory_address(mode)

        value = self._read_memory(address)

        res = (value << 1) & 0xFF
        res = res | (1 if (self._p & C_FLAG) != 0 else 0)

        self._a = self._a & res

        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (N_FLAG if (self._a & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if self._a == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (value & 0x80) != 0 else 0)  # C

        self._write_memory(address, res)

    def _op_sre(self, mode):
        # SRE (SRE) [LSE] Shift right one bit in memory, then EOR accumulator with memory.
        address = self._calculate_memory_address(mode)

        value = self._read_memory(address)

        res = 0x7F & (value >> 1)
        self._a = self._a ^ res

        self._p = self._p & ~(N_FLAG | Z_FLAG | C_FLAG)  # clear flags
        self._p = self._p | (N_FLAG if (self._a & 0x80) != 0 else 0)  # N
        self._p = self._p | (Z_FLAG if res == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if (value & 0x01) != 0 else 0)  # C

        self._write_memory(address, res)

    def _op_rra(self, mode):
        # RRA (RRA) [RRA] Rotate one bit right in memory, then add memory to accumulator (with carry).
        address = self._calculate_memory_address(mode)

        value1 = self._read_memory(address)
        value = (value1 >> 1) & 0xFF
        value = value | (0x80 if (self._p & C_FLAG) != 0 else 0)

        res = self._a + value + (1 if (value1 & 0x01) != 0 else 0)

        self._p = self._p & ~(N_FLAG | V_FLAG | Z_FLAG | C_FLAG)  # Clear flags
        self._p = self._p | (res & N_FLAG)  # N
        self._p = self._p | (V_FLAG if (~(self._a ^ value) & (self._a ^ (res & 0xFF)) & 0x80) != 0 else 0)  # V
        self._p = self._p | (Z_FLAG if (res & 0xFF) == 0 else 0)  # Z
        self._p = self._p | (C_FLAG if res > 0xFF else 0)  # C

        self._a = res & 0xFF

        self._write_memory(address, value)
