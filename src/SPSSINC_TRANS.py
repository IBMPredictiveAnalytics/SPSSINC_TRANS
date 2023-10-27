#/***********************************************************************
# * Licensed Materials - Property of IBM 
# *
# * IBM SPSS Products: Statistics Common
# *
# * (C) Copyright IBM Corp. 1989, 2023
# *
# * US Government Users Restricted Rights - Use, duplication or disclosure
# * restricted by GSA ADP Schedule Contract with IBM Corp. 
# ************************************************************************/

# Extension command for transformation functions


__author__  =  'spss, jkp'
__version__ =  '1.3.0'
version = __version__

# history
# 09-sep-2009  initial version
# 16-sep-2009   allow function to be defined in BEGIN PROGRAM block; dotted name support, class support
# 23-dec-2009 add INITIAL subcommand for class constructors
# 25-feb-2010  make empty strings converted to numeric yield missing (None)
# 06-jul-2010  support for TO in result list
# 08-Nov-2012 Support for parameter lists in formula and user missing value treatments
# 18-mar-2013 change variable creation code
# 12-jun-2014 guard None values in character data
# 23-sep-2023 switch formula parsing to be ast based



    ##debugging
# debugging
        # makes debug apply only to the current thread
try:
    import wingdbstub
    import threading
    wingdbstub.Ensure()
    wingdbstub.debugger.SetDebugThreads({threading.get_ident(): 1})
except:
    pass

import inspect, re, sys, ast
import spss
from extension import Template, Syntax, processcmd
from spssdata import ismissing


class DataStep(object):
    def __enter__(self):
        """initialization for with statement"""
        try:
            spss.StartDataStep()
        except:
            spss.Submit("EXECUTE")
            spss.StartDataStep()
        return self

    def __exit__(self, type, value, tb):
        spss.EndDataStep()
        return False


def Run(args):
    """Execute the SPSSINC TRANSFORM command"""

    args = args[list(args.keys())[0]]
    ###print args   #debug

    oobj = Syntax([
        Template("RESULT", subc="",  ktype="varname", var="result", islist=True),
        Template("TYPE", subc="",  ktype="int", var="vartype", vallist=[0,32767], islist=True),
        Template("USERMISSING", subc="", ktype="str", var="usermissing",
            vallist=["sysmis", "asis"]),
        Template("LITERALESCAPES", subc="", ktype="bool", var="literalescapes"),
        Template("", subc="INITIAL", ktype="literal", var="initial", islist=True),
        Template("", subc="VARIABLES", ktype="varname", var="variables", islist=True),
        Template("", subc="FORMULA", ktype="literal", var="formula", islist=True),
        Template("HELP", subc="", ktype="bool")])


    #enable localization
    global _
    try:
        _("---")
    except:
        def _(msg):
            return msg

    # A HELP subcommand overrides all else
    if "HELP" in args:
        #print helptext
        helper()
    else:
        processcmd(oobj, args, transform)


def helper():
    """open html help in default browser window
    
    The location is computed from the current module name"""
    
    import webbrowser, os.path
    
    path = os.path.splitext(__file__)[0]
    helpspec = "file://" + path + os.path.sep + \
         "markdown.html"
    
    # webbrowser.open seems not to work well
    browser = webbrowser.get()
    if not browser.open_new(helpspec):
        print(("Help file not found:" + helpspec))
try:    #override
    from extension import helper
except:
    pass

# main function

