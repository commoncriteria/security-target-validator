# This is file is meant to collide with 

#- Path to input files
IN ?= input

H := \#\#

#- Base name(with extensions) of input and output files
BASE ?= $(shell echo "$${PWD$H*/}")

#- Input XML file
PP_XML ?= $(IN)/$(BASE).xml

#- Folder containing TDs
TD_DIR ?= input/tds
TDs ?= $(shell [ ! -d $(TD_DIR) ] || find $(TD_DIR) -name '*.xml' -type f)

hello:
	python3 $(TRANS)/cc_apply_tds.py $(PP_XML) $(TDs) 2>/dev/null
