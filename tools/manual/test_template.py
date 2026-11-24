# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""docs/manual/style.typ and setup-rows.typ, built into small documents of their own (#136)."""

import json
import os
import tempfile
import unittest

import manual_paths
import build
import typst_run
from edition import BuildError

WHEN = 1791979200
ROWS = [
    {'screen': 'Display Setup, page 1', 'parent': 'Rule line', 'label': 'Style', 'choices': ['Horizontal', 'None'],
     'default': 'Horizontal', 'field': 'ruler_style', 'acted': True},
    {'screen': 'Display Setup, page 1', 'parent': '', 'label': 'Row/column indicator', 'choices': ['On', 'Off'],
     'default': 'On', 'field': 'indicator', 'acted': True},
    {'screen': 'Online Setup and Utility', 'parent': '', 'label': 'Setup local functions', 'choices': [],
     'default': None, 'field': None, 'acted': False},
]
KEYS = ['Display Setup, page 1 / Rule line / Style', 'Display Setup, page 1 / Row/column indicator',
        'Online Setup and Utility / Setup local functions']
ROWS_DOC = '''#import "/docs/manual/setup-rows.typ": setup-rows, check-prose, setup-table, menu-table, unavailable
#let prose = (PROSE)
#check-prose(setup-rows, prose)
#setup-table(setup-rows, prose, "Display Setup, page 1")
#menu-table(setup-rows, prose, "Online Setup and Utility")
'''
BOOK_DOC = '''#import "/docs/manual/style.typ": *
#show: book
#counter(page).update(1)
#set page(numbering: "1")
= A chapter <chapter>
Press #keys("Shift", "Alt", "X"), then #key("F3"). The screen says #on-screen[F3=Exit].
== A section <section>
#note[A note.]
#attention[An attention notice.]
See @chapter and @section.
#figure(kind: table, caption: [A table], table(columns: 2, table.header[One][Two], [a], [b]))
'''

APPENDIX_DOC = '''= Another
#figure(kind: table, caption: [Its table], table(columns: 1, [b]))
#show: appendix
= Keymaps <keymaps>
#figure(kind: table, caption: [Keys], table(columns: 1, [a]))
See @keymaps.
'''

KEYMAP_ROWS = [
    {'chord': [], 'key': 'Enter', 'label': 'Enter', 'code': 88, 'modifiers': 'kept', 'reads': ['ENTER'],
     'local': None, 'rule': False},
    {'chord': ['Alt'], 'key': '1', 'label': 'Dup/PA1', 'code': 103, 'modifiers': 'none', 'reads': ['PA1'],
     'local': None, 'rule': False},
    {'chord': [], 'key': 'Left Ctrl', 'label': 'Reset/Quit', 'code': 17, 'modifiers': 'kept', 'reads': ['RESET'],
     'local': None, 'rule': False},
    {'chord': [], 'key': 'A', 'label': 'A', 'code': 28, 'modifiers': 'kept', 'reads': ['a'], 'local': None,
     'rule': False},
    {'chord': ['Shift', 'Alt'], 'key': 'X', 'label': None, 'code': None, 'modifiers': None, 'reads': [],
     'local': 'SetUp', 'rule': False},
    {'chord': ['Shift'], 'key': 'Home', 'label': 'Rule', 'code': 98, 'modifiers': 'none', 'reads': [],
     'local': 'Rule', 'rule': True},
    {'chord': [], 'key': ']', 'label': None, 'code': None, 'modifiers': None, 'reads': [], 'local': None,
     'rule': False},
]
KEYMAP = {'name': 'us104', 'title': 'US 104-key (ANSI)', 'status': 'tested', 'base': None, 'devices': [],
          'rows': KEYMAP_ROWS}
FUNCTIONS = {'ENTER': True, 'PA1': True, 'RESET': False}  # each with whether oec acts on it
LOCAL = ('SetUp', 'Rule')
KEYS_DOC = '''#import "/docs/manual/keymap-rows.typ": *
#let functions = (FUNCTIONS)
#let local = (LOCAL)
#check-keys(keymap-data, functions, local)
#let km = keymaps.first()
#function-table(km, functions, "send")
#local-table(km, local)
#keymap-table(km, functions)
EXTRA
'''