def transform(result, formula, vartype=(0,), literalescapes=False, initial=None,
    variables=None, usermissing="asis"):
    """Execute the transformations

    result is a list of variable names for the function result(s)
    formula is the expression to be evaluated as a list of tokens
    literal values have to be enclosed in << >> due to differences between the universal parser and
    Python on how quoted strings are handled. :-(
    vartype is a list of type values for the result variables.
    literalescapes == True causes the repr of the value to be returned.
    initial optionally provides an expression that is executed before initiating the case loop.
    It should generate a function named func that can be referenced in the formula.  No
    SPSS variables can be used.
    variables optionally is a list of variable names to be substituted in the formula
    usermissing indicates value pass through or convert to sysmis."""
    
    # debugging
            # makes debug apply only to the current thread
    try:
        import wingdbstub
        import threading
        wingdbstub.Ensure()
        wingdbstub.debugger.SetDebugThreads({threading.get_ident(): 1})
    except:
        pass  

    # global variable FIRST is provided so that functions can initialize themselves
    # It will be set True on first call.  It is up to the function to set it to False if desired
    global FIRST
    FIRST = True
    global funcs
    # global variable MISSINGS holds a name-indexed dictionary of user missing value
    # codes as per the Dataset class documentation.
    global MISSINGS
    try:
        formula = repair(formula, "FORMULA")
        if formula.startswith("="):
            formula = formula[1:]
        with DataStep():
            ds = spss.Dataset()     # the active dataset
            result, vartype = expandto(ds, result, vartype)
            resultindexes = []       # where result values will be stored
            numvars = len(ds.varlist)
            if not variables is None:   # variable existance is not checked here
                variables, ignore = expandto(ds, variables, (0,))
                variables = ",".join(variables)
                formula = formula.replace("<>", variables)
                
        # initialization needs to be done when no DataStep is in effect
        # but it needs the optional variables list expanded, for which
        # a dataset is required
        
        if initial:
            initial = repair(initial, "CLASS")
            if not variables is None:
                initial = initial.replace("<>", variables)
            initialize(initial)
        try:
            func = sys.modules["__main__"].func
        except:
            pass
        
            
        mods, invariables, nakedfuncs= getIdentifiers(formula)
        ###_customfunction = resolvestr(formula)
        funcs = {}
        
        with DataStep():
            ds = spss.Dataset()     # the active dataset
            # Create or modify result variable definition(s)

            numres = adjustresultdefs(result, ds, vartype, resultindexes, numvars)

            data = {}
            params = {}
            ###params["_customfunction"] = _customfunction  TODO?

            # try to map variable names to positions.
            # spssparams will contain module and function names as well as variable names
            # Since we can't tell them apart, exceptions here are ignored and caught later
            # when the expression is eval'ed

            MISSINGS = {}
            for k in invariables:
                try:
                    data[k] = ds.varlist[k].index  # replace names with indexes
                    MISSINGS[k] = ds.varlist[k].missingValues
                except:
                    pass

            # loop through the cases calling the function for each case

            for i, row in enumerate(ds.cases):
                for k, v in list(data.items()):
                    try:
                        if usermissing == "sysmis":
                            if ismissing(row[v], MISSINGS[k]):
                                params[k] = None
                                continue
                        params[k] = row[v]
                    except:
                        pass

                # The first time, check to see whether the specified function is actually a class.
                # If so, construct it and get its func attribute and use that as the function.

                ##if i == 0 and inspect.isclass(_customfunction):
                if i == 0:
                    ###mods, invariables, nakedfuncs= getIdentifiers(formula)
                    ###_customfunction = resolvestr(formula)
                    funcs = {}
                    for f in nakedfuncs:
                        try:
                            funcs[f] = getimport("__main__", f)
                            #exec(f"""from __main__ import {f}""", locals())
                        except:
                            raise ValueError(f("""function {f} was not found in __main__"""))
                    for m in mods:
                        try:
                            # imported modules need to be listed in funcs, because that will
                            # be the globals dictionary that eval will see.
                            exec(f"""import {m}""")
                            funcs[m] = sys.modules[m]
                        except:
                            raise ValueError(_(f"""Module {m} was not found"""))
                    try:
                        co = compile(formula, "<formula>", "eval")
                    except:
                        raise ValueError(_(f"""The formula contains a syntax error:\n{sys.excinfo()[1]}"""))
                try:
                    # funcs should contain all the local functions
                    res = eval(co, funcs, params)   # compute the requested values
                    ###res = eval(formula, funcs, params)   # compute the requested values
                except:
                    raise ValueError(_("The formula references an undefined variable or could not be evaluated:\n") + str(sys.exc_info()[1]))
                processresults(res, numres, literalescapes, vartype, ds, i, resultindexes)
    finally:
        del FIRST    # really should be in finally 

def processresults(res, numres, literalescapes, vartype, ds, i, resultindexes):
    if isinstance(res, (str, int, float, type(None))):
        res = [res]
    else:
        res = list(res)   # function might have returned some complicated object
    for r in range(len(res), numres):   # fill with None if too few results returned
        res.append(None)
    if len(res) != numres:
        raise ValueError(_("Function returned too many values.  Number expected: %s") % numres)
    for r in range(numres):
        if literalescapes and vartype[r] > 0:
            res[r] = repr(res[r])    # protect escape sequences such as \t so they will be taken literally
        if vartype[r] == 0 and res[r] == "":   # converting an empty string to a float - make it missing
            res[r] = None
        elif vartype[r] > 0 and res[r] is None:
            res[r] = ""

        # try to coerce result values to the type declared for the result
        if (
            vartype[r] == 0
            and not isinstance(res[r], (float, int))
            and not res[r] is None
        ):
            try:
                res[r] = float(res[r])
            except:
                res[r] = None
        if vartype[r] > 0 and not isinstance(res[r], str):
            try:
                res[r] = str(res[r])
            except:
                pass
        
        ds.cases[i, resultindexes[r]] = res[r]   # update the dataset

