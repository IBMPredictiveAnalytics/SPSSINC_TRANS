#/***********************************************************************
# * Licensed Materials - Property of IBM 
# *
# * IBM SPSS Products: Statistics Common
# *
# * (C) Copyright IBM Corp. 1989, 2014
# *
# * US Government Users Restricted Rights - Use, duplication or disclosure
# * restricted by GSA ADP Schedule Contract with IBM Corp. 
# ************************************************************************/

# Extension command for transformation functions
from __future__ import with_statement

__author__  =  'spss, jkp'
__version__ =  '1.2.4'
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


helptext="""SPSSINC TRANS RESULT=varname-list [TYPE=number-list] [USERMISSING={ASIS*| SYSMIS}
[/INITIAL i-expression]
[/VARIABLES variablelist]
/FORMULA f-expression.

varname-list is the list of names for the result variables.  Typically there is only one, but
a function can return multiple values.  If fewer values than requested are returned for a case,
the values are filled out with sysmis or blank.  If too many values are returned,
the command stops with an error message.

TO can be used in the result list with the following rules.
If the variables in TO exist, TO is expanded in the usual way to that list of variables in file order.
If the variables do not exist, and they have the same root and numerical suffixes, they are
expanded in numerical order.  For example,
a b c01 to c03 d
expands to
a b c01 c02 c03 d
if c01 and c03 do not exist.
Either both or neither of the TO variables must exist.  Any preexisting variables in the
expanded list will be replaced.

number-list is a list of the type codes for the variables.  0, the default, means numeric.  
Positive integer values mean a string of that length.  There must be as many type 
codes as there are result variables, except that the entire list can be omitted if 
all values are to be numeric, and a single number can be specified to apply to 
the entire result list.  Types will be changed for existing variables if necessary.  
Type changes happen BEFORE the data are passed, so the Python code 
should expect to see values in that representation.  Note that some type changes 
destroy the values.

If TO is used in the result list, exactly one type code for the group should be specified if
a number list is provided.

System missing values are converted to Python None.  By default, user missing
values are left as is.  Specify USERMISSING=SYSMIS to convert these to the
sysmis value (None) before calling the formula function.

For Python programmers, a dictionary of user missing values can be accessed as
sys.modules["SPSSINC_TRANS"].MISSINGS
It can be used to work with individual variable missing values like this toy example, which
just tests a specific variable for any type of missing value.

begin program.
from spssdata import ismissing
def anymissing(x):
    mvs = sys.modules["SPSSINC_TRANS"].MISSINGS['X1']
    return  ismissing(x, mvs)
end program.
spssinc trans result = x1missing
/formula "anymissing(X1)".

This only makes sense if USERMISSING = ASIS, since otherwise you can just
test for None.  That allows for more selective handling of user missings.

f-expression is the formula to evaluate.  It should have the form
modulename.function(parm1=value, parm2=value,...)
where 
modulename.function is the Python function to call.  This might be from a
module in the Python library, an SPSS Community module, or any other source.
If modulename is omitted, the function is assumed to have been defined in
a previous BEGIN PROGRAM block executed in the current session,
or via the INITIAL subcommmand, or, if it is not defined that way, 
it can be a built-in Python function.

parm1, parm2, ... are the names of the function parameters: each value
is an existing SPSS Statistics variable name, a number, or a literal string in triple quotes.
Use opposite-style quotes for literals.  E.g., if the literal contains ", use '
to delimit the string.

Literal strings must be enclosed in triple single or double quotes.
For example, write
parm1 = '''abc"def'''

The parameter expression can be made as a Python list containing variable names, number, and/or literals
by enclosing the items in square brackets.  For example
/formula mymodule.myfunc(variables=[x,y,z, 100], parm='''a literal''')
where x, y, and z will be interpreted as variables in the active dataset.  

For functions that have parameters that are not named such as many of the built-in functions,
omit the "name=" part of the call, e.g.,
/formula max(paeduc, maeduc)
More general Python expressions can be used with some limitations.  
Standard Python operators except / can be used in parameter expressions,
e.g. parm1=x+y
as long as they do not reference something that needs to be imported.
Since the expression must be valid Python syntax, reserved words such
as in, with, for, def, and class, among others, cannot be used in it.

You can enclose the entire formula in single or double quotes in order to
use general expressions.  In this case do not use triple quotes around 
literals but use the opposite type of quotes or double them according
to Statistics conventions.

The item named as the function can be a suitable class if the class initialization
parameters are compatible with the call (but see the INITIAL subcommand).  If a class
is specified, it is constructed on the first case.  It must create an attribute
named func that is the actual function to be called.  This provides
a convenient way to initialize parameters.  See the subs function in
extendedTransforms.py for an example.

Numerical values are by default passed as float values.  If a function requires
an argument to be an integer, wrap it in the int function.  For example,
/FORMULA mod.f(Year = int(2000), ...)
Remember that the int function does not accept None values, which is what sysmis becomes.

The VARIABLES subcommand can be used to create a Python variable list in 
the formula or initial expressions that supports SPSS rules.  
It allows the use of TO according to the rules above for RESULT
except that all the variables must already exist (since these are inputs).  
To refer to the variable list in the formula or initial expressions, use
<> in that expression.  For example,

/VARIABLES= V1 TO V3
/FORMULA "somefunc(<>, parm=100)"

would be interpreted as

/FORMULA "somefunc(V1, V2, V3, parm=100)"

assuming that V1, V2, and V3 exist.

INITIAL can be used to construct a function, which must be named func, that can be
used in the f-expression.  The expression must be a class constructor, and it will usually
have a different parameter list from the evaluation function.  Here is an example
using the vlookup function in extendedTransforms.

SPSSINC TRANS RESULT=resultcode TYPE=0
/INITIAL "extendedTransforms.vlookup(key='key', value='value', dataset='lookup')"
/FORMULA func(x).

vlookup takes a dataset defining a lookup table with key as the lookup key and value
as the result.  This class returns the actual lookup function named func which is
then used in the f-expression.

The automatic constructor call described above can be used, but the likely
difference in the parameter lists often makes using INITIAL more convenient.
The i-expression is only called once and does not participate in the case-
processing loop.

The INITIAL expression cannot refer to SPSS variables as they are undefined
at this point.  If you use the "<>" construct in the initial call, the <>
is expanded, but to avoid undefined variables, the list needs to be quoted
just as would be required if an explicit list of SPSS variables was given.
For example, /VARIABLES salary salbegin /INITIAL   "C('<>')"
would be expanded to
C('salary, salbegin')
and the __init__ function could use this as appropriate.  Here is a complete,
example using an inline class definition.  The result is to
compute the mean of the listed variables.  In this case, of course,
the result could be computed more directly.

begin program.
class C(object):
    def __init__(self, *args):
        self.numvar = len(args[0].split(","))
        def f(*args):
            return sum(args)/self.numvar
        self.func = f
end program.

spssinc trans result=nsum
/variables salary salbegin
/INITIAL   "C('<>')"
/FORMULA   "func(<>)"

Python escape sequences such as \t are expanded in the final value.  Thus a \t would become
a tab character.  LITERALESCAPES=YES causes these values to be protected with
an extra backslash (the repr value).  This will, of course, make the string longer.

The capitalization of the module, function, and parameter names must match the
function definition.

Example:
SPSSINC TRANS RESULT=datestring TYPE=30
FORMULA extendedTransforms.datetimetostr(value=adatevar, pattern='''%A, %B %d, %Y''').

This calls the function datetimetostr in the extendedTransforms module, which converts an
SPSS date value to a string according to the pattern 
dayname, monthname day-of-month, 4-digit-year
and stores the result in the variable datestring, which is made to be a string of length 30.

The parameter names will depend on the particular function called.

For function authors,
A variable named FIRST is set True when the function is first called in case the
function needs to do some one-time initialization.  It can be accessed as
sys.modules["SPSSINC_TRANS"].FIRST

Set it to False on the first call.  Suggested code would resemble this;
    try:
        if sys.modules["SPSSINC_TRANS"].FIRST:
            print "first call"
            sys.modules["SPSSINC_TRANS"].FIRST = False
    except:
        pass
"""

