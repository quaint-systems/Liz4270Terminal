// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

// The user manual's template (#136): an homage to a 1990s IBM publication, in IBM Plex.
// docs/superpowers/specs/2026-10-14-user-manual-design.md, "The look", has the numbers and why.

// ---- What tools/manual/build.py passes in ----

#let meta = (
  paper: sys.inputs.at("paper", default: "us-letter"),
  version: sys.inputs.at("version", default: "0.0.0"),
  commit: sys.inputs.at("commit", default: "unknown"),
  date: sys.inputs.at("date", default: "an unknown date"),
  draft: sys.inputs.at("draft", default: "true") == "true",
  form: sys.inputs.at("form", default: "LZ01-4270-XX"),
  edition-name: sys.inputs.at("edition-name", default: ""),
  firmware: sys.inputs.at("firmware", default: ""),
  build: sys.inputs.at("build", default: "/build/manual"),
)
#assert(meta.paper in ("us-letter", "a4"), message: "paper must be us-letter or a4")

#let product = "Liz4270 Display Station"
#let book-title = "User’s Guide"
#let cover-line = "3270 COMPATIBLE INFORMATION DISPLAY SYSTEM"

// ---- Fonts: Plex names its middle weights as families of their own ----

#let serif = "IBM Plex Serif"
#let sans = "IBM Plex Sans"
#let sans-md = "IBM Plex Sans Medm"
#let sans-sb = "IBM Plex Sans SmBld"
#let mono = "IBM Plex Mono"
#let terminal = "IBM 3270"

// ---- The page: one text area on both papers, so they break pages alike ----

#let hang = 1.35in // the body's indent; headings, footers and the cover start at the text area's edge
#let area-w = 6.5in
#let area-h = 9.0in
#let page-w = if meta.paper == "a4" { 210mm } else { 8.5in }
#let page-h = if meta.paper == "a4" { 297mm } else { 11in }
#let side = (page-w - area-w) / 2
#let top-m = (page-h - area-h) / 2 - 0.15in
#let bottom-m = page-h - area-h - top-m

// ---- Markers for build.py's check that both papers paginate alike ----

// The height is the marker's on its page, for the check that no figure floats above its own heading.
#let placed(what) = context [#metadata((what: what, page: here().page(), y: here().position().y.pt())) <placed>]

// ---- Pieces for the chapters ----

#let key(k) = box(
  inset: (x: 3.5pt, y: 0pt), outset: (y: 2.5pt), radius: 2pt,
  stroke: 0.6pt + luma(35%), fill: luma(95%),
  text(font: sans-md, size: 0.82em, k),
)

// A chord, kept on one line: #keys("Shift", "Alt", "X").
#let keys(..ks) = box(ks.pos().map(key).join(h(1.5pt) + text(font: sans, size: 0.85em)[+] + h(1.5pt)))

