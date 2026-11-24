# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""coax_manchester_encode (firmware/core/manchester.c) against the format
xmit_serial shifts out, built here from its description."""

import unittest

from core import manchester_encode


def reference(word):
    """The sync bit, the ten bits MSB first, then odd parity over them. Each bit
    is two half-bit levels, 1 as 10 and 0 as 01, MSB first in 32 bits, with 8
    zero bits of padding on the right."""
    bits = [(word >> i) & 1 for i in range(9, -1, -1)]
    parity = 1 if sum(bits) % 2 == 0 else 0
    halves = '10' + ''.join('10' if bit else '01' for bit in bits) + ('10' if parity else '01')
    return int(halves, 2) << 8


class TestManchester(unittest.TestCase):
    def test_known_words(self):
        # Worked by hand: TT/AR, power-on reset, the terminal ID 0x04 as a data
        # word, and all ones.
        cases = {0x000: 0x95555600, 0x00A: 0x95566600, 0x010: 0x95595500, 0x3FF: 0xAAAAAA00}
        for (word, expected) in cases.items():
            with self.subTest(word=f'{word:03x}'):
                self.assertEqual(manchester_encode(word), expected)

    def test_every_word_matches_the_reference(self):
        for word in range(0x400):
            self.assertEqual(manchester_encode(word), reference(word), f'{word:03x}')

    def test_parity_makes_the_ones_odd(self):
        for word in (0x001, 0x003, 0x155, 0x2AA):
            halves = f'{manchester_encode(word) >> 8:024b}'
            pairs = [halves[i:i + 2] for i in range(2, 24, 2)]  # after the sync bit
            self.assertEqual(pairs.count('10') % 2, 1, f'{word:03x}')

    def test_bits_above_the_tenth_are_ignored(self):
        self.assertEqual(manchester_encode(0x400), manchester_encode(0x000))


if __name__ == '__main__':
    unittest.main()
