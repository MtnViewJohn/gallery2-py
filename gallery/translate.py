import io
import re
from gal_utils import text

class Translator:
    userstring = 1
    userrational = 2
    userfilename = 3
    usermod = 4
    userop = 5
    userstart = 6
    userconfig = 7
    userrule = 8
    userpath = 9
    userinclude = 10
    userpathop = 11
    usereof = 12
    usertargetmod = 13

    symbols = [u'{', u'}', u'[', u']', u'^', u'*', u'/', u'+', u'-', u'(', 
               u')', u',', u'|', u'\u2026', u'\u00B1', u'\u2264', u'\u2265',
               u'\u2260', u'\u221e']

    tokens = [
        (re.compile(r'startshape\b'), userstart),
        (re.compile(r'background\b'), userconfig),
        (re.compile(r'include\b'), userinclude),
        (re.compile(r'tile\b'), userconfig),
        (re.compile(r'rule\b'), userrule),
        (re.compile(r'path\b'), userpath),
        (re.compile(r'rotate\b'), usermod),
        (re.compile(r'r\b'), usermod),
        (re.compile(r'flip\b'), usermod),
        (re.compile(r'f\b'), usermod),
        (re.compile(r'hue\b'), usermod),
        (re.compile(r'h\b'), usermod),
        (re.compile(r'saturation\b'), usermod),
        (re.compile(r'sat\b'), usermod),
        (re.compile(r'brightness\b'), usermod),
        (re.compile(r'b\b'), usermod),
        (re.compile(r'alpha\b'), usermod),
        (re.compile(r'a\b'), usermod),
        (re.compile(r'x\b'), usermod),
        (re.compile(r'y\b'), usermod),
        (re.compile(r'x1\b'), usermod),
        (re.compile(r'y1\b'), usermod),
        (re.compile(r'rx\b'), usermod),
        (re.compile(r'ry\b'), usermod),
        (re.compile(r'x2\b'), usermod),
        (re.compile(r'y2\b'), usermod),
        (re.compile(r'z\b'), usermod),
        (re.compile(r'size\b'), usermod),
        (re.compile(r's\b'), usermod),
        (re.compile(r'skew\b'), usermod),
        (re.compile(r'\|hue\b'), usertargetmod),
        (re.compile(r'\|h\b'), usertargetmod),
        (re.compile(r'\|saturation\b'), usertargetmod),
        (re.compile(r'\|sat\b'), usertargetmod),
        (re.compile(r'\|brightness\b'), usertargetmod),
        (re.compile(r'\|b\b'), usertargetmod),
        (re.compile(r'\|alpha\b'), usertargetmod),
        (re.compile(r'\|a\b'), usertargetmod),
        (re.compile(r'param\b'), usermod),
        (re.compile(r'p\b'), usermod),
        (re.compile(r'width\b'), usermod),
        (re.compile(r'MOVETO\b'), userpathop),
        (re.compile(r'LINETO\b'), userpathop),
        (re.compile(r'ARCTO\b'), userpathop),
        (re.compile(r'CURVETO\b'), userpathop),
        (re.compile(r'MOVEREL\b'), userpathop),
        (re.compile(r'LINEREL\b'), userpathop),
        (re.compile(r'ARCREL\b'), userpathop),
        (re.compile(r'CURVEREL\b'), userpathop),
        (re.compile(r'CLOSEPOLY\b'), userpathop)
    ]

    def __init__(self, cfdg2txt):
        self.lineno = 1
        self.colortarget = False
        self.extraChars = False
        self.cfdg2 = cfdg2txt
        self.begin = 0
        self.output = io.StringIO()
        self.token = None
        self.toktype = 0

    def close(self):
        self.output.close()


    linecomment = re.compile(r'(//|#)[^\n]*$', flags = re.MULTILINE)
    blockcomment = re.compile(r'/\*.+?\*/', flags = re.MULTILINE + re.DOTALL)
    whitespace = re.compile(r'\s+')
    float1 = re.compile(r'\d+\.?\d*')
    float2 = re.compile(r'\.\d+')
    filename = re.compile(r'[a-zA-Z]\S*\.cfdg', re.UNICODE)
    qfilename = re.compile(r'"[^"\n]*"')
    identifier = re.compile(r'\w+', re.UNICODE)

    def lex(self):
        if self.token is not None:
            ret = self.token
            self.token = None
            return (ret, self.toktype)

        while  True:
            # Skip (but echo) comments and white space.
            while True:
                m = (Translator.linecomment.match(self.cfdg2, self.begin) or 
                     Translator.blockcomment.match(self.cfdg2, self.begin) or 
                     Translator.whitespace.match(self.cfdg2, self.begin))
                if m:
                    out = m.group(0)
                    self.output.write(out)
                    self.begin = m.end(0)
                    self.lineno += out.count(u'\n')
                else:
                    break;

            # End of file
            if self.begin == len(self.cfdg2):
                return (u'', Translator.usereof)

            # Floats
            m = (Translator.float1.match(self.cfdg2, self.begin) or
                 Translator.float2.match(self.cfdg2, self.begin))
            if m:
                self.begin = m.end(0)
                return (m.group(0), Translator.userrational)

            # Include filenames
            m = (Translator.filename.match(self.cfdg2, self.begin) or
                 Translator.qfilename.match(self.cfdg2, self.begin))
            if m:
                self.begin = m.end(0)
                return (m.group(0), Translator.userfilename)

            # operators, grouping, and |
            for symbol in Translator.symbols:
                if self.cfdg2.startswith(symbol, self.begin):
                    self.begin += 1
                    return (symbol, Translator.userop)

            # reserved keywords
            for (regex, toktype) in Translator.tokens:
                m = regex.match(self.cfdg2, self.begin)
                if m:
                    self.begin = m.end(0)
                    return (m.group(0), toktype)

            # Identifiers (shape names)
            m = Translator.identifier.match(self.cfdg2, self.begin)
            if m:
                self.begin = m.end(0)
                return (m.group(0), Translator.userstring)

            # Unknown character. In version 3 this caused an error but in
            # version 2 they were silently dropped. Older cfdg files have
            # lots of wierd extra stuff in them. Here we filter them out.
            self.begin += 1
            self.output.write(u' ')
            self.extraChars = True


    def unlex(self, token, toktype):
        if self.token is not None:
            raise Exception(u'Internal error in translator.')

        self.token = token
        self.toktype = toktype

    def translate(self):
        currentshape = ''
        while True:
            (token, toktype) = self.lex()

            if toktype == Translator.usereof:
                return

            if toktype == Translator.userstart:
                currentshape = u''
                self.output.write(u'startshape')
                (token, toktype) = self.lex()
                if toktype == Translator.userstring:
                    self.output.write(token)
                else:
                    print (token, toktype)
                    raise Exception(u'Bad startshape at line ' + text(self.lineno))

                # Peek at next token to see if it is ( color etc ). This is an
                # old syntax that was dropped. Here we will just drop them.
                (token, toktype) = self.lex()
                if token == '{':
                    while True:
                        (token, toktype) = self.lex()
                        if token == '}':
                            break
                else:
                    self.unlex(token,toktype)


            elif toktype == Translator.userinclude:
                currentshape = u''
                self.output.write(u'import')
                (token, toktype) = self.lex()
                if toktype == Translator.userfilename:
                    self.output.write(token)
                else:
                    raise Exception(u'Bad include at line ' + text(self.lineno))

            elif toktype == Translator.userrule:
                (token, toktype) = self.lex()
                if toktype == Translator.userstring:
                    if currentshape != token:
                        self.output.write(u'shape ' + token + u'\n')
                        currentshape = token
                else:
                    raise Exception(u'Bad rule at line ' + text(self.lineno))
                self.output.write(u'rule')
                (token, toktype) = self.lex()
                if toktype == Translator.userrational:
                    self.output.write(token)
                    (token, toktype) = self.lex()
                if token != u'{':
                    raise Exception(u'Unrecognized token at line ' + text(self.lineno))
                self.output.write(u'{')
                self.translateRuleBody()

            elif toktype == Translator.userpath:
                currentshape = u''
                self.output.write(u'path')
                (token, toktype) = self.lex()
                if toktype != Translator.userstring:
                    raise Exception(u'Bad path name at line ' + text(self.lineno))
                self.output.write(token)
                (token, toktype) = self.lex()
                if token != u'{':
                    raise Exception(u'Unrecognized token at line ' + text(self.lineno))
                self.output.write(u'{')
                self.translatePathBody()

            elif (toktype == Translator.userconfig or
                    (toktype == Translator.usermod and token == u'size')):
                self.output.write(u'CF::' + token.capitalize() + u' =')
                self.translateMod()
                currentshape = ''

            else:
                raise Exception(u'Unrecognized token at line ' + text(self.lineno))


    def translateMod(self):
        params = None
        width = None
        (token, toktype) = self.lex()
        if token != u'{' and token != u'[':
            raise Exception(u'Expecting an adjustment at line ' + text(self.lineno))
        basic = token == u'{'

        self.output.write(u'[' if basic else u'[[')

        while True:
            (token, toktype) = self.lex()
            if toktype == Translator.userop:
                if token == u'}' or token == u']':
                    if token == (u']' if basic else u'}'):
                        raise Exception(u'Adjustment delimeters don\'t match at line ' + text(self.lineno))
                    self.output.write(u']' if basic else u']]')
                    return (params, width)
                if token == u'|':
                    self.colortarget = True;
                self.output.write(token)

            elif toktype == Translator.userrational or toktype == Translator.userstring:
                self.output.write(token)

            elif toktype == Translator.usertargetmod or toktype == Translator.usermod:
                if toktype == Translator.usertargetmod:
                    self.colortarget = True

                if token == u'p' or token == u'param':
                    (token, toktype) = self.lex()
                    if toktype != Translator.userstring:
                        raise Exception(u'Error parsing adjustment parameter at line ' + text(self.lineno))
                    params = token
                elif token == u'width':
                    saveOutput = self.output
                    self.output = io.StringIO()
                    while True:
                        (token, toktype) = self.lex()
                        if (token == u']' or token == u'}' or 
                            toktype == Translator.usermod or 
                            toktype == Translator.usertargetmod):
                            self.unlex(token,toktype)
                            break;
                        self.output.write(token)

                    width = self.output.getvalue()
                    self.output.close()
                    self.output = saveOutput
                else:
                    self.output.write(token)

            else:
                raise Exception(u'Error parsing adjustment at line ' + text(self.lineno))



    def translateRuleBody(self):
        while True:
            (token, toktype) = self.lex()
            if toktype == Translator.userstring:
                self.output.write(token)
                self.translateMod()
            elif toktype == Translator.userrational:
                self.translateLoopRule(token)
            elif token == u'}':
                self.output.write(u'}')
                return
            else:
                raise Exception(u'Error parsing rule at line ' + text(self.lineno))

    def translateLoopRule(self, count):
        self.output.write(u'loop ' + count)
        (token, toktype) = self.lex()
        if token != u'*':
            raise Exception(u'Error parsing loop at line ' + text(self.lineno))
        self.translateMod()
        (token, toktype) = self.lex()
        if toktype == Translator.userstring:
            self.output.write(token)
            self.translateMod()
        elif token == u'{':
            self.output.write(u'{')
            self.translateRuleBody()
        else:
            raise Exception(u'Error parsing loop at line ' + text(self.lineno))


    def translatePathBody(self):
        while True:
            (token, toktype) = self.lex()
            if toktype == Translator.userstring or toktype == Translator.userpathop:
                self.translatePathElement(token)
            elif toktype == Translator.userrational:
                self.translateLoopPath(token)
            elif token == u'}':
                self.output.write(u'}')
                return
            else:
                raise Exception(u'Error parsing path at line ' + text(self.lineno))


    def translateLoopPath(self, count):
        self.output.write(u'loop ' + count)
        (token, toktype) = self.lex()
        if token != u'*':
            raise Exception(u'Error parsing loop at line ' + text(self.lineno))
        self.translateMod()
        (token, toktype) = self.lex()
        if toktype == Translator.userstring or toktype == Translator.userpathop:
            self.translatePathElement(token)
        elif token == u'{':
            self.output.write(u'{')
            self.translatePathBody()
        else:
            raise Exception(u'Error parsing loop at line ' + text(self.lineno))


    def translatePathElement(self, name):
        self.output.write(name)
        if name == u'FILL' or name == u'STROKE':
            saveOutput = self.output
            self.output = io.StringIO()
            (params, width) = self.translateMod()
            cmdMod = self.output.getvalue()
            self.output.close()
            self.output = saveOutput
            if params or width:
                self.output.write(u'(')
                if width:
                    self.output.write(width)
                if params and width:
                    self.output.write(u', ')
                if params:
                    self.translateParams(params)
                self.output.write(u')')
            self.output.write(cmdMod)
            return

        (token, toktype) = self.lex()
        if token != u'{':
            raise Exception(u'Error parsing path op at line ' + text(self.lineno))

        args = {}
        ptType = u''
        saveOutput = self.output
        self.output = io.StringIO()
        while True:
            (token, toktype) = self.lex()
            if token == u'}':
                if ptType != u'':
                    args[ptType] = self.output.getvalue()
                self.output.close()
                self.output = saveOutput
                break

            if toktype == Translator.usermod:
                if ptType != u'':
                    args[ptType] = self.output.getvalue()
                    self.output.close()
                    self.output = io.StringIO()

                if token == u'p' or token == u'param':
                    (token, toktype) = self.lex()
                    if toktype != Translator.userstring:
                        raise Exception(u'Error parsing path op parameter at line ' + text(self.lineno))
                    args[u'param'] = token
                    ptType = u''
                else:
                    ptType = token
            else:
                self.output.write(token)

        if name == u'CLOSEPOLY':
            self.output.write(u'(')
            if u'param' in args:
                self.translateParams(args[u'param'])
            self.output.write(u')')
            return

        self.output.write(u'(')
        if u'x' in args:
            self.output.write(args[u'x'])
        else:
            self.output.write(u'0')
        self.output.write(u', ')
        if u'y' in args:
            self.output.write(args[u'y'])
        else:
            self.output.write(u'0')

        if name in [u'MOVETO', u'MOVEREL', u'LINETO', u'LINEREL']:
            pass

        elif name in [u'ARCTO', u'ARCREL']:
            if u'rx' in args or u'ry' in args:
                self.output.write(u', ')
                if u'rx' in args:
                    self.output.write(args[u'rx'])
                else:
                    self.output.write(u'1')
                self.output.write(u', ')
                if u'ry' in args:
                    self.output.write(args[u'ry'])
                else:
                    self.output.write(u'1')
                self.output.write(u', ')
                if u'r' in args:
                    self.output.write(args[u'r'])
                else:
                    self.output.write(u'0')
            else:
                self.output.write(u', ')
                if u'r' in args:
                    self.output.write(args[u'r'])
                else:
                    self.output.write(u'1')

            if u'param' in args:
                self.output.write(u', ')
                self.translateParams(args[u'param'])

        elif name in [u'CURVETO', u'CURVEREL']:
            p1 = u'x1' in args and u'y1' in args
            p2 = u'x2' in args and u'y2' in args
            if p1:
                self.output.write(u', ' + args[u'x1'] + u', ' + args[u'y1'])
            if p2:
                self.output.write(u', ' + args[u'x2'] + u', ' + args[u'y2'])
            if not p1:
                self.output.write(u', CF::Continuous')

        else:
            raise Exception(u'Error parsing path op at line ' + text(self.lineno))

        self.output.write(u')')



    def translateParams(self, pstring):
        params = []
        if u'cw' in pstring:
            params.append(u'CF::ArcCW')
        if u'large' in pstring:
            params.append(u'CF::ArcLarge')
        if u'align' in pstring:
            params.append(u'CF::Align')
        if u'miterjoin' in pstring:
            params.append(u'CF::MiterJoin')
        if u'roundjoin' in pstring:
            params.append(u'CF::RoundJoin')
        if u'beveljoin' in pstring:
            params.append(u'CF::BevelJoin')
        if u'buttcap' in pstring:
            params.append(u'CF::ButtCap')
        if u'roundcap' in pstring:
            params.append(u'CF::RoundCap')
        if u'squarecap' in pstring:
            params.append(u'CF::SquareCap')
        if u'iso' in pstring:
            params.append(u'CF::IsoWidth')
        if u'evenodd' in pstring:
            params.append(u'CF::EvenOdd')
        if len(params) == 0:
            params.append(u'CF::None')
        self.output.write(u'+'.join(params))