class Docs(unittest.TestCase):

    def setUp(self):
        os.makedirs(manual_paths.TESTS_OUT, exist_ok=True)
        self.dir = tempfile.TemporaryDirectory(dir=manual_paths.TESTS_OUT)
        self.addCleanup(self.dir.cleanup)
        self.build_dir = '/' + os.path.relpath(self.dir.name, manual_paths.ROOT)

    def compile(self, text):
        path = os.path.join(self.dir.name, 'doc.typ')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(text)
        typst_run.compile_pdf(path, os.path.join(self.dir.name, 'doc.pdf'), {'build': self.build_dir}, WHEN)
        return typst_run.placed(path, {'build': self.build_dir})


class TestCoverage(Docs):

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.dir.name, 'data'))
        with open(os.path.join(self.dir.name, 'data', 'setup.json'), 'w', encoding='utf-8') as stream:
            json.dump(ROWS, stream)

    def build_with(self, keys, unavailable=(KEYS[2],)):
        """Prose for keys, the ones in unavailable marked as rows the firmware doesn't act on."""
        prose = ''.join(f'{json.dumps(k)}: unavailable[Sounds the alarm.], ' if k in unavailable
                        else f'{json.dumps(k)}: [Does this.], ' for k in keys) or ':'
        self.compile(ROWS_DOC.replace('PROSE', prose))

    def test_every_row_described_builds(self):
        self.build_with(KEYS)

    def test_a_row_with_no_description_stops_the_build_and_is_named(self):
        with self.assertRaisesRegex(BuildError, 'SetUp rows with no description: Display Setup, page 1 / '
                                                'Row/column indicator'):
            self.build_with([KEYS[0], KEYS[2]])

    def test_a_description_with_no_row_stops_the_build_and_is_named(self):
        with self.assertRaisesRegex(BuildError, "SetUp rows the firmware doesn't have: Display Setup, page 1 / "
                                                'Rule line / Colour'):
            self.build_with(KEYS + ['Display Setup, page 1 / Rule line / Colour'])

    def test_a_row_the_firmware_acts_on_described_as_unavailable_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'SetUp rows the firmware acts on, described as unavailable: '
                                                'Display Setup, page 1 / Row/column indicator'):
            self.build_with(KEYS, unavailable=(KEYS[1], KEYS[2]))

    def test_a_row_that_sounds_the_alarm_described_as_working_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'SetUp rows that sound the alarm, described as working: '
                                                'Online Setup and Utility / Setup local functions'):
            self.build_with(KEYS, unavailable=())