import inspect, re, copy, sys
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

    args = args[args.keys()[0]]
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

    ##debugging
    #try:
        #import wingdbstub
        #if wingdbstub.debugger != None:
            #import time
            #wingdbstub.debugger.StopDebug()
            #time.sleep(2)
            #wingdbstub.debugger.StartDebug()
    #except:
        #pass

    #enable localization
    global _
    try:
        _("---")
    except:
        def _(msg):
            return msg

    # A HELP subcommand overrides all else
    if args.has_key("HELP"):
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
        print("Help file not found:" + helpspec)
try:    #override
    from extension import helper
except:
    pass

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

    # global variable FIRST is provided so that functions can initialize themselves
    # It will be set True on first call.  It is up to the function to set it to False if desired
    global FIRST
    FIRST = True
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
            
        co, spssparams, modname, _customfunction = resolvestr(formula) 
        
        with DataStep():
            ds = spss.Dataset()     # the active dataset
            # Create or modify result variable definition(s)

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

            data = {}
            params = {}
            params["_customfunction"] = _customfunction

            # try to map variable names to positions.
            # spssparams will contain module and function names as well as variable names
            # Since we can't tell them apart, exceptions here are ignored and caught later
            # when the expression is eval'ed

            MISSINGS = {}
            for k in spssparams:
                try:
                    data[k] = ds.varlist[k].index  # replace names with indexes
                    MISSINGS[k] = ds.varlist[k].missingValues
                except:
                    pass

            # loop through the cases calling the function for each case

            for i, row in enumerate(ds.cases):
                for k, v in data.items():
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

                if i == 0 and inspect.isclass(_customfunction):
                    try:
                        params["_customfunction"] = eval(co, params).func
                    except:
                        raise ValueError(_("The formula specified a class, but the class did not produce a suitable function to call"))
                try:
                    res = eval(co, params)   # compute the requested values
                except:
                    raise ValueError(_("The formula references an undefined variable or could not be evaluated:\n") + str(sys.exc_value))
                if isinstance(res, (basestring, int, float, type(None))):
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
                    ds.cases[i, resultindexes[r]] = res[r]   # update the dataset
    finally:
        del FIRST    # really should be in finally 

def resolvestr(afunc):
    """Return a compiled function suitable for execution by eval

    afunc is a string in the form module.func
    or module.func(parm=value,...)to be imported.
    """

    # f is the function name
    # co is the compiled expression
    # spssp is the set of parameters to be satisfied from SPSS case data
    f, co, spssp = factor(afunc)

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
        exec "from %s import %s as _customfunction" % (modname, bf[-1])

    return co, spssp, modname, _customfunction

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
            raise ValueError(_("The formula syntax given is invalid:\n") + str(sys.exc_value))
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
    
    