def adjustresultdefs(result, ds, vartype, resultindexes, numvars):
    for i, v in enumerate(result):
        try:
            vindex = ds.varlist[v].index
            if ds.varlist[vindex].type != vartype[i]:   # change type if necessary
                ds.varlist[vindex].type = vartype[i]
                if vartype[i] > 0:
                    ds.varlist[vindex].alignment = 0   # left aligned for strings
                else:
                    ds.varlist[vindex].alignment = 2   # ensure right-aligned for number
            resultindexes.append(vindex)
        except:   # new variable
            ds.varlist.append(v, vartype[i])
            resultindexes.append(numvars)
            if vartype[i] > 0:
                ds.varlist[numvars].alignment = 0   # left aligned for strings
            numvars += 1
    numres = len(result)
    return numres


def resolvestr(afunc):
    """Return a compiled function suitable for execution by eval

    afunc is a string in the form module.func
    or module.func(parm=value,...)to be imported.
    """

    # f is the function name
    # co is the compiled expression
    # spssp is the set of parameters to be satisfied from SPSS case data
    f, co, spssp = factor(afunc)

    if re.match(r"[a-zA-Z0-9_]+\(", afunc) is None:
        return None, None, None, None
    bf = f.split(".")

    if len(bf) == 1:     # try to get the function or class from the anonymous main, then check if it is a built-in
        item = bf[0].strip()
        _customfunction = getattr(sys.modules["__main__"], item, None)
        modname = "__main__"
        if _customfunction is None:
            _customfunction = __builtins__.get(item, None)
        if not callable(_customfunction):
            raise ValueError(_("""The specified function or class was given without a module name
and was not found in a previous BEGIN PROGRAM block 
and is not a built-in function: """) + item)
    else:
        modname = ".".join(bf[:-1])
        _temp = __import__(modname, globals(), locals(), [bf[-1]], 0)
        _customfunction = _temp.__dict__[bf[-1]]

    return _customfunction

def factor(afunc):
    """decompose the string m.f or m.f(parms) and return function and parameter dictionaries

    afunc has the form xxx or xxx(p1=value, p2=value,...)
    create a dictionary from the parameters consisting of at least _first:True.
    parameter must have the form name=value, name=value,... 
    """

    firstparen = afunc.find("(")

    if firstparen >0:       # parameters found, make a dictionary of them
        try:
            f = afunc[:firstparen]
            afunc = "_customfunction" + afunc[firstparen:]
            co = compile(afunc, "<string>", "eval")
            spssparams = set(co.co_names)
        except :
            raise ValueError(_("The formula syntax given is invalid:\n") + str(sys.exc_info()[1]))
    else:
        spssparams = set()
        f = afunc
        co = compile("_customfunction()", "<string>", "eval")
    return f, co, spssparams

def repair(formula, label):
    """Attempt to put a formula tokenized by the UP back together and return the literal
    
    formula is the sequence of tokens to repair
    label is the text to use to identify the formula"""
    
    fo = formula[:2]
    special = '=[]()+-*/^'
    special2 = '([=+-*/^'
    fot = formula[2:]

    try:
        for i, item in enumerate(fot):
            if item in special or i == 0 or fot[i-1] in special2:
                fo.append(item)
            else:
                fo.append("," + item)
    except:
        raise ValueError(_("Error: the expression is invalid.  Check for unbalanced parentheses or quotes or a missing =: %s") % label)
    formula = "".join(fo)    # put the pieces back together
    return formula

def initialize(expr):
    """call the function or class constructor
    
    expr is an expression of the form mod.func(... where mod. is optional
    func is inserted into the __main__ namespace"""
    
    mo = re.match(r"(.*?)\..*\(?", expr)
    if mo:  # a module name was given
        modname = mo.group(1)
        exec("import " + modname)
        sys.modules["__main__"].func = eval(expr).func
    else:  # presume that class has been defined in main context
        sys.modules["__main__"].func = eval("sys.modules['__main__']." + expr).func
    