class TestStyle(Docs):

    def test_a_chapter_builds_with_its_pieces_and_marks_where_they_land(self):
        self.assertEqual([m['what'] for m in self.compile(BOOK_DOC)],
                         ['Chapter 1 [A chapter]', 'section [A section]', 'Table 1-1 [A table]'])

    def test_a_figure_with_no_caption_builds_and_is_marked(self):
        doc = BOOK_DOC + '#figure(rect(width: 1in, height: 0.5in))\n'
        self.assertEqual([m['what'] for m in self.compile(doc)],
                         ['Chapter 1 [A chapter]', 'section [A section]', 'Table 1-1 [A table]', 'Figure 1-1'])

    def test_an_appendix_is_lettered(self):
        doc = BOOK_DOC + APPENDIX_DOC
        self.assertEqual([m['what'] for m in self.compile(doc)][-4:],
                         ['Chapter 2 [Another]', 'Table 2-1 [Its table]', 'Appendix A [Keymaps]',
                          'Table A-1 [Keys]'])

    def test_the_contents_and_references_name_an_appendix_as_one(self):
        doc = BOOK_DOC + APPENDIX_DOC + '''#context assert.eq(chapter-label(query(<keymaps>).first()), "Appendix A")
#context assert.eq(chapter-label(query(<chapter>).first()), "Chapter 1")
'''
        self.compile(doc)

    def test_a_long_table_starts_on_the_page_it_follows(self):
        # A table runs on to the next page, its header repeated, rather than leaving a page half empty.
        rows = ', '.join(f'[row {n}]' for n in range(60))
        doc = BOOK_DOC + f'#figure(kind: table, caption: [Long], table(columns: 1, [#placed("first row")], {rows}))\n'
        marks = {m['what']: m['page'] for m in self.compile(doc)}
        self.assertEqual(marks['first row'], marks['Chapter 1 [A chapter]'])
        self.assertGreater(marks['Table 1-2 [Long]'], marks['first row'])

    def test_on_screen_text_the_font_cant_draw_stops_the_build(self):
        # Typst would set it in another font, or as nothing, and say nothing (#141's review).
        with self.assertRaisesRegex(BuildError, "3270font's subset has no ☃ for on-screen text"):
            self.compile(BOOK_DOC + '#on-screen[Press ☃ now]\n')
        self.compile(BOOK_DOC + '#on-screen[Enter password ===========>]\n')

    def test_a_float_that_lands_above_its_heading_is_caught(self):
        doc = BOOK_DOC + 'Some text.\n\n== Late\n#figure(placement: top, rect(height: 1in), caption: [Late])\n'
        with self.assertRaisesRegex(BuildError, r'Figure 1-1 lands above its heading \[Late\]'):
            build.check_floats(self.compile(doc))

    def test_on_screen_text_is_checked_quotes_and_all(self):
        # A quote in markup is a smartquote element, which the check read as a blank (#143's review).
        self.compile(BOOK_DOC + """#assert.eq(plain-text([it's "so"]), "it's \\"so\\"")
#on-screen[It's]
""")

    def test_cells_are_cut_from_a_drawn_screen(self):
        os.makedirs(os.path.join(self.dir.name, 'screens'))
        from PIL import Image
        Image.new('RGB', (32, 19)).save(os.path.join(self.dir.name, 'screens', 'status-wait-640.png'))
        self.compile(BOOK_DOC + '#cells-image("status-wait", 4)\n')

    def test_on_a4_too(self):
        path = os.path.join(self.dir.name, 'doc.typ')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(BOOK_DOC)
        typst_run.compile_pdf(path, os.path.join(self.dir.name, 'a4.pdf'), {'paper': 'a4'}, WHEN)

    def test_another_paper_is_refused(self):
        path = os.path.join(self.dir.name, 'doc.typ')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(BOOK_DOC)
        with self.assertRaisesRegex(BuildError, 'paper must be us-letter or a4'):
            typst_run.compile_pdf(path, os.path.join(self.dir.name, 'x.pdf'), {'paper': 'a5'}, WHEN)



