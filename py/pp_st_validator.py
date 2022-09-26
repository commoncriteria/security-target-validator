#!/usr/bin/env python3
"""
This python module takes in xml files that have been processed and
fixes internal references and counters (which are hard to do
with XSLT).
"""

import sys
from lxml.etree import Schematron
from  lxml.etree import Element, SubElement
import lxml.etree
# import xml.etree.ElementTree as ET

# from io import StringIO
# import re
# import string
# from xml.sax.saxutils import quoteattr, escape
ns = {'cc': "https://niap-ccevs.org/cc/v1",
      'sec': "https://niap-ccevs.org/cc/v1/section",
      'htm': "http://www.w3.org/1999/xhtml"}

def SCH(tag):
    return "{http://www.ascc.net/xml/schematron}"+tag

class State:

    def __init__(self, root, rule):
        self.root = root
        self.parent_map = {c: p for p in self.root.iter() for c in p}
        self.rule = rule
        self.derive_schematron()

    def is_foreign_depends(el):
        child = el.find("./*")        
        return child is not None
        
    def derive_schematron(self):
        for depend in self.root.findall(".//cc:depends", ns):
            if State.is_foreign_depends(depend):
                print("There's a child")
            else:
                parent = self.parent_map[depend]
                for dependency_id in depend.attrib:
                    self.handle_dependency(parent, depend.attrib[dependency_id])

    def handle_dependency(self, dependent, dependee_id):
        test = ""
        if dependent.tag == "{"+ns['cc']+"}include-pkg":
            baseurl = dependent.find(".//cc:url",ns).text;
            branch =  dependent.find(".//cc:branch",ns).text;
            test = ".//cc:include-pkg[.//cc:url='"+baseurl + "' and .//cc:branch='"+branch+"']"
        elif dependent.tag == "{"+ns['cc']+"}f-component":
            cc_id = dependent.attrib["cc-id"]
            test = ".//cc:f-component[@cc-id='"+cc_id
            if "iteration" in dependent.attrib:
                test += "' and @iteration='"+dependent.attrib['iteration']
            test += "']"
        else:
            return
        test += " or .//*[@id='"+dependee_id+"']"
        add_assert(self.rule, test, "")


def make_schematron_skeleton():
    el = Element(SCH("schema"))
    for aa in ns:
        ns_element = SubElement(el, SCH("ns"))
        ns_element.attrib["prefix"] = aa
        ns_element.attrib["uri"]= ns[aa]
        print("ns["+aa+"]: " + ns[aa])

    patt = SubElement(el, SCH("pattern"))
    patt.attrib["name"]="Basic"
    rule = SubElement(patt, SCH("rule"))
    rule.attrib["context"]="/*"
    return el, rule

def add_assert(rule_el, test, descrip):
    assert_el = SubElement(rule_el, SCH("assert"))
    assert_el.attrib["test"]=test
    assert_el.text = descrip

                    
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: <pp-xml> <st-xml>")
        sys.exit(0)

    root, rule = make_schematron_skeleton()
    add_assert(rule, "/*", "You shall not not pass.")
    #    print(lxml.etree.tostring(el, pretty_print=True))
    pp = lxml.etree.parse(sys.argv[1])
    State(pp, rule)
    print(lxml.etree.tostring(root, pretty_print=True, encoding='utf-8').decode("utf-8"))
    schematron = Schematron(root)

    st = lxml.etree.parse(sys.argv[2])
    res = schematron.validate(st)
    if res:
        print("SUCCESS: "+sys.argv[2])
    else:
        print("FAILURE: "+sys.argv[2])
        print(schematron.error_log)

    

    
