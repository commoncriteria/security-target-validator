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
from enum import Enum, auto

class mod_type(Enum):
    REPLACE = auto()

ns = {'cc': "https://niap-ccevs.org/cc/v1",
      'sec': "https://niap-ccevs.org/cc/v1/section",
      'htm': "http://www.w3.org/1999/xhtml"}

def SCH(tag):
    return "{http://www.ascc.net/xml/schematron}"+tag

def CC(tag):
    return "{"+ns['cc']+"}"+tag

class State:
    """ This class represents the Protection Profile document. """
    def __init__(self, root, rule, url, modsfrs, base_url):
        self.root = root
#        self.parent_map = {c: p for p in self.root.iter() for c in p}
        self.rule = rule
        self.url = url
        self.modsfrs = modsfrs
        self.derive_schematron(base_url)
        
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

    def get_non_opt_comps(self, base_url):
        if base_url is None:
            xpath_str = ".//cc:f-component[not(ancestor::cc:obj-sfrs|ancestor::cc:opt-sfrs)]"

        else:
            xpath_str = ".//cc:base-pp[cc:git/cc:url/text()='"+base_url+"']//cc:f-component|.//cc:man-sfrs//cc:f-component|.//cc:sel-sfrs//cc:f-component|.//cc:impl-dep-sfrs//cc:f-component"
        return self.root.xpath(xpath_str, namespaces=ns)

    def derive_fcomponent_asserts(self, base_url):
        fcomps = self.get_non_opt_comps(base_url)
        for fcomp in fcomps:
            cc_id = fcomp.attrib["cc-id"]
            if cc_id in self.modsfrs:
                # TODO: There are times when we're not replacing
                # the whole SFR and just replace
                # The depends
                if self.modsfrs[cc_id]==mod_type.REPLACE:
                    continue
                else:
                    print("Can only handle full replace now")
                    sys.exit(1)
            dependses = fcomp.findall("./cc:depends", ns)

            if dependses:
                for depends in dependses:
                    if State.is_optional_depends(depends):
                        continue
                    for attr in depends.attrib:
                        dependency_id = depends.attrib[attr]
                        self.handle_fcomp(fcomp, dependee_id=dependency_id)
            else:
                self.handle_fcomp(fcomp)
                
    def derive_extdocs_asserts(self):
        # Derives schematron rules for external documents
        for pack in self.root.findall(".//cc:include-pkg", ns):
            self.derive_extdoc_asserts(pack, "package", True)
        # Here we have to keep track of the base that's being served
        for mod in self.root.findall(".//cc:modules/cc:module", ns):
            self.derive_extdoc_asserts(mod, "module", False)

    def derive_extdoc_asserts(self, el, st_el_name, should_add_by_default):
    # Derives schematron rules for a single external document
        depends_list = el.findall("./cc:depends", ns)
        if depends_list:
            for depends in depends_list:
                if State.is_optional_depends(depends):
                    continue
                for dependency_id in depends.attrib:
                    self.handle_dependent_doc(el, depends.attrib[dependency_id], st_el_name)
        elif should_add_by_default:
            self.handle_dependent_doc(el, None, st_el_name)

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
                    
    def derive_schematron(self, base_url):
        self.derive_fcomponent_asserts(base_url)
        self.derive_extdocs_asserts()
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
    
    def handle_fcomp(self, dependent, dependee_id=None):
        cc_id = dependent.attrib["cc-id"]
        test = self.ME()+"//cc:f-component[@cc-id='"+cc_id
        reason = cc_id.upper()
        if "iteration" in dependent.attrib:
            test += "' and @iteration='"+dependent.attrib['iteration']
            reason += "/"+dependent.attrib['iteration']
        test += "']"
        reason +=  " is mandatory and, therefore, must also be included in the ST.("
        if dependee_id is not None:
            test += " or not("+self.ME()+"//*[@id='"+dependee_id+"'])"
            reason = "If '"+dependee_id+"' is selected, then " + cc_id + " must also be included.("
        reason += self.url + ")"
        add_assert(self.rule, test, reason)
                    
    def handle_dependent_doc(self, dependent, dependee_id, st_tag):
        baseurl = dependent.find(".//cc:url",ns).text;
        branch =  dependent.find(".//cc:branch",ns).text;
        # test = EXT"//cc:package[cc:git/cc:url='"+baseurl + "' and cc:git/cc:branch='"+branch+"']"\
        #     " or not("+self.ME()+"//cc:selectable[@id='"+dependee_id+"'])"
        test = "//cc:"+st_tag+"[cc:git/cc:url='"+baseurl + "' and cc:git/cc:branch='"+branch+"']"
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
    return el, patt

def add_assert(rule_el, test, descrip):
    assert_el = SubElement(rule_el, SCH("assert"))
    assert_el.attrib["test"]=test
    assert_el.text = descrip