def expandto(ds, result, vartype):
    """Return result and vartype with any TO construct expanded
    
    ds is an spss.Dataset object
    result is the result variable list
    vartype = tye result type list after expansion of singletons
    
    TO/to expanded as follows where TO is caseless
    The form is x TO y.
    Either both x and y must already exist or neither.
    If both exist, x TO y is replaced by the inclusive list of existing variables
    If neither exist x and y the expression must have the form
    xm TO xn where m and n are integers and n>=m.  It will be expanded to
    xm xm+1 ... xn.
    In the expanded expressions, appropriate leading zeros are preserved.
    The type list is expanded with the matching type of the first variable, hence
    all variables in the expanded expression will have the same type."""
    

    #if len(result) < 3:   # using TO requires at least 3 items
        #return result, vartype
    result = regroup(result)  # turn results into single vars or TO constructs
    if len(vartype) == 1:
        vartype= len(result) * [vartype[0]]
    if len(vartype) != len(result):
        raise ValueError(_("The number of variable type values differs from the number of result variables"))
    rresult = []
    rvartype = []
    for i, r in enumerate(result):
        if len(r) == 1:
            rresult.append(r[0])
            rvartype.append(vartype[i])
        else:
            index1, index2 = -1, -1
            try:   # need to see if neither or both variables exist - in not supported
                index1 = ds.varlist[r[0]].index
                index2 = ds.varlist[r[1]].index
            except:
                pass
            if (index1 >=0) ^ (index2 >=0):
                raise ValueError(_("Either neither or both names must exist in TO"))
            if index1 >= 0:   # variables exist
                if index2 < index1:
                    raise ValueError(_("Variables in TO are not in file order: %s, %s") % (r[0], r[1]))
                for v in range(index1, index2+1):
                    rresult.append(ds.varlist[v].name)
                    rvartype.append(vartype[i])
            else:  # variable do not exist
                numberednames = gennames(r)
                for v in numberednames:
                    rresult.append(v)
                    rvartype.append(vartype[i])
    return rresult, rvartype
    
    
def regroup(result):
    """Return list of single vars or duples of (start,end) for TO construct"""
    
    if result[0].lower() == 'to' or result[-1].lower() == 'to':
        raise ValueError(_("TO cannot start or end the result list"))
    rresult = []
    start = 0
    reslen = len(result)
    while start < reslen:
        tonext = start < reslen-1 and result[start+1].lower() == "to"
        if not tonext:
            rresult.append((result[start],))
            start += 1
        else:
            rresult.append((result[start], result[start+2]))
            start += 3
    return rresult
            
def gennames(r):
    """Generate variable names with numerical suffixes
    
    r is a duple of names ending in digit(s)"""
    
    r1 = re.match(r"(.*?)(\d+)$", r[0])
    r2 = re.match(r"(.*?)(\d+)$", r[1])
    if r1 is None or r2 is None:
        raise ValueError(_("New variables used with TO must have a numerical suffix"))
    r1 = r1.groups()
    r2 = r2.groups()
    if not (r1[0].lower() == r2[0].lower() and int(r1[1]) <= int(r2[1])):
        raise ValueError(_("New variables used with TO must have the same prefix and ascending numerical parts: %s, %s") % (r[0], r[1]))
    numlen = len(r1[1])
    res = []
    for i in range(int(r1[1]), int(r2[1])+1):
        res.append(r1[0] + "%0*d" % (numlen, i))
    return res
    
    
def getIdentifiers(frml):
    """return sets of imports, variables, and nonbuiltin functions
    
    frml is a Python expressions for evaluation
    variable names must be syntactically valid as Python identifiers"""
    
    frml = frml.strip()
    try:
        tree = ast.parse(frml)  # exception raised if bad syntax
    except:
        print(f"""Invalid syntax: {sys.exc_info()[1]}""")
        raise 
    flen = len(frml)
    # Using sets eliminates duplicates
    varnames = set()
    imports = set()
    nakedfuncs = set()
    walrus = set()
    
    for node in ast.walk(tree):
        # walrus operator variables are NOT spss variables (but can be very useful)
        if isinstance(node, ast.NamedExpr):
            walrus.add(node.target.id)
            continue
        if isinstance(node, ast.Name):
            item = node.id
            if item in walrus:
                continue
            istart, iend = node.col_offset, node.end_col_offset
            # guess whether module or variable - could be wrong
            # var if end of expr or last char not . or ; and does not look like a module function reference
            
            # list if unqualified function and not a builtin
            if iend < flen and frml[iend] == "(" and (istart == 0 or frml[istart-1] != "."):
                if not item in __builtins__:
                    nakedfuncs.add(item)
            else:
                if iend == flen or frml[iend] not in [".", ";"] or re.match(r"[_a-zA-Z0-9.]+\(", frml[istart:]) is None:
                    # This test may never be reached as bad syntax has already caused an exception
                    if not item.isidentifier():
                        raise ValueError(_(f"""{varname} is not a legal variable name in Python.
Please rename the SPSS variable in order to use it here."""))
                    varnames.add(item)
                    ###    variables.add((node.id, node.col_offset, node.end_col_offset))
                else:
                    # some modules such as str are not importable, so protect these imports later on
                    # __main__ is already available
                    if item != "__main__":
                        imports.add(item)
    ###return imports, variables, nakedfuncs
    return imports, varnames, nakedfuncs

def getimport(module, name):
    module = __import__(module, fromlist=[name])
    return getattr(module, name)