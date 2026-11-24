// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

// The Liz4270 Display Station User's Guide (#136). Built by tools/manual/build.py, which draws the screens
// and walks SetUp first.

#import "style.typ": *

#show: book

#cover()
#counter(page).update(2)
#edition-notice()

#unnumbered([Contents], outlined: false)
#outline(title: none, depth: 2)

#unnumbered([Figures])
#outline(title: none, target: figure.where(kind: image))

#unnumbered([Tables])
#outline(title: none, target: figure.where(kind: table))

#unnumbered([About this book])

This book is for anyone who has a Liz4270 display station and wants to attach it to a 3270 controller and
use it. It says how to set it up, what the screen and the keyboard do, and every setting SetUp offers.

Liz4270 behaves as an IBM 3483-V display station does in CUT mode, so a reader who knows the 3483-V will
find most of it familiar. Where Liz4270 differs, this book says so.

The glossary defines the 3270 terms this book uses, and the index finds a subject by its page.

=== How this book shows things

- Keys are shown as they're labelled: #key("Enter"), and #keys("Shift", "Alt", "X") for keys held down
  together.
- Text on the display station's screen is shown as it looks there: #on-screen[F3=Exit].
- Every screen in this book was drawn by the display station's own firmware, the version on the cover.

#note[A note adds something worth knowing.]

#attention[An attention notice warns of something that can't be undone, such as ending the host's
sessions.]

#pagebreak(to: "odd", weak: true)
#set page(numbering: "1")
#counter(page).update(1)

#include "chapters/01-introducing.typ"
#include "chapters/02-setting-up.typ"
#include "chapters/03-screen.typ"
#include "chapters/04-keyboard.typ"
#include "chapters/05-setup.typ"
#include "chapters/06-sound.typ"
#include "chapters/07-updating.typ"
#include "chapters/08-problems.typ"

#show: appendix
#include "chapters/appendix-a-keymaps.typ"

#include "chapters/glossary.typ"

#unnumbered([Index]) <index>
#book-index()

#unnumbered([Readers' comments])

If something in this book is wrong, unclear or missing, please say so. Open an issue at
#raw("github.com/quaint-systems/Liz4270Terminal/issues"), and give the form number from the cover, the page, and
what you found.