def make_root_rule(patt):
    rule = SubElement(patt, SCH("rule"))
    rule.attrib["context"]="/*"
    return rule

# Patt is carrying the results back
# base_url is only not none for modules
def derive_rule_from_ppdoc(pp_str, url, patt, modsfrs, base_url=None):
    pp = lxml.etree.fromstring(pp_str)
    rule = make_root_rule(patt)
    State(pp, rule, url, modsfrs, base_url)
    if base_url is None:
        return
    xpath=(".//cc:base-pp[cc:git/cc:url/text()='"+base_url+"']")
    base_el = pp.xpath(xpath, namespaces=ns)
    if len(base_el) != 1:
        print("Expected exactly 1 base-pp in the module")
        sys.exit(1)
    for modsfr in base_el[0].findall(CC("modified-sfrs//")+CC("f-component")):
        cc_id = modsfr.attrib["cc-id"]
        modsfrs[cc_id]=mod_type.REPLACE
    return
        

def get_str_of_effective(git_el, is_updating, workdir):
        url = git_el.find(CC("url")).text
        branch = git_el.find(CC("branch")).text
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
            os.system("git pull -f --all")
        os.system("git checkout " + branch)
        try:
            commit_el = git_el.find(CC("commit"))
            revert_cmd = "git reset --hard "+commit_el.text
#            revert_cmd = "git revert  -n "+commit_el.text
            os.system(revert_cmd)
        except:
            print("Failed to revert project. Pushing forward")

        env=dict(os.environ, TRANS=str(mydir))
        # subprocess.Popen(['make', '-s'], env=env).wait()
        # This uses 'make' to build the effective PP because
        # the project may have adjusted the hooks, so the
        process = subprocess.Popen("make -s", env=env, shell=True,text=True, stdout=subprocess.PIPE)
        out,err = process.communicate()
        return out, url

# os.path.realpath(__file__)
mydir=(Path(os.path.dirname(__file__))/".."/"mock-transforms").resolve()
    
def get_all_effectives(st, is_updating, workdir):
    if not(workdir.is_dir()):
        print("The directory to store reference repositories does not exist: "+str(workdir))
        sys.exit(1)

    root, patt = make_schematron_skeleton()
    base_rule = make_root_rule(patt)
    add_assert(base_rule,
               "not(//cc:selectable[@exclusive='yes' and preceding-sibling::cc:selectable])",
               "Exclusive with selectable ")

    base_el = st.findall(".//"+CC("base-pp"))
    if len(base_el) != 1:
        print("Expected one base-pp element. Found " + len(base_el))
        sys.exit(1)
    baseurl = base_el[0].find(CC("git/")+CC("url")).text
    modsfrs = {}
    for git in st.findall(".//"+CC("module")+"/"+CC("git")):
        out, url = get_str_of_effective(git, is_updating, workdir)
        derive_rule_from_ppdoc(out, url, patt, modsfrs, base_url= baseurl)

    # Should be exactly one base-pp
    for git in st.findall(".//"+CC("base-pp")+"/"+CC("git")):
        out, url = get_str_of_effective(git, is_updating, workdir)
        derive_rule_from_ppdoc(out, url, patt, modsfrs)
    
    for git in st.findall(".//"+CC("package")+"/"+CC("git")):
        out, url = get_str_of_effective(git, is_updating, workdir)
        derive_rule_from_ppdoc(out, url, patt, {})
    print(lxml.etree.tostring(root, pretty_print=True, encoding='utf-8').decode("utf-8"))
    schematron = Schematron(root)
    res = schematron.validate(st)
    if res:
        print("SUCCESS: "+sys.argv[2])
    else:
        print("FAILURE: "+sys.argv[2])
        print(schematron.error_log)
        
        # eff_xml_str = subprocess.check_output("EFF_XML='&1' make -s effective", shell=True, text=True)
        # #pp_doc = lxml.etree.fromparse(eff_xml_str)
        # os.system("EFF_XML=effective.xml make effective")
        # pp_doc = lxml.etree.parse("effective.xml")
                    
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: [-v] [--dont-update] [<work-dir>] <st-xml>")
#        print("Usage: <pp-xml> <st-xml>")
        sys.exit(0)

    curr = 1
    should_update = True
    if sys.argv[curr] == "-v":
        is_verbose = True
        curr+=1
    if sys.argv[curr] == "--dont-update":
        should_update = False
        curr+=1
    workdir=Path.home()/"commoncriteria/ref-repo"
    tempy = Path(sys.argv[curr])
    if tempy.is_dir():
        workdir=tempy
        curr+=1
    st = lxml.etree.parse(sys.argv[2])
    get_all_effectives(st, should_update, workdir)

    

    
