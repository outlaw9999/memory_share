# GEMINI.md (v1.2.4 TRIGGERS)

BEFORE EDIT:
kit recall "<intent>"

IF unknown schema:
kit introspect --json

IF multi-file OR core-symbol:
kit graph "<path>"

VERIFY:
pytest OR py_compile

DONE:
kit-vantage verify-memory

FAIL:
kit doctor
