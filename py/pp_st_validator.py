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
import os
import subprocess
from pathlib import Path

ns = {'cc': "https://niap-ccevs.org/cc/v1",
      'sec': "https://niap-ccevs.org/cc/v1/section",
      'htm': "http://www.w3.org/1999/xhtml"}

def SCH(tag):
    return "{http://www.ascc.net/xml/schematron}"+tag

def CC(tag):
    return "{"+ns['cc']+"}"+tag

class State:
    """ This class represents the Protection Profile document. """
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

    def derive_fcomponent_asserts(self):
        for fcomp in self.root.findall(".//cc:f-component", ns):
            dependses = fcomp.findall("./cc:depends", ns)
            if dependses:
                for depends in dependses:
                    if State.is_optional_depends(depends):
                        continue
                    for dependency_id in depends.attrib:
                        self.handle_dependent_fcomp(fcomp, depends.attrib[dependency_id])
            else:
                self.handle_mandatory_fcomp(fcomp)
                
    def derive_packages_asserts(self):
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

    def derive_rules_asserts(self):
        for rule in self.root.findall(".//cc:rule[cc:if]", ns):
            if_el = rule.find("./cc:if",ns)
            if if_el is None:
                test = self.stringify_and(rule)
            else:
                test = "not"+self.stringify_and(if_el)
                then_el = rule.find("./cc:then", ns)
                test += " or " + self.stringify_and(then_el)
            reason = ""
            if "id" in rule.attrib:
                reason = "Rule (IF/THEN) id:'"+rule.attrib["id"]+"'"
            add_assert(self.rule, test , reason)
        
                    
    def derive_schematron(self):
        self.derive_fcomponent_asserts()
        self.derive_packages_asserts()
        self.derive_rules_asserts()

    def stringify_and(self, top):
        return self.stringify_loop(top, "and")

    def stringify_or(self, or_el):
        return self.stringify_loop(top, "or")

    def stringify_loop(self, top, op):
        magic = "("
        ret = ""
        spaced_op = " "+op+" "
        for child in top:
            ret += magic
            magic= spaced_op
            if child.tag == CC("ref-id"):
                ret += self.stringify_refid(child)
            elif child.tag == CC("and"): # This should never be called
                ret += self.stringify_and(child)
            elif child.tag == CC("or"):
                ret += self.stringify_or(child)
            elif child.tag == CC("doc"):
                ret += self.stringify_doc(child)
            elif child.tag == CC("not"):
                ret += "not"+self.stringify_and(child)
            else:
                Error("Blah")
        return ret+")"


    def stringify_refid(self, ref_el):
        return self.ME()+"//cc:*[@id='"+ref_el.text+"']"

    def stringify_doc(self, doc_el):
        ret=""
        local_doc_id = doc_el.attrib["ref"]
        doc_url = self.root.find("*[@id='"+local_doc_id+"']/cc:git/cc:url",ns).text
        magic="("
        for kid in doc_el:
            ret += magic + self.EXT(doc_url)+"//*[@id='" +kid.text+"']"
            magic= " and "
        return ret+")"

    def handle_mandatory_fcomp(self, dependent):
        cc_id = dependent.attrib["cc-id"]
        test = self.ME()+"//cc:f-component[@cc-id='"+cc_id
        cc_id = cc_id.upper()
        if "iteration" in dependent.attrib:
            test += "' and @iteration='"+dependent.attrib['iteration']
            cc_id="/"+dependent.attrib['iteration']
        test += "']"
        reason =  cc_id + " is mandatory and, therefore, must also be included in the ST."
        add_assert(self.rule, test, reason)
        
        
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
#        print("ns["+aa+"]: " + ns[aa])

    patt = SubElement(el, SCH("pattern"))
    patt.attrib["name"]="Basic"
    rule = SubElement(patt, SCH("rule"))
    rule.attrib["context"]="/*"
    return el, rule

def add_assert(rule_el, test, descrip):
    assert_el = SubElement(rule_el, SCH("assert"))
    assert_el.attrib["test"]=test
    assert_el.text = descrip


# def get_effective_doc(url, branch, fpath):
#     workdir = tempfile.TemporaryDirectory()
#     abspath = os.path.abspath(fpath)
#     commands = ("cd "+workdir.name +
#                 " && git clone --branch " + branch + " --recursive " + url +
#                 " && cd * && " +
#                 " (unset PP_XML; EFF_XML=\"" + abspath + "\"  make effective)")
#     os.system(commands)
def validate_st_against_ppdoc(st, pp_str, url):
    # print("Looking for "+pp_str)
    pp = lxml.etree.fromstring(pp_str)
    root, rule = make_schematron_skeleton()
    add_assert(rule, "not(//cc:selectable[@exclusive='yes' and preceding-sibling::cc:selectable])", "Exclusive with selectable ")
    State(pp, rule, url)
    print(lxml.etree.tostring(root, pretty_print=True, encoding='utf-8').decode("utf-8"))
    schematron = Schematron(root)
    res = schematron.validate(st)
    if res:
        print("SUCCESS: "+sys.argv[2])
    else:
        print("FAILURE: "+sys.argv[2])
        print(schematron.error_log)


    
def get_all_effectives(st, is_updating):
    workdir=Path.home()/"commoncriteria/ref-repo"
    mydir=(Path(".")/"mock-transforms").resolve()
    if not(workdir.is_dir()):
        print("The directory to store reference repositories does not exist: "+str(workdir))
        sys.exit(1)
    for gits in st.findall(".//"+CC("git")):
        url = gits.find(CC("url")).text
        branch = gits.find(CC("branch")).text
        projname = url.rsplit('/', 1)[-1]
        projdir = workdir/projname
        # TODO make this system agnostic
        if not(projdir.is_dir()):
            os.chdir(workdir)
            clone = "git clone --branch "+ branch + " " + url
            print("Cloning: " + clone)
            os.system(clone)
        os.chdir(projdir)
        if is_updating:
            os.system("git pull -f ")
        try:
            commit_el = gits.find(CC("commit"))
            revert_cmd = "git reset --hard "+commit_el.text
#            revert_cmd = "git revert  -n "+commit_el.text
            os.system(revert_cmd)
        except:
            print("Failed to revert project. Pushing forward")

        # print("Mydir is "+str(mydir))
        env=dict(os.environ, TRANS=str(mydir))
        # subprocess.Popen(['echo', 'hello'])

        # subprocess.Popen(['make', '-s'], env=env).wait()
        # sys.exit(0)

        process = subprocess.Popen("make -s", env=env, shell=True,text=True, stdout=subprocess.PIPE)
        out,err = process.communicate()
        # eff_xml_str = subprocess.check_output("EFF_XML='&1' make -s effective", shell=True, text=True)
        # #pp_doc = lxml.etree.fromparse(eff_xml_str)
        # os.system("EFF_XML=effective.xml make effective")
        validate_st_against_ppdoc(st, out, url)
        # pp_doc = lxml.etree.parse("effective.xml")
        # print("proj: "+projname)
        # print("Git: "+url)
                    
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: [--dont-update] <pp-xml> <work-dir>")
#        print("Usage: <pp-xml> <st-xml>")
        sys.exit(0)
    st = lxml.etree.parse(sys.argv[2])
    get_all_effectives(st, True)

    sys.exit(0)
    #    print(lxml.etree.tostring(el, pretty_print=True))

    

    