#let note(body, label: "Note:") = block(above: 1.1em, below: 1.1em,
  grid(columns: (auto, 1fr), column-gutter: 0.45em, text(font: sans-sb)[#label], body))

#let attention(body) = block(above: 1.2em, below: 1.2em, width: 100%,
  inset: (x: 8pt, y: 7pt), stroke: (left: 2.5pt + black),
  [#text(font: sans-sb)[Attention:] #body])

// A name printed on the case, over a connector or a light, as the reader finds it there.
#let on-case(t) = box(text(font: sans-sb, size: 0.88em, t))

// An open fact in a draft: something still to be measured, tried or decided, shown so the draft's reader sees
// what the book doesn't yet know. A published edition can carry none, so a release build stops at the first.
#let to-confirm(body) = {
  assert(meta.draft, message: "a published edition can't carry a To confirm item; settle it and take it out")
  block(above: 1.1em, below: 1.1em, width: 100%, inset: (x: 8pt, y: 7pt),
    stroke: (paint: black, thickness: 0.75pt, dash: "dashed"),
    [#text(font: sans-sb)[To confirm:] #body])
}

// The characters 3270font's subset in tools/sim/fonts/ can draw, from its covered.txt (a code point in hex on each
// line). Typst would set any other in another font, or as nothing, and say nothing.
#let hex-value(h) = h.clusters().fold(0, (n, c) => n * 16 + "0123456789ABCDEF".position(upper(c)))
#let terminal-covered = (read("/tools/sim/fonts/covered.txt").split("\n").filter(h => h.trim() != "")
  .map(h => str.from-unicode(hex-value(h.trim()))))

// Content's plain text, for checking it. A quote in markup is a smartquote of its own, given as quotes says:
// (double, single), straight unless the caller asks.
#let plain-text(c, quotes: ("\"", "'")) = if type(c) == str { c } else if c.func() == smartquote {
  if c.double { quotes.first() } else { quotes.last() } } else if c.has("text") { c.text } else if c.has(
  "children") { c.children.map(x => plain-text(x, quotes: quotes)).join() } else if c.has("body") {
  plain-text(c.body, quotes: quotes) } else if c.has("child") { plain-text(c.child, quotes: quotes) } else { " " }

// The terminal's own text, such as F3=Exit, with its quotes straight as the terminal draws them. The build
// stops on a character the font can't draw.
#let on-screen(t) = {
  let missing = plain-text(t).clusters().filter(c => c.trim() != "" and c not in terminal-covered).dedup()
  if missing.len() > 0 { panic("3270font's subset has no " + missing.join(" ") + " for on-screen text") }
  set smartquote(enabled: false)
  text(font: terminal, size: 1.05em, t)
}

// A screen build.py drew through the firmware's renderer: build/manual/screens/NAME-640.png.
#let screen-image(name, width: 4.8in) = box(stroke: 0.5pt + black,
  image(meta.build + "/screens/" + name + "-640.png", width: width, scaling: "pixelated"))

// A few of a screen's cells, such as a status-line symbol, cut from one build.py drew: twice a screen
// figure's scale, 0.12 in a cell.
#let cells-image(name, cells) = box(stroke: 0.5pt + black,
  image(meta.build + "/screens/" + name + "-640.png", width: cells * 0.12in, scaling: "pixelated"))

// LIZ, as firmware/core/splash.c draws it: 8 units a column, 19 a row, 11 of each row striped.
#let logo-rows = (
  "#####           #########  #################",
  "#####           #########  #################",
  "#####             #####                #####",
  "#####             #####            #####",
  "#####             #####        #####",
  "#####             #####    #####",
  "##############  #########  #################",
  "##############  #########  #################",
)
#let liz-logo(width: 2.4in) = {
  let u = width / 352
  box(width: width, height: 144 * u, {
    for (r, row) in logo-rows.enumerate() {
      let cells = row.clusters()
      let c = 0
      while c < cells.len() {
        if cells.at(c) == "#" {
          let s = c
          while c < cells.len() and cells.at(c) == "#" { c += 1 }
          place(dx: s * 8 * u, dy: r * 19 * u, rect(width: (c - s) * 8 * u, height: 11 * u, fill: black))
        } else { c += 1 }
      }
    }
  })
}

// ---- The index and the glossary: the template's own, since a package would download at compile time ----

// A term as the index sets it. A string is set as typed, so it is written with ’. Content's quotes are made
// typographic, as Typst sets them in the text: opening at the start or after a space or a bracket, closing (an
// apostrophe among them) anywhere else. Empty content is an empty term.
#let index-text(t) = if t == none or type(t) == str { t } else {
  let open(s, mark, quote) = s.replace(regex("(^|[\s(\[])" + mark), m => m.captures.first() + quote)
  let s = plain-text(t, quotes: ("\u{E001}", "\u{E000}"))
  if s == none { "" } else {
    open(open(s, "\u{E001}", "“"), "\u{E000}", "‘").replace("\u{E001}", "”").replace("\u{E000}", "’") }
}