class TestKeymapCoverage(Docs):

    def build_with(self, functions=FUNCTIONS, local=LOCAL, keymaps=(KEYMAP,), ignores=('RESET',), extra=''):
        os.makedirs(os.path.join(self.dir.name, 'data'), exist_ok=True)
        with open(os.path.join(self.dir.name, 'data', 'keymaps.json'), 'w', encoding='utf-8') as stream:
            json.dump({'keymaps': list(keymaps), 'oec_ignores': list(ignores)}, stream)
        # Each function's oec mark, or (mark, group) for a group of its own.
        functions = {name: f if isinstance(f, tuple) else (f, 'send') for (name, f) in functions.items()}
        entries = ''.join(f'{json.dumps(name)}: (name: {json.dumps(name.title())}, group: {json.dumps(group)}, '
                          f'oec: {"true" if oec else "false"}, body: [Does it.]), '
                          for (name, (oec, group)) in functions.items()) or ':'
        described = ''.join(f'{json.dumps(name)}: [Does it.], ' for name in local) or ':'
        self.compile(KEYS_DOC.replace('FUNCTIONS', entries).replace('LOCAL', described).replace('EXTRA', extra))

    def test_every_key_described_builds(self):
        self.build_with()

    def test_a_key_with_no_description_stops_the_build_and_is_named(self):
        with self.assertRaisesRegex(BuildError, 'keys with no description: PA1'):
            self.build_with({'ENTER': True, 'RESET': False})

    def test_a_description_of_a_key_no_keymap_has_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'descriptions of keys no keymap has: JUMP'):
            self.build_with({**FUNCTIONS, 'JUMP': False})

    def test_a_key_oec_ignores_described_as_working_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'keys oec ignores, described as working under oec: RESET'):
            self.build_with({**FUNCTIONS, 'RESET': True})

    def test_a_key_oec_acts_on_described_as_ignored_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'keys oec acts on, described as ignored by oec: ENTER'):
            self.build_with({**FUNCTIONS, 'ENTER': False})

    def test_a_local_key_with_no_description_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'local keys with no description: Rule'):
            self.build_with(local=('SetUp',))

    def test_a_description_of_a_local_key_no_keymap_has_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'descriptions of local keys no keymap has: Play'):
            self.build_with(local=LOCAL + ('Play',))

    def test_a_key_sent_with_nothing_oec_reads_needs_its_description(self):
        rows = KEYMAP_ROWS + [{'chord': ['Shift'], 'key': 'ScrLk', 'label': 'Copy/Play/Test', 'code': 10,
                               'modifiers': 'Shift', 'reads': [], 'local': None, 'rule': False,
                               'sends': 'Shift+Copy/Play/Test'}]
        with self.assertRaisesRegex(BuildError, 'keys with no description: Shift\\+Copy/Play/Test'):
            self.build_with(keymaps=({**KEYMAP, 'rows': rows},), ignores=('RESET', 'Shift+Copy/Play/Test'))
        self.build_with({**FUNCTIONS, 'Shift+Copy/Play/Test': False}, keymaps=({**KEYMAP, 'rows': rows},),
                        ignores=('RESET', 'Shift+Copy/Play/Test'),
                        extra='#assert.eq(keys-for-rows(km, "Shift+Copy/Play/Test").map(r => r.key), ("ScrLk",))\n')

    def test_a_row_with_no_reading_builds(self):
        extra = '#assert.eq(km.rows.filter(r => r.reads == () and r.local == none).len(), 1)\n'
        self.build_with(extra=extra)

    def test_keys_that_are_typst_syntax_build_as_typed(self):
        names = ['\\', '#', '*', '[', ']', '_', '$', '"', '`', '<', '@']
        rows = KEYMAP_ROWS + [{'chord': [], 'key': k, 'label': k, 'code': 1, 'modifiers': 'kept', 'reads': [k],
                               'local': None, 'rule': False} for k in names]
        extra = '''#let plain(c) = if type(c) == str { c } else if c.has("text") { c.text } else if c.has("children") {
  c.children.map(plain).join() } else if c.has("body") { plain(c.body) } else if c.has("child") {
  plain(c.child) } else { "" }
#for r in km.rows.slice(KNOWN) { assert.eq(plain(chord(r)), r.key) }
'''.replace('KNOWN', str(len(KEYMAP_ROWS)))
        self.build_with(keymaps=({**KEYMAP, 'rows': rows},), extra=extra)

    def test_a_second_keymaps_keys_are_checked_too(self):
        second = {**KEYMAP, 'name': 'uk', 'title': 'UK', 'rows': KEYMAP_ROWS + [
            {'chord': ['Alt'], 'key': '3', 'label': 'Jump/PA3', 'code': 111, 'modifiers': 'none', 'reads': ['JUMP'],
             'local': None, 'rule': False}]}
        with self.assertRaisesRegex(BuildError, 'keys with no description: JUMP'):
            self.build_with(keymaps=(KEYMAP, second))

    def test_a_key_only_another_keymap_gives_leaves_the_default_tables_whole(self):
        # Chapter 4 sets the default keymap's tables: a key a second keymap adds is described, not set there.
        second = {**KEYMAP, 'name': 'uk', 'title': 'UK', 'rows': KEYMAP_ROWS + [
            {'chord': ['Alt'], 'key': '3', 'label': 'Jump/PA3', 'code': 111, 'modifiers': 'none', 'reads': ['JUMP'],
             'local': None, 'rule': False}]}
        self.build_with({**FUNCTIONS, 'JUMP': (False, 'move')}, keymaps=(KEYMAP, second),
                        ignores=('RESET', 'JUMP'), extra='#function-table(km, functions, "move")\n')

    def test_a_key_in_no_group_chapter_4_knows_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, r'keys in no group Chapter 4 sets: PA1 \(sned\)'):
            self.build_with({**FUNCTIONS, 'PA1': (True, 'sned')})

    def test_keys_show_by_the_names_on_a_pc_keyboard(self):
        # The firmware's USB names, Left GUI and Non-US #, aren't what a PC keyboard's keys say (#143's review).
        rows = KEYMAP_ROWS + [
            {'chord': [], 'key': 'Left GUI', 'label': None, 'code': None, 'modifiers': None, 'reads': [],
             'local': None, 'rule': False},
            {'chord': ['Alt'], 'key': '\\', 'label': '\\|', 'code': 91, 'modifiers': 'Shift',
             'reads': ['BROKEN_BAR'], 'local': None, 'rule': False},
            {'chord': ['Alt'], 'key': 'Non-US #', 'label': '\\|', 'code': 91, 'modifiers': 'Shift',
             'reads': ['BROKEN_BAR'], 'local': None, 'rule': False}]
        extra = '''#import "/docs/manual/style.typ": plain-text
#assert.eq(plain-text(chord(km.rows.find(r => r.key == "Left GUI"))), "Left Windows")
#assert.eq(shown-rows(km, "BROKEN_BAR").map(r => r.key), ("\\\\",))
'''
        self.build_with({**FUNCTIONS, 'BROKEN_BAR': True}, keymaps=({**KEYMAP, 'rows': rows},), extra=extra)

    def test_an_overlay_names_its_base_by_its_title(self):
        overlay = {**KEYMAP, 'name': 'uk', 'title': 'UK', 'base': 'us104', 'devices': ['04d9:0006']}
        extra = '''#import "/docs/manual/style.typ": plain-text
#assert.eq(plain-text(keymap-about(keymaps.at(1))).trim(),
  "Chosen for the keyboards with USB IDs 04d9:0006. An overlay on US 104-key (ANSI).")
#assert.eq(plain-text(keymap-about(keymaps.at(0))).trim(), "Chosen for any keyboard that no other keymap claims.")
'''
        self.build_with(keymaps=(KEYMAP, overlay), extra=extra)

    def test_keys_for_a_key_no_keymap_gives_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'no key in us104 gives PF13'):
            self.build_with(extra='#keys-for(km, "PF13")\n')

    def test_keys_for_finds_every_chord_and_local_keys_too(self):
        extra = '''#assert.eq(keys-for-rows(km, "PA1").map(r => r.key), ("1",))
#assert.eq(keys-for-rows(km, "Rule").map(r => r.key), ("Home",))
'''
        self.build_with(extra=extra)


