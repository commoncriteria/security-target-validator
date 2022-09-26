#!/bin/env python3
import lxml.etree as ET
import sys


if __name__ == "__main__":
    if len(sys.argv)==1:
        print("Usage: <input-file> [<td1> [<td2> ...]]")
        sys.exit(0)

    schema_et = ET.parse(sys.argv[1])
    schematron = ET.Schematron(schema_et)

    for test_path in sys.argv[2:]:
        test = ET.parse(test_path)
        res = schematron.validate(test)
        if res:
            print("SUCCESS: "+test_path)
        else:
            print("FAILURE: "+ test_path)
            print(schematron.error_log)

