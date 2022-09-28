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

def CC(tag):
    return "{"+ns['cc']+"}"+tag
class State:

    def __init__(self, root, rule, url):
        self.root = root
        self.parent_map = {c: p for p in self.root.iter() for c in p}
        self.rule = rule
        self.url = url
        self.derive_schematron()

    def is_foreign_depends(el):
        child = el.find("./*")        
        return child is not None

    def is_optional_depends(depends):
        child = depends.find("./*")
        if child is None:
            return False
        if child.tag == CC("optional"):
            return True
        return False

    
    def EXT(self, url):
        return "//cc:*[cc:git/cc:url='"+url+"']"
    
    def ME(self):
        return self.EXT(self.url)
        
    def derive_schematron(self):
        for fcomp in self.root.findall(".//cc:f-component[cc:depends]", ns):
            for depends in fcomp.findall("./cc:depends", ns):
                if State.is_optional_depends(depends):
                    continue
                for dependency_id in depends.attrib:
                    self.handle_dependent_fcomp(fcomp, depends.attrib[dependency_id])
        for pack in self.root.findall(".//cc:include-pkg", ns):
            depends_list = pack.findall("./cc:depends", ns)
            if depends_list:
                for depends in depends_list:
                    if State.is_optional_depends(depends):
                        continue
                    for dependency_id in depends.attrib:
                        self.handle_dependent_package(pack, depends.attrib[dependency_id])
            else:
                self.handle_dependent_package(pack, None)
                    
    def handle_dependent_fcomp(self, dependent, dependee_id):
        cc_id = dependent.attrib["cc-id"]
        test = self.ME()+"//cc:f-component[@cc-id='"+cc_id
        cc_id = cc_id.upper()
        if "iteration" in dependent.attrib:
            test += "' and @iteration='"+dependent.attrib['iteration']
            cc_id="/"+dependent.attrib['iteration']
        test += "'] or not("+self.ME()+"//*[@id='"+dependee_id+"'])"
        reason = "If '"+dependee_id+"' is selected, then " + cc_id + " must also be included."
        add_assert(self.rule, test, reason)

                    
    def handle_dependent_package(self, dependent, dependee_id):
        baseurl = dependent.find(".//cc:url",ns).text;
        branch =  dependent.find(".//cc:branch",ns).text;
        # test = EXT"//cc:package[cc:git/cc:url='"+baseurl + "' and cc:git/cc:branch='"+branch+"']"\
        #     " or not("+self.ME()+"//cc:selectable[@id='"+dependee_id+"'])"
        test = "//cc:package[cc:git/cc:url='"+baseurl + "' and cc:git/cc:branch='"+branch+"']"
        reason = baseurl + "," + branch + "must be included in all STs"
        if dependee_id is not None:
            test += " or not("+self.ME()+"//cc:selectable[@id='"+dependee_id+"'])"
            reason = "When selecting '" + dependee_id +"', you need to include " + baseurl + ", " + branch
        add_assert(self.rule, test, reason)


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
    add_assert(rule, "not(//cc:selectable[@exclusive='yes' and preceding-sibling::cc:selectable])", "Exclusive with selectable ")
    #    print(lxml.etree.tostring(el, pretty_print=True))
    pp = lxml.etree.parse(sys.argv[1])
    State(pp, rule, "https://github.com/commoncriteria/operatingsystem")
    print(lxml.etree.tostring(root, pretty_print=True, encoding='utf-8').decode("utf-8"))
    schematron = Schematron(root)

    st = lxml.etree.parse(sys.argv[2])
    res = schematron.validate(st)
    if res:
        print("SUCCESS: "+sys.argv[2])
    else:
        print("FAILURE: "+sys.argv[2])
        print(schematron.error_log)

    

    