# A book's pages numbered from 1, for the index's tests.
INDEX_DOC = '''#import "/docs/manual/style.typ": *
#show: book
#set page(numbering: "1")
#counter(page).update(1)
'''
# The index's groups, as index-groups makes them from the document's markers.
GROUPS = 'index-groups(index-marks())'


class TestIndex(Docs):

    def test_a_marker_takes_no_room(self):
        # A marker beside a word must not push the full stop after it away, as a space would (Chapter 1's first draft
        # did, by 3 pt). It splits the run, so the word and the stop lose their kerning: a quarter of a point.
        self.compile(INDEX_DOC + '#context assert(calc.abs(measure[CUT mode#ix[CUT].].width - measure[CUT mode.].width)'
                     ' < 0.5pt)\n')

    def test_the_index_sorts_and_groups_without_regard_to_case(self):
        self.compile(INDEX_DOC + f'''Text #ix[rule line] #ix[Auto dim] #ix[3174] #ix[†] #ix[alarm]
#context {{
  let groups = {GROUPS}
  assert.eq(groups.map(g => g.title), ("Special characters", "Numerics", "A", "R"))
  assert.eq(groups.at(2).entries.map(e => e.term), ("alarm", "Auto dim"))
}}
''')

    def test_a_terms_pages_are_merged_in_order(self):
        self.compile(INDEX_DOC + f'''#ix[SetUp] Text #ix[SetUp]
#pagebreak()
#pagebreak()
More #ix[SetUp]
#context assert.eq({GROUPS}.first().entries.first().pages.map(p => p.page), ("1", "3"))
''')

    def test_an_index_page_reads_as_its_footer_does(self):
        # The front matter is numbered in roman numerals, the chapters from 1.
        self.compile(f'''#import "/docs/manual/style.typ": *
#show: book
#counter(page).update(2)
Front #ix[SetUp]
#pagebreak()
#set page(numbering: "1")
#counter(page).update(1)
Body #ix[SetUp]
#context assert.eq({GROUPS}.first().entries.first().pages.map(p => p.page), ("ii", "1"))
''')

    def test_a_sub_entry_sits_under_its_term(self):
        self.compile(INDEX_DOC + f'''Text #ix("alarm", sub: "volume") #ix[alarm]
#context {{
  let entries = {GROUPS}.first().entries
  assert.eq(entries.map(e => e.term), ("alarm",))
  assert.eq(entries.first().pages.map(p => p.page), ("1",))
  assert.eq(entries.first().subs.map(s => (s.term, s.pages.map(p => p.page))), (("volume", ("1",)),))
}}
''')

    def test_an_entry_reads_term_then_pages(self):
        # The first index printed its own code where the pages go (PR 3's first build).
        self.compile(INDEX_DOC + r'''#let pages = ((page: "3", loc: none), (page: "vii", loc: none))
#assert.eq(plain-text(index-line("alarm", none, pages)), "alarm\u{2002}3, vii")
#assert.eq(plain-text(index-line("Rule key", "rule line", ())), "Rule key, see rule line")
#assert.eq(plain-text(index-line("characters", none, ())), "characters")
''')

    def test_a_see_with_no_entry_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'index sees a term with no entry: Rule key -> rule line'):
            self.compile(INDEX_DOC + 'Text #ix("Rule key", see: "rule line")\n#book-index()\n')

    def test_terms_that_differ_only_in_case_stop_the_build(self):
        with self.assertRaisesRegex(BuildError, 'index terms that differ only in case: SetUp, setup'):
            self.compile(INDEX_DOC + 'Text #ix[setup] #ix[SetUp]\n#book-index()\n')

    def test_a_seen_term_with_pages_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'index terms with both a see and pages: Rule key'):
            self.compile(INDEX_DOC + 'Text #ix("Rule key", see: "rule line") #ix[rule line] #ix[Rule key]\n'
                         '#book-index()\n')

    def test_a_marker_with_both_a_sub_entry_and_a_see_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'index markers with both a sub-entry and a see: alarm, volume -> sound'):
            self.compile(INDEX_DOC + 'Text #ix("alarm", sub: "volume", see: "sound") #ix[sound]\n#book-index()\n')

    def test_a_term_that_sees_two_terms_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'index terms that see more than one term: Rule key -> rule line, ruler'):
            self.compile(INDEX_DOC + 'Text #ix("Rule key", see: "rule line") #ix("Rule key", see: "ruler")\n'
                         '#ix[rule line] #ix[ruler]\n#book-index()\n')

    def test_sub_entries_that_differ_only_in_case_stop_the_build(self):
        with self.assertRaisesRegex(BuildError, 'index sub-entries that differ only in case: alarm: Volume, volume'):
            self.compile(INDEX_DOC + 'Text #ix("alarm", sub: "volume") #ix("alarm", sub: "Volume")\n#book-index()\n')

    def test_an_empty_term_stops_the_build(self):
        for marker in ('#ix[]', '#ix("")', '#ix(" ")', '#ix("alarm", sub: "")'):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(BuildError, 'index markers with an empty term or sub-entry, on page 1'):
                    self.compile(INDEX_DOC + f'Text #ix[alarm] {marker}\n#book-index()\n')

    def test_a_marker_on_an_unnumbered_page_cant_clash_with_an_arabic_one(self):
        # A page with no number of its own reads in roman numerals, as the front matter does, not as its place in
        # the book: page 1 there and the chapters' page 1 are two pages.
        self.compile(f'''#import "/docs/manual/style.typ": *
#show: book
#set page(numbering: none)
Cover #ix[SetUp]
#pagebreak()
#set page(numbering: "1")
#counter(page).update(1)
Body #ix[SetUp]
#context assert.eq({GROUPS}.first().entries.first().pages.map(p => p.page), ("i", "1"))
''')

    def test_a_content_terms_quotes_are_typographic(self):
        # A string term is set as typed, so it is written with ’; a content term's quotes are Typst's smart quotes,
        # which plain-text keeps straight for the on-screen check.
        self.compile(INDEX_DOC + '''Text #ix[keyboard's keys] #ix["Clear" key] #ix("alarm", sub: [host's])
#context {
  let marks = index-marks()
  assert.eq(marks.map(m => m.term), ("keyboard’s keys", "“Clear” key", "alarm"))
  assert.eq(marks.last().sub, "host’s")
}
#book-index()
''')

    def test_the_index_builds_on_both_papers(self):
        doc = INDEX_DOC + '''Text #ix[alarm] #ix("alarm", sub: "volume") #ix[3174] #ix("Rule key", see: "rule line")
#ix[rule line]
#pagebreak()
More #ix[alarm]
#unnumbered([Index])
#book-index()
'''
        path = os.path.join(self.dir.name, 'doc.typ')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(doc)
        for paper in ('us-letter', 'a4'):
            typst_run.compile_pdf(path, os.path.join(self.dir.name, f'{paper}.pdf'), {'paper': paper}, WHEN)

    def test_a_glossary_expansion_marked_with_pages_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, 'index terms with both a see and pages: operator information area'):
            self.compile(INDEX_DOC + '''#glossary(("OIA": (expands: "operator information area", body: [The status line.]),))
Text #ix[operator information area]
#book-index()
''')

    def test_an_index_term_is_set_as_typed(self):
        self.compile(INDEX_DOC + r'''Text #ix("*") #ix("#") #ix("\\") #ix("F3=Exit")
#context {
  let groups = index-groups(index-marks())
  assert.eq(groups.map(g => (g.title, g.entries.map(e => e.term))),
    (("Special characters", ("#", "*", "\\")), ("F", ("F3=Exit",))))
}
#book-index()
''')