// An index marker, printing nothing, beside the words it indexes: #ix[auto dim], #ix("alarm", sub: "volume"),
// #ix("Rule key", see: "rule line"). Never in a heading or a caption, which the contents, the lists and the
// footers repeat: each copy would index its own page (test_typography.py refuses one).
#let ix(term, sub: none, see: none) = [#metadata((term: index-text(term), sub: index-text(sub),
  see: index-text(see)))<ix>]

// Sorting without regard to case, then by case, so SetUp and setup would sit together.
#let index-key(term) = lower(term) + "\u{0}" + term

// A term's group, IBM's way: Special characters, then Numerics, then its letter.
#let index-group(term) = {
  let first = term.clusters().first()
  if first.match(regex("^\p{L}")) != none { upper(first) } else if first.match(regex("^\p{Nd}")) != none {
    "Numerics" } else { "Special characters" }
}

// Each page once, by its sheet, in the order the book reaches it.
#let index-pages(marks) = marks.fold((), (pages, m) => if pages.any(p => p.sheet == m.sheet) { pages } else {
  pages + ((page: m.page, sheet: m.sheet, loc: m.loc),) })

// Every marker in the book, with its page as the footer numbers it and its sheet, the page's place in the book.
// A page with no numbering of its own reads in roman numerals, as the front matter does, so it can't read as a
// chapter's page. Contextual.
#let index-marks() = query(<ix>).map(m => {
  let loc = m.location()
  let style = loc.page-numbering()
  (..m.value, page: numbering(if style == none { "i" } else { style }, ..counter(page).at(loc)),
    sheet: loc.page(), loc: loc)
})

// The index from the markers: its groups in IBM's order, each entry's pages merged, its sub-entries under it.
// The build stops on an empty term or sub-entry, a marker with both a sub-entry and a see, a see with no entry,
// terms or a term's sub-entries that differ only in case, a term that sees two, or a term both seen and given
// pages.
#let index-groups(marks) = {
  let empty = marks.filter(m => m.term == none or m.term.trim() == "" or (m.sub != none and m.sub.trim() == ""))
  if empty.len() > 0 {
    panic("index markers with an empty term or sub-entry, on page " + empty.map(m => m.page).dedup().join(", "))
  }
  let both = marks.filter(m => m.sub != none and m.see != none)
  if both.len() > 0 {
    panic("index markers with both a sub-entry and a see: "
      + both.map(m => m.term + ", " + m.sub + " -> " + m.see).dedup().join("; "))
  }
  let terms = marks.map(m => m.term).dedup().sorted(key: index-key)
  let twins = terms.filter(t => terms.filter(o => lower(o) == lower(t)).len() > 1)
  if twins.len() > 0 { panic("index terms that differ only in case: " + twins.join(", ")) }
  let astray = marks.filter(m => m.see != none and m.see not in terms)
  if astray.len() > 0 {
    panic("index sees a term with no entry: " + astray.map(m => m.term + " -> " + m.see).dedup().join(", "))
  }
  let entries = terms.map(term => {
    let own = marks.filter(m => m.term == term)
    let sees = own.filter(m => m.see != none).map(m => m.see).dedup()
    if sees.len() > 1 { panic("index terms that see more than one term: " + term + " -> " + sees.join(", ")) }
    let bare = own.filter(m => m.see == none and m.sub == none)
    let subs = own.filter(m => m.see == none and m.sub != none).map(m => m.sub).dedup().sorted(key: index-key)
    let twins = subs.filter(s => subs.filter(o => lower(o) == lower(s)).len() > 1)
    if twins.len() > 0 { panic("index sub-entries that differ only in case: " + term + ": " + twins.join(", ")) }
    if sees.len() > 0 and bare.len() + subs.len() > 0 { panic("index terms with both a see and pages: " + term) }
    (term: term, see: sees.at(0, default: none), pages: index-pages(bare),
      subs: subs.map(s => (term: s, pages: index-pages(own.filter(m => m.sub == s)))))
  })
  let titles = entries.map(e => index-group(e.term)).dedup()
  let order = ("Special characters", "Numerics")
  let titles = order.filter(t => t in titles) + titles.filter(t => t not in order).sorted()
  titles.map(title => (title: title, entries: entries.filter(e => index-group(e.term) == title)))
}

