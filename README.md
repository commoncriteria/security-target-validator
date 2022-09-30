# security-target-validator

Tool that validates a Common Criteria Security Target against 
Common Criteria Protection Profile Documents.

# System Requirements
This project requires a directory where it can download projects.
Right now, it's hardcoded to ~/commoncriteria/ref-repo, but that may change. 
This must exist before it can run.
It also requires _python3_ and _make_ to run.


# Security Target Description
First off, we acknowledge that this will probably have to change in the future.

Security Targets basically look like all the PP documents (base+modules+packages) put onto a single XML document.
Each document is wrapped with something ('base', 'package', 'module'), which doesn't really matter that much.
What matters is the _git_ element that refers to the project's URL, and the branch and commit ID that the ST should be validated against.

The contents of each document's section looks similar and most of it really doesn't matter. 
What does matter is that items with IDs are preserved with ID attribute intact, if they are part of the ST, and removed if they are not.
Basically if you're choosing a selection keep it in (unchanged) and if you're choosing not to make it part of the ST, remove it entirely.