class TestGlossary(Docs):

    def test_the_glossary_sorts_and_marks_its_terms(self):
        self.compile(INDEX_DOC + '''#glossary((
  "OIA": (body: [The status line.]),
  "CUT": (expands: "control unit terminal", body: [A display station the controller runs.]),
  "alarm": (body: [A tone.]),
))
#context {
  let marks = query(<ix>).map(m => m.value)
  assert.eq(marks.map(m => m.term), ("alarm", "CUT", "control unit terminal", "OIA"))
  assert.eq(marks.at(2).see, "CUT")
}
''')

    def test_a_see_also_with_no_entry_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, "glossary sees a term it doesn't define: DFT"):
            self.compile(INDEX_DOC + '#glossary(("CUT": (body: [A mode.], also: ("DFT",)),))\n')



class TestToConfirm(Docs):
    """An open fact shows in a draft, and stops a published edition."""

    DOC = '#import "/docs/manual/style.typ": *\n#to-confirm[The current it draws.]\n'

    def build_as(self, draft):
        path = os.path.join(self.dir.name, 'doc.typ')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(self.DOC)
        typst_run.compile_pdf(path, os.path.join(self.dir.name, 'doc.pdf'),
                              {'build': self.build_dir, 'draft': draft}, WHEN)

    def test_a_draft_shows_it(self):
        self.build_as('true')
        self.assertTrue(os.path.getsize(os.path.join(self.dir.name, 'doc.pdf')))

    def test_a_published_edition_stops_at_it(self):
        with self.assertRaisesRegex(BuildError, "can't carry a To confirm item"):
            self.build_as('false')


if __name__ == '__main__':
    unittest.main()
