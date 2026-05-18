import argparse

parser = argparse.ArgumentParser(prog="AutoTest")

parser.add_argument("--report-dir", dest="report_dirrrr")

args = parser.parse_args()

print(args.report_dirrrr)