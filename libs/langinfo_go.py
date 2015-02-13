
"""LangInfo definition for "Go" language."""

from langinfo import LangInfo

lang = "Go"
import styles
if not lang in styles.StateMap:
    map = styles.StateMap['C++'].copy()
    styles.addSharedStyles(map)
    styles.StateMap[lang] = map


class GoLangInfo(LangInfo):
    """http://golang.org"""
    name = lang
    conforms_to_bases = ["Text"]
    exts = [".go"]
    # From http://golang.org/ref/spec#Keywords
    reserved_keywords = set("""
        break        default      func         interface    select
        case         defer        go           map          struct
        chan         else         goto         package      switch
        const        fallthrough  if           range        type
        continue     for          import       return       var
    """.split())
    # From http://golang.org/ref/spec#Predeclared_identifiers
    predeclared_identifiers = set("""
        bool byte complex64 complex128 error float32 float64
        int int8 int16 int32 int64 rune string
        uint uint8 uint16 uint32 uint64 uintptr

        true false iota nil""".split())
    predeclared_functions = set("""
        append cap close complex copy delete imag len
        make new panic print println real recover
        """.split())
    default_encoding = "utf-8"
