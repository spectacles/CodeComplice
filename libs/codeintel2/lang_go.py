#!/usr/bin/env python

"""Go language support for codeintel."""

import os
import sys
import json
import logging
import process
import time

try:
    from zope.cachedescriptors.property import Lazy as LazyClassAttribute
except ImportError:
    import warnings
    warnings.warn("Unable to import zope.cachedescriptors.property")
    # Fallback to regular properties.
    LazyClassAttribute = property

import ciElementTree as ET
import which

import SilverCity
from SilverCity.Lexer import Lexer
from SilverCity import ScintillaConstants
from codeintel2.accessor import AccessorCache
from codeintel2.citadel import CitadelLangIntel, CitadelBuffer
from codeintel2.common import Trigger, TRG_FORM_CALLTIP, TRG_FORM_CPLN, TRG_FORM_DEFN, CILEDriver, Definition, CodeIntelError
from codeintel2.langintel import ParenStyleCalltipIntelMixin, ProgLangTriggerIntelMixin, PythonCITDLExtractorMixin
from codeintel2.udl import UDLBuffer
from codeintel2.tree import tree_from_cix
from SilverCity.ScintillaConstants import (
    SCE_C_COMMENT, SCE_C_COMMENTDOC, SCE_C_COMMENTDOCKEYWORD,
    SCE_C_COMMENTDOCKEYWORDERROR, SCE_C_COMMENTLINE,
    SCE_C_COMMENTLINEDOC, SCE_C_DEFAULT, SCE_C_IDENTIFIER, SCE_C_NUMBER,
    SCE_C_OPERATOR, SCE_C_STRING, SCE_C_CHARACTER, SCE_C_STRINGEOL, SCE_C_WORD)


try:
    from xpcom.server import UnwrapObject
    _xpcom_ = True
except ImportError:
    _xpcom_ = False


#---- globals

lang = "Go"
log = logging.getLogger("codeintel.go")
# log.setLevel(logging.DEBUG)

try:
    sys.path.append(os.path.dirname(__file__))
    from langinfo_go import GoLangInfo
except:
    class GoLangInfo:
        reserved_keywords = set([])
        predeclared_identifiers = set([])
        predeclared_functions = set([])
        default_encoding = "utf-8"
    import styles
    if not styles.StateMap.has_key(lang):
        map = styles.StateMap['C++'].copy()
        styles.addSharedStyles(map)
        styles.StateMap[lang] = map
finally:
    sys.path.pop()


#---- Lexer class

class GoLexer(Lexer):
    lang = lang
    def __init__(self):
        self._properties = SilverCity.PropertySet()
        self._lexer = SilverCity.find_lexer_module_by_id(ScintillaConstants.SCLEX_CPP)
        self._keyword_lists = [
            SilverCity.WordList(' '.join(sorted(GoLangInfo.reserved_keywords))),
            SilverCity.WordList(' '.join(
                            sorted(GoLangInfo.predeclared_identifiers.
                                   union(GoLangInfo.predeclared_functions)))),
        ]


#---- LangIntel class