// One line of the index: the term, an en space and its pages, each linked to its marker; or the term and what it
// sees. The term is a string, so it is set as typed.
#let index-line(term, see, pages) = if see != none [#term, #emph[see] #see] else if pages.len() == 0 [#term] else {
  [#term#"\u{2002}"]
  pages.map(p => if p.loc == none { p.page } else { link(p.loc, p.page) }).join(", ")
}

// The index, set in two columns across the text area, hang and all.
#let book-index() = context {
  pad(left: -hang, columns(2, gutter: 0.35in, {
    set text(size: 10.5pt)
    set par(hanging-indent: 1em, leading: 0.5em, spacing: 0.45em)
    for group in index-groups(index-marks()) {
      block(sticky: true, above: 1.3em, below: 0.6em, text(font: sans-sb, size: 12.5pt, group.title))
      for e in group.entries {
        par(index-line(e.term, e.see, e.pages))
        for s in e.subs { pad(left: 1em, par(index-line(s.term, none, s.pages))) }
      }
    }
  }))
}

// The glossary, from a dictionary: "CUT": (expands: "control unit terminal", body: [...], also: ("DFT",)), the
// last two optional. Sorted here, so the source can list them in any order. Each term is marked in the index,
// and an expansion sees its term there: "control unit terminal, see CUT".
#let glossary(entries) = {
  let unknown = entries.values().map(e => e.at("also", default: ())).flatten().filter(t => t not in entries)
  if unknown.len() > 0 { panic("glossary sees a term it doesn't define: " + unknown.dedup().join(", ")) }
  for term in entries.keys().sorted(key: index-key) {
    let entry = entries.at(term)
    let expands = entry.at("expands", default: none)
    let also = entry.at("also", default: ())
    block(above: 1em, below: 1em, par(hanging-indent: 1em, {
      text(font: sans-sb, term)
      ix(term)
      if expands != none { [ (#expands)]; ix(expands, see: term) }
      [. ]
      entry.body
      if also.len() > 0 [ See also #also.join(", ", last: " and ").]
    }))
  }
}

// ---- The front matter's fixed pages ----

#let cover() = page(margin: (x: side, top: top-m, bottom: bottom-m), footer: none, {
  set text(font: sans)
  grid(columns: (1fr, auto),
    text(size: 10pt, tracking: 0.04em, cover-line),
    align(right, {
      text(font: sans-sb, size: 12pt)[#meta.form#if meta.draft [ (#meta.commit)]]
      if meta.draft { linebreak(); text(size: 10pt, meta.date) }
    }))
  v(2.1in)
  line(length: 100%, stroke: 2pt)
  v(0.18in)
  text(size: 32pt, weight: "bold", product)
  v(-0.12in)
  text(size: 32pt, weight: "light", book-title)
  v(0.25in)
  text(size: 12pt)[For firmware version #meta.version]
  v(1fr)
  align(right, liz-logo())
})

#let edition-notice() = page(
  footer: context pad(left: -hang, text(font: sans-sb, size: 10.5pt, counter(page).display())), {
  v(1fr)
  set par(spacing: 0.85em)
  if meta.draft {
    text(font: sans-sb, size: 11pt)[Draft of #meta.date (#meta.commit)]
    parbreak()
    [This is a draft, not a published edition. A published edition is numbered on the cover, in place of
    the draft's XX. This draft describes version #meta.version of the Liz4270 firmware.]
  } else {
    text(font: sans-sb, size: 11pt, meta.edition-name)
    parbreak()
    [This edition applies to version #meta.firmware of the Liz4270 firmware, and to later versions until a
    new edition says otherwise.]
  }
  parbreak()
  [SetUp's About page shows the version a display station runs (see @about).]
  parbreak()
  [The latest edition is published beside each firmware release, at
  #raw("github.com/quaint-systems/Liz4270Terminal/releases").]
  parbreak()
  [*Readers' comments.* If something in this book is wrong or unclear, open an issue at
  #raw("github.com/quaint-systems/Liz4270Terminal/issues").]
  parbreak()
  [Liz4270 is an independent project. It is not made, sold or supported by IBM. IBM is a trademark of
  International Business Machines Corporation. Other names may be trademarks of their owners.]
  v(0.6em)
  line(length: 100%, stroke: 0.5pt)
  text(size: 10pt)[© Copyright CoffeeMuse 2026. Licensed under CC BY 4.0, the Creative Commons Attribution
  4.0 International License. \ Typeset with Typst in IBM Plex and 3270font, from commit #raw(meta.commit).]
})

// An unnumbered title in the front or back matter, set like a chapter's.
#let unnumbered(title, outlined: true) = heading(level: 1, numbering: none, outlined: outlined, title)

// ---- Chapters, and appendices after #show: appendix ----

#let in-appendix = state("appendix", false)

// What a numbered chapter or appendix is called: "Chapter 5", "Appendix A".
#let chapter-label(el) = {
  let number = numbering(el.numbering, ..counter(heading).at(el.location()))
  (if in-appendix.at(el.location()) { "Appendix " } else { "Chapter " }) + number
}

// A figure's or a table's label: "Figure 5-1", "Table A-1".
#let figure-label(it) = (if it.kind == table { "Table " } else { "Figure " }) + numbering(it.numbering,
  ..it.counter.at(it.location()))

// The back matter's appendices: from here on, a level-1 heading is lettered, "Appendix A. Keymaps", and its
// figures and tables are numbered "A-1".
#let appendix(body) = {
  set heading(numbering: (..n) => if n.pos().len() == 1 { numbering("A", ..n) })
  in-appendix.update(true)
  counter(heading).update(0)
  body
}

// ---- The book ----

#let footer = context {
  let here-page = here().page()
  let opening = query(heading.where(level: 1)).any(h => h.location().page() == here-page)
  let chapters = query(selector(heading.where(level: 1)).before(here()))
  set text(font: sans, size: 10pt)
  let num = text(font: sans-sb, size: 10.5pt, counter(page).display())
  // The footer spans the whole text area, hang and all, so a page number sits as far from the
  // outer edge on a left-hand page as on a right-hand one.
  pad(left: -hang, if opening {
    grid(columns: (1fr, auto), align: (left, right), [© Copyright CoffeeMuse 2026], num)
  } else if calc.even(counter(page).get().first()) {
    [#num #h(1.2em) #product #book-title]
  } else {
    let title = if chapters.len() > 0 { chapters.last().body } else { [] }
    align(right)[#title #h(1.2em) #num]
  })
}

#let book(body) = {
  set document(title: product + " " + book-title, author: "CoffeeMuse")
  set text(font: serif, size: 12pt, lang: "en", region: "us", hyphenate: false)
  set par(justify: false, leading: 0.6em, spacing: 0.95em)
  // Typst's second-level marker, ‣, isn't in Plex Serif: a dash, as IBM's books had.
  set list(marker: ([•], [–]), indent: 0.6em, body-indent: 0.5em)
  set enum(indent: 0pt, body-indent: 0.6em)
  show raw: set text(font: mono, size: 0.95em)
  set page(paper: meta.paper, margin: (left: side + hang, right: side, top: top-m, bottom: bottom-m),
    footer: footer, footer-descent: 40%, numbering: "i")

  // Headings: chapters numbered, sections not.
  set heading(numbering: (..n) => if n.pos().len() == 1 { numbering("1", ..n) })
  show heading.where(level: 1): it => {
    pagebreak(to: "odd", weak: true)
    counter(figure.where(kind: image)).update(0)
    counter(figure.where(kind: table)).update(0)
    pad(left: -hang, block(width: 100%, below: 2.2em, {
      v(0.2in)
      line(length: 100%, stroke: 4pt)
      v(0.12in)
      set text(font: sans, weight: "bold", size: 26pt)
      if it.numbering != none [#chapter-label(it). ]
      it.body
    }))
    placed(if it.numbering != none { chapter-label(it) } else { "chapter" } + " " + repr(it.body))
  }
  show heading.where(level: 2): it => {
    pad(left: -hang, block(width: 100%, above: 1.8em, below: 0.9em, sticky: true, {
      line(length: 100%, stroke: 0.75pt)
      v(0.4em)
      text(font: sans-sb, size: 15pt, it.body)
    }))
    placed("section " + repr(it.body))
  }
  show heading.where(level: 3): it => {
    pad(left: -hang, block(above: 1.4em, below: 0.7em, sticky: true, text(font: sans-sb, size: 12.5pt, it.body)))
    placed("subsection " + repr(it.body))
  }

  // Figures and tables, numbered by chapter, framed between rules. A figure with a placement floats.
  set figure(numbering: (..n) => numbering(if in-appendix.get() { "A-1" } else { "1-1" },
    counter(heading).get().first(), ..n), gap: 0.6em)
  set figure.caption(separator: [. ])
  show figure.caption: it => align(left, text(font: sans, size: 10pt,
    [#text(font: sans-sb)[#it.supplement #context it.counter.display(it.numbering)#it.separator]#it.body]))
  show figure.where(kind: table): set figure.caption(position: top)
  show figure.where(kind: table): set block(breakable: true)
  show figure: it => {
    let top = it.kind == table
    // A table may run on to the next page, its header repeated; a figure stays whole.
    let framed = block(width: 100%, above: 1.4em, below: 1.4em, breakable: top, {
      // The rule and a table's caption stay with what follows them.
      block(sticky: true, below: 0pt, {
        line(length: 100%, stroke: 0.75pt)
        v(0.5em)
        if top { it.caption; v(0.4em) }
      })
      align(center, it.body)
      if not top and it.caption != none { v(0.5em); it.caption }
      v(0.5em)
      line(length: 100%, stroke: 0.75pt)
      // Inside, so a float is marked where it lands.
      placed(figure-label(it) + if it.caption != none { " " + repr(it.caption.body) })
    })
    if it.placement == none { framed } else { place(it.placement, float: true, clearance: 1.4em, framed) }
  }

  set table(stroke: none, inset: (x: 5pt, y: 4.5pt), align: left)
  show table: set text(size: 10.5pt)
  show table.cell.where(y: 0): set text(font: sans-sb, size: 10pt)

  // The contents and the lists of figures and tables: "Chapter 5. Using SetUp", "Figure 5-1. Password Set".
  set outline(indent: 1.5em)
  show outline.entry: it => {
    let el = it.element
    let prefix = if el.func() == heading and el.level == 1 and el.numbering != none {
      [#chapter-label(el). ]
    } else if el.func() == figure {
      [#it.prefix(). ]
    }
    let entry = link(el.location(), it.indented(none, [#prefix#it.inner()]))
    if it.level == 1 and el.func() == heading {
      v(0.7em, weak: true)
      text(font: sans-sb, entry)
    } else { entry }
  }

  // References: a chapter as "Chapter 5", an appendix as "Appendix A"; a section, which has no number, by its title and page, as
  // IBM's books did: "Locking the display station" on page 16.
  show ref: it => {
    let el = it.element
    if el == none or el.func() != heading { return it }
    let loc = el.location()
    if el.level == 1 and el.numbering != none {
      link(loc)[#chapter-label(el)]
    } else {
      link(loc)["#el.body" on page #numbering(loc.page-numbering(), ..counter(page).at(loc))]
    }
  }

  body
}
