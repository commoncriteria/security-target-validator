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
import xml.etree.ElementTree as ET

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

    def __init__(self, root):
        self.root = root
        self.parent_map = {c: p for p in self.root.iter() for c in p}

        self.derive_schematron()
        
    def derive_schematron(self):
        for depend in self.root.findall(".//cc:depends", ns):
            if depend.find("./*"):
                print("There's a child")
            else:
                parent = self.parent_map[depend]
                for dependency_id in depend.attrib:
                    self.handle_dependency(parent, depend.attrib[dependency_id])




    def handle_dependency(self, dependent, dependee_id):

        rul = ""
        if dependent.tag == "{"+ns['cc']+"}include-pkg":
            baseurl = dependent.find(".//cc:url",ns).text;
            branch =  dependent.find(".//cc:branch",ns).text;
            rul = ".//cc:include-pkg[.//cc:url='"+baseurl + "' and .//cc:branch='"+branch+"']"
        elif dependent.tag == "{"+ns['cc']+"}f-component":
            cc_id = dependent.attrib["cc-id"]
            rul = ".//cc:f-component[@cc-id='"+cc_id
            if "iteration" in dependent.attrib:
                rul += "' and @iteration='"+dependent.attrib['iteration']
            rul += "']"
        else:
            return
        rul += " or .//*[@id='"+dependee_id+"']"
        print("<assert test=\""+ rul +"\"> </assert>") 
            
                    
if __name__ == "__main__":
    el = Element(SCH("schema"))
    for aa in ns:
        ns_element = SubElement(el, SCH("ns"))
        ns_element.attrib["prefix"] = aa
        ns_element.attrib["url"]= ns[aa]
        print("ns["+aa+"]: " + ns[aa])

    patt = SubElement(el, SCH("pattern"))
    patt.attrib["name"]="Basic"
    rule = SubElement(patt, SCH("rule"))
    rule.attrib["context"]="/*"
#    print(lxml.etree.tostring(el, pretty_print=True))
    print(lxml.etree.tostring(el))
    

    
    Schematron(el)
    if len(sys.argv) < 3:
        print("Usage: <pp-xml> <st-xml>")
        sys.exit(0)
    pp = ET.parse(sys.argv[1])
    State(pp)

    