class GoLangIntel(CitadelLangIntel,
                          ParenStyleCalltipIntelMixin,
                          ProgLangTriggerIntelMixin,
                          PythonCITDLExtractorMixin):
    lang = lang
    citdl_from_literal_type = {"string": "string"}
    calltip_trg_chars = tuple('(')
    trg_chars = tuple(' (."')

    completion_name_mapping = {
        'var': 'variable',
        'func': 'function',
        'package': 'module',
        'type': 'class',
        'const': 'constant',
    }

    def codeintel_type_from_completion_data(self, completion_entry):
        """Given a dictionary containing 'class' and 'type' keys return a
        codeintel type. Used for selecting icon in completion list.
        """
        completion_type = self.completion_name_mapping.get(completion_entry['class']) or completion_entry['class']
        if completion_entry['type'].startswith('[]'):
            completion_type = '@variable'
        elif completion_entry['type'].startswith('map['):
            completion_type = '%variable'
        return completion_type

    def trg_from_pos(self, buf, pos, implicit=True, lang=None, trigger_type="both"):
        log.debug("trg_from_pos(pos=%r)", pos)
        if pos < 2:
            return None
        accessor = buf.accessor
        last_pos = pos - 1
        last_char = accessor.char_at_pos(last_pos)

        if last_char == '.': # must be "complete-object-members" or None
            log.debug("  triggered 'complete-object-members'")
            return Trigger(self.lang, TRG_FORM_CPLN,
                           "object-members", pos, implicit)
        elif last_char == '(':
            log.debug("  triggered 'calltip-call-signature'")
            return Trigger(self.lang, TRG_FORM_CALLTIP, "call-signature", pos, implicit)
        elif last_char in '\'"`' or last_char == "@":
            # Check if it's an import
            log.debug("  checking for import statement")
            ac = AccessorCache(accessor, pos, fetchsize=100)
            prev_style = accessor.style_at_pos(last_pos-1)
            if prev_style == SCE_C_STRING:
                # It's the end of a string then, not what we are looking for.
                return False

            # Bug in Komodo 8 - peek at the previous style to ensure the cache
            # is primed. No needed in Komodo 9 onwards.
            p, ch, style = ac.peekPrevPosCharStyle()
            log.debug("  p1 %r, ch %r, style %r", p, ch, style)

            loops_left = 100
            while loops_left:
                loops_left -= 1
                p, ch, style = ac.getPrecedingPosCharStyle(style)
                log.debug("  p %r, ch %r, style %r", p, ch, style)
                if p is None:
                    break
                if style == SCE_C_WORD:
                    p, text = ac.getTextBackWithStyle(style)
                    log.debug("    p %r, text %r", p, text)
                    if text == "import":
                        log.debug("  triggered 'complete-imports'")
                        return Trigger(self.lang, TRG_FORM_CPLN, "imports", pos, implicit)
                    break
                elif style not in (SCE_C_DEFAULT, SCE_C_OPERATOR, SCE_C_STRING,
                                   SCE_C_COMMENT, SCE_C_COMMENTDOC, SCE_C_COMMENTLINE):
                    break

        log.debug("  triggered 'complete-any'")
        return Trigger(self.lang, TRG_FORM_CPLN, "any", pos, implicit)

    def preceding_trg_from_pos(self, buf, pos, curr_pos, preceding_trg_terminators=None, trigger_type="both", DEBUG=False):
        #DEBUG = True
        if DEBUG:
            log.debug("pos: %d", pos)
            log.debug("ch: %r", buf.accessor.char_at_pos(pos))
            log.debug("curr_pos: %d", curr_pos)

        if pos != curr_pos and self._last_trg_type == "names":
            # The last trigger type was a 3-char trigger "names", we must try
            # triggering from the same point as before to get other available
            # trigger types defined at the same poisition or before.
            trg = ProgLangTriggerIntelMixin.preceding_trg_from_pos(
                    self, buf, pos+2, curr_pos, preceding_trg_terminators,
                    DEBUG=DEBUG)
        else:
            trg = ProgLangTriggerIntelMixin.preceding_trg_from_pos(
                    self, buf, pos, curr_pos, preceding_trg_terminators,
                    DEBUG=DEBUG)

        names_trigger = None
        style = None
        if pos > 0:
            accessor = buf.accessor
            if pos == curr_pos:
                # We actually care about whats left of the cursor.
                pos -= 1
            style = accessor.style_at_pos(pos)
            if DEBUG:
                style_names = buf.style_names_from_style_num(style)
                log.debug("  style: %s (%s)", style, ", ".join(style_names))
            if style in (1,2):
                ac = AccessorCache(accessor, pos)
                prev_pos, prev_ch, prev_style = ac.getPrecedingPosCharStyle(style)
                if prev_style is not None and (pos - prev_pos) > 3:
                    # We need at least 3 character for proper completion handling.
                    names_trigger = self.trg_from_pos(buf, prev_pos + 4, implicit=False)


        if DEBUG:
            log.debug("trg: %r", trg)
            log.debug("names_trigger: %r", names_trigger)
            log.debug("last_trg_type: %r", self._last_trg_type)

        if names_trigger:
            if not trg:
                trg = names_trigger
            # Two triggers, choose the best one.
            elif trg.pos == names_trigger.pos:
                if self._last_trg_type != "names":
                    # The names trigger gets priority over the other trigger
                    # types, unless the previous trigger was also a names trg.
                    trg = names_trigger
            elif trg.pos < names_trigger.pos:
                trg = names_trigger

        if trg:
            self._last_trg_type = trg.type
        return trg

    def async_eval_at_trg(self, buf, trg, ctlr):
        # if a definition lookup, use godef
        log.debug('async_eval_at_trg:: %r' % (trg, ))
        if trg.form == TRG_FORM_DEFN:
            return self.lookup_defn(buf, trg, ctlr)
        elif trg.name == "go-complete-imports":
            return self.available_imports(buf, trg, ctlr)
        # otherwise use gocode
        return self.invoke_gocode(buf, trg, ctlr)

    def lookup_defn(self, buf, trg, ctlr):
        env = buf.env
        godef_path = self._get_gotool('godef', env)
        # We can't store the path and watch prefs because this isn't a
        # true xpcom object.
        if godef_path is None:
            godef_path = 'godef'
        cmd = [godef_path, '-i=true', '-t=true', '-f=%s' % buf.path, '-o=%s' % trg.pos]
        log.debug("running [%s]", cmd)
        p = process.ProcessOpen(cmd, env=buf.env.get_all_envvars())

        output, error = p.communicate(buf.accessor.text)
        if error:
            log.debug("'gocode' stderr: [%s]", error)
            raise CodeIntelError(error)

        lines = output.splitlines()
        log.debug(output)

        defparts = lines[0].rsplit(":",2)

        if len(defparts) == 2:
            # current file
            path = buf.path
            line = defparts[0]
        else:
            # other file
            path = defparts[0]
            line = defparts[1]
        name, typeDesc = lines[1].split(' ', 1)

        d = Definition("Go",path,
                       blobname=None,
                       lpath=None,
                       name=name,
                       line=line,
                       ilk='function' if typeDesc.startswith('func') else typeDesc,
                       citdl=None,
                       signature=typeDesc,
                       doc='\n'.join(lines[1:]),
                    )
        log.debug(d)
        ctlr.start(buf, trg)
        ctlr.set_defns([d])
        ctlr.done("success")

    _packages_from_exe = {}

    def available_imports(self, buf, trg, ctlr):
        env = buf.env
        go_exe = self.get_go_exe(env)
        if not go_exe:
            raise CodeIntelError("Unable to locate go executable")

        if go_exe not in self._packages_from_exe:
            cmd = [go_exe, 'list', 'std']
            cwd = None
            if buf.path != "<Unsaved>":
                cwd = os.path.dirname(buf.path)
            env_vars = env.get_all_envvars()
            log.debug("running cmd %r", cmd)
            try:
                p = process.ProcessOpen(cmd, cwd=cwd, env=env_vars)
            except OSError as e:
                raise CodeIntelError("Error executing '%s': %s" % (cmd, e))
            output, error = p.communicate()
            if error:
                log.warn("cmd %r error [%s]", cmd, error)
                raise CodeIntelError(error)
            package_names = [x.strip() for x in output.splitlines() if x]
            log.debug("retrieved %d package names", len(package_names))
            self._packages_from_exe[go_exe] = package_names

        stdlib_imports = self._packages_from_exe.get(go_exe, [])
        ctlr.start(buf, trg)
        ctlr.set_cplns([("import", name) for name in stdlib_imports])
        ctlr.done("success")

    def invoke_gocode(self, buf, trg, ctlr):
        pos = trg.pos
        if trg.type == "call-signature":
            pos = pos - 1

        env = buf.env
        gocode_path = self._get_gotool('gocode', buf.env)
        # We can't store the path and watch prefs because this isn't a
        # true xpcom object.
        if gocode_path is None:
            gocode_path = 'gocode'
        cmd = [gocode_path, '-f=json', 'autocomplete', buf.path, '%s' % pos]
        log.debug("running [%s]", cmd)
        try:
            p = process.ProcessOpen(cmd, env=env.get_all_envvars())
        except OSError as e:
            log.error("Error executing '%s': %s", cmd[0], e)
            return

        acc_text = buf.accessor.text
        if isinstance(acc_text, bytes):
            acc_text = acc_text.decode("utf-16")

        output, error = p.communicate(acc_text)
        if error:
            log.warn("'%s' stderr: [%s]", cmd[0], error)

        try:
            completion_data = json.loads(output)
            log.debug('full completion_data: %r', completion_data)
            completion_data = completion_data[1]
        except IndexError:
            ctlr.start(buf, trg)
            ctlr.error("no valid response from gocode: check gocode is running")
            ctlr.done("error")

            # exit on empty gocode output
            return
        except ValueError as e:
            log.exception('Exception while parsing json')
            return

        ctlr.start(buf, trg)
        completion_data = [x for x in completion_data if x['class'] != 'PANIC'] # remove PANIC entries if present
        if not completion_data:
            # Only contained PANIC entries.
            ctlr.error("no valid response from gocode: check gocode is running")
            ctlr.done("error")
            return

        if trg.type == "object-members":
            ctlr.set_cplns([(self.codeintel_type_from_completion_data(entry), entry['name']) for entry in completion_data])
            ctlr.done("success")
        elif trg.type == "call-signature":
            entry = completion_data[0]
            ctlr.set_calltips(['%s %s' % (entry['name'], entry['type'])])
            ctlr.done("success")
        elif trg.type == "any" and trg.implicit == False:
            ctlr.set_cplns([(self.codeintel_type_from_completion_data(entry), entry['name']) for entry in completion_data])
            ctlr.done("success")

    def get_go_exe(self, env):
        golang_path = env.get_pref("go", "")
        if golang_path and os.path.exists(golang_path):
            return golang_path
        path = [d.strip()
                for d in env.get_envvar("PATH", "").split(os.pathsep)
                if d.strip()]
        try:
            return which.which('go', path=path)
        except which.WhichError:
            return None

    def _get_gotool(self, tool_name, env):
        # First try the pref
        # Then try which
        # Finally try relative to the golang executable
        tool_path = env.get_pref(tool_name, "")
        if tool_path and os.path.exists(tool_path):
            return tool_path
        path = [d.strip()
                for d in env.get_envvar("PATH", "").split(os.pathsep)
                if d.strip()]
        try:
            return which.which(tool_name, path=path)
        except which.WhichError:
            pass
        go_exe = self.get_go_exe(env)
        if go_exe:
            ext = sys.platform.startswith("win") and ".exe" or ""
            tool_path = os.path.join(os.path.dirname(go_exe), tool_name + ext)
            if os.path.exists(tool_path):
                return tool_path
        return None

#---- Buffer class

class GoBuffer(CitadelBuffer):
    lang = lang
    # '/' removed as import packages use that
    cpln_fillup_chars = "~`!@#$%^&()-=+{}[]|\\;:'\",.<>? "
    cpln_stop_chars = "~`!@#$%^&*()-=+{}[]|\\;:'\",.<>? "
    ssl_lang = lang
    # The ScintillaConstants all start with this prefix:
    sce_prefixes = ["SCE_C_"]

#---- CILE Driver class

class GoCILEDriver(CILEDriver):
    lang = lang
    _gooutline_executable_and_error = None

    @LazyClassAttribute
    def golib_dir(self):
        ext_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        return os.path.join(ext_path, "golib")

    def compile_gooutline(self, buf):
        go_exe = buf.langintel.get_go_exe(buf.env)
        if not go_exe:
            raise CodeIntelError("Unable to locate go executable")
        if self._gooutline_executable_and_error is None or go_exe != self._gooutline_executable_and_error[0]:
            self._gooutline_executable_and_error = (go_exe, None, "Unknown Error")
            outline_src = os.path.join(self.golib_dir, "outline.go")
            cmd = [go_exe, "build", outline_src]
            cwd = self.golib_dir
            env = buf.env.get_all_envvars()
            try:
                # Compile the executable.
                p = process.ProcessOpen(cmd, cwd=cwd, env=env, stdin=None)
                output, error = p.communicate()
                if error:
                    log.warn("'%s' stderr: [%s]", cmd, error)
                outline_exe = outline_src.rstrip(".go")
                if sys.platform.startswith("win"):
                    outline_exe += ".exe"
                # Remember the executable.
                self._gooutline_executable_and_error = (go_exe, outline_exe, None)
            except Exception as ex:
                error_message = "Unable to compile 'outline.go'" + str(ex)
                self._gooutline_executable_and_error = (go_exe, None, error_message)
        if self._gooutline_executable_and_error[1]:
            return self._gooutline_executable_and_error[1]
        raise CodeIntelError(self._gooutline_executable_and_error[2])

    def scan_purelang(self, buf, mtime=None, lang="Go"):
        """Scan the given GoBuffer return an ElementTree (conforming
        to the CIX schema) giving a summary of its code elements.

        @param buf {GoBuffer} is the Go buffer to scan
        @param mtime {int} is a modified time for the file (in seconds since
            the "epoch"). If it is not specified the _current_ time is used.
            Note that the default is not to stat() the file and use that
            because the given content might not reflect the saved file state.
        """
        # Dev Notes:
        # - This stub implementation of the Go CILE return an "empty"
        #   summary for the given content, i.e. CIX content that says "there
        #   are no code elements in this Go content".
        # - Use the following command (in the extension source dir) to
        #   debug/test your scanner:
        #       codeintel scan -p -l Go <example-Go-file>
        #   "codeintel" is a script available in the Komodo SDK.
        log.info("scan '%s'", buf.path)
        if mtime is None:
            mtime = int(time.time())

        # The 'path' attribute must use normalized dir separators.
        if sys.platform.startswith("win"):
            path = buf.path.replace('\\', '/')
        else:
            path = buf.path

        try:
            gooutline_exe_path = self.compile_gooutline(buf)
        except Exception as e:
            log.error("Error compiling outline: %s", e)
            raise

        cmd = [gooutline_exe_path, buf.path]
        env = buf.env.get_all_envvars()
        log.debug("running [%s]", cmd)
        try:
            p = process.ProcessOpen(cmd, env=env)
        except OSError as e:
            log.error("Error executing '%s': %s", cmd, e)
            return

        output, error = p.communicate()
        if error:
            log.warn("'%s' stderr: [%s]", cmd[0], error)

        xml = '<codeintel version="2.0">\n' + output + '</codeintel>'
        return tree_from_cix(xml)


#---- registration

def register(mgr):
    """Register language support with the Manager."""
    mgr.set_lang_info(
        lang,
        silvercity_lexer=GoLexer(),
        buf_class=GoBuffer,
        langintel_class=GoLangIntel,
        import_handler_class=None,
        cile_driver_class=GoCILEDriver,
        is_cpln_lang=True)

